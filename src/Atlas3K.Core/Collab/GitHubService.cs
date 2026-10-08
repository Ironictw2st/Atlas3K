using System.Globalization;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace Atlas3K.Core.Collab;

/// <summary>
/// GitHub for a project repository, through the GitHub CLI (gh): pull requests with Atlas3K map diffs, reviews, and
/// map pins. A map pin is an issue labelled <see cref="PinLabel"/> whose body carries its world position in an HTML
/// comment (<c>&lt;!-- atlas3k-pin {"map":..,"x":..,"z":..} --&gt;</c>), so it reads as a normal issue on GitHub and
/// shows up as a marker in Atlas3K.
/// </summary>
public sealed partial class GitHubService(CollabRepo repo)
{
    public const string PinLabel = "map-pin";

    private GitService Git => repo.Git;

    private JsonNode GhJson(params string[] args) => JsonNode.Parse(Git.Gh(args).StdOut)!;

    // ---------------------------------------------------------------- pull requests

    /// <summary>Pushes the current branch and opens a PR whose description ends with the map diff against
    /// <paramref name="baseBranch"/>.</summary>
    public JsonObject CreatePr(string title, string? body, string? baseBranch = null, bool draft = false)
    {
        baseBranch ??= DefaultBranch();
        repo.Push();
        Git.TryGit("fetch", "-q", "origin", baseBranch);
        var mergeBase = Git.Git("merge-base", $"origin/{baseBranch}", "HEAD").Text;
        var diff = repo.Diff(mergeBase, "HEAD");
        var full = (body is { Length: > 0 } ? body + "\n\n" : "") + CollabRepo.DiffMarkdown(diff);
        var args = new List<string> { "pr", "create", "--title", title, "--body", full, "--base", baseBranch };
        if (draft) args.Add("--draft");
        var url = Git.Gh([.. args]).Text.Split('\n')[^1].Trim();
        return new JsonObject { ["url"] = url, ["files"] = diff.Count, ["base"] = baseBranch };
    }

    public string DefaultBranch() =>
        Git.TryGh("repo", "view", "--json", "defaultBranchRef", "--jq", ".defaultBranchRef.name") is { Ok: true, Text.Length: > 0 } r
            ? r.Text : "main";

    public JsonNode ListPrs(string state = "open") =>
        GhJson("pr", "list", "--state", state, "--limit", "100", "--json",
            "number,title,author,headRefName,baseRefName,state,url,isDraft,reviewDecision,updatedAt");

    public JsonNode ViewPr(int number) =>
        GhJson("pr", "view", number.ToString(CultureInfo.InvariantCulture), "--json",
            "number,title,body,author,state,url,headRefName,baseRefName,isDraft,mergeable,reviewDecision,comments,reviews,files");

    /// <summary>The map diff of a PR (its head against the merge base with its base branch).</summary>
    public List<CollabRepo.FileDiff> PrDiff(int number)
    {
        var pr = ViewPr(number);
        var baseRef = pr["baseRefName"]!.GetValue<string>();
        var local = $"refs/atlas3k/pr/{number}";
        Git.Git("fetch", "-q", "origin", $"+refs/pull/{number}/head:{local}", baseRef);
        var mergeBase = Git.Git("merge-base", $"origin/{baseRef}", local).Text;
        return repo.Diff(mergeBase, local);
    }

    public string CheckoutPr(int number) => Git.Gh("pr", "checkout", number.ToString(CultureInfo.InvariantCulture)).Text;

    public string CommentPr(int number, string body) => Git.Gh("pr", "comment", number.ToString(CultureInfo.InvariantCulture), "--body", body).Text;

    /// <summary>action: approve, request-changes or comment.</summary>
    public string ReviewPr(int number, string action, string? body)
    {
        if (action is not ("approve" or "request-changes" or "comment")) throw new ArgumentException("action must be approve, request-changes or comment");
        var args = new List<string> { "pr", "review", number.ToString(CultureInfo.InvariantCulture), "--" + action };
        if (body is { Length: > 0 }) args.AddRange(["--body", body]);
        else if (action != "approve") throw new ArgumentException($"{action} needs a body");
        return Git.Gh([.. args]).Text;
    }

    /// <summary>Merges a PR on GitHub. GitHub merges by lines, not Atlas3K's driver: when the PR conflicts with its base,
    /// merge the base into the PR branch locally first (collab-merge), push, then merge.</summary>
    public string MergePr(int number, string method = "merge", bool deleteBranch = true)
    {
        if (method is not ("merge" or "squash" or "rebase")) throw new ArgumentException("method must be merge, squash or rebase");
        var pr = ViewPr(number);
        if (pr["mergeable"]?.GetValue<string>() == "CONFLICTING")
            throw new InvalidOperationException($"PR #{number} conflicts with {pr["baseRefName"]}: check it out (pr-checkout {number}), " +
                                                $"collab-merge origin/{pr["baseRefName"]}, resolve, commit, push, then merge");
        var args = new List<string> { "pr", "merge", number.ToString(CultureInfo.InvariantCulture), "--" + method };
        if (deleteBranch) args.Add("--delete-branch");
        return Git.Gh([.. args]).Text;
    }

    // ---------------------------------------------------------------- map pins

    public sealed record Pin(int Number, string Title, string State, string Url, string Author, List<string> Assignees,
                             List<string> Labels, string Map, double X, double Z, string? Layer, string? EntityId, string Body);

    [GeneratedRegex(@"<!--\s*atlas3k-pin\s*(\{.*?\})\s*-->", RegexOptions.Singleline)]
    private static partial Regex PinMarker();

    public Pin CreatePin(string title, string? body, double x, double z, string? layer = null, string? entityId = null,
                         IEnumerable<string>? assignees = null, IEnumerable<string>? labels = null)
    {
        Git.TryGh("label", "create", PinLabel, "--color", "1D76DB", "--description", "Atlas3K map pin (location in the map)");
        var marker = new JsonObject
        {
            ["map"] = repo.Paths.MapName,
            ["x"] = Math.Round(x, 2),
            ["z"] = Math.Round(z, 2),
        };
        if (layer is not null) marker["layer"] = layer;
        if (entityId is not null) marker["entity"] = entityId;
        var text = (body ?? "") + $"\n\n📍 `{repo.Paths.MapName}` at x {x:0.##}, z {z:0.##}" + (entityId is null ? "" : $", entity `{entityId}`")
                   + $"\n<!-- atlas3k-pin {marker.ToJsonString()} -->\n";
        var args = new List<string> { "issue", "create", "--title", title, "--body", text, "--label", PinLabel };
        foreach (var l in labels ?? []) args.AddRange(["--label", l]);
        foreach (var a in assignees ?? []) args.AddRange(["--assignee", a]);
        var url = Git.Gh([.. args]).Text.Split('\n')[^1].Trim();
        var number = int.Parse(url[(url.LastIndexOf('/') + 1)..], CultureInfo.InvariantCulture);
        return ListPins("all").First(p => p.Number == number);
    }

    public List<Pin> ListPins(string state = "open")
    {
        var issues = GhJson("issue", "list", "--label", PinLabel, "--state", state, "--limit", "500", "--json",
            "number,title,body,state,url,author,assignees,labels").AsArray();
        var pins = new List<Pin>();
        foreach (var i in issues)
        {
            var body = i!["body"]?.GetValue<string>() ?? "";
            var m = PinMarker().Match(body);
            if (!m.Success) continue;
            JsonNode? marker;
            try { marker = JsonNode.Parse(m.Groups[1].Value); }
            catch (JsonException) { continue; }
            pins.Add(new Pin(i["number"]!.GetValue<int>(), i["title"]!.GetValue<string>(), i["state"]!.GetValue<string>(),
                i["url"]!.GetValue<string>(), i["author"]?["login"]?.GetValue<string>() ?? "",
                i["assignees"]!.AsArray().Select(a => a!["login"]!.GetValue<string>()).ToList(),
                i["labels"]!.AsArray().Select(a => a!["name"]!.GetValue<string>()).ToList(),
                marker!["map"]?.GetValue<string>() ?? "", marker["x"]!.GetValue<double>(), marker["z"]!.GetValue<double>(),
                marker["layer"]?.GetValue<string>(), marker["entity"]?.GetValue<string>(),
                PinMarker().Replace(body, "").Trim()));
        }
        File.WriteAllText(Path.Combine(repo.StateDir, "pins.json"), JsonSerializer.Serialize(pins, LockService.Json));
        return pins;
    }

    /// <summary>The pins as last listed (for drawing without a network call).</summary>
    public static List<Pin> CachedPins(string mapDir)
    {
        var path = Path.Combine(mapDir, ".git", "atlas3k", "pins.json");
        return File.Exists(path) ? JsonSerializer.Deserialize<List<Pin>>(File.ReadAllText(path), LockService.Json) ?? [] : [];
    }

    public string CommentIssue(int number, string body) => Git.Gh("issue", "comment", number.ToString(CultureInfo.InvariantCulture), "--body", body).Text;

    public string ClosePin(int number, string? comment = null)
    {
        var args = new List<string> { "issue", "close", number.ToString(CultureInfo.InvariantCulture) };
        if (comment is { Length: > 0 }) args.AddRange(["--comment", comment]);
        return Git.Gh([.. args]).Text;
    }
}
