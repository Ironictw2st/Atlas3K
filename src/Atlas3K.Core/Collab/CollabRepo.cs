using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Atlas3K.Core.Editing;

namespace Atlas3K.Core.Collab;

/// <summary>
/// A map project shared through git: the repository is the kit's map folder (raw_data\terrain\campaigns\&lt;map&gt;),
/// so every editor keeps working on the files where they are. Rasters go to Git LFS. Atlas3K registers itself as the
/// merge driver for .layer / .terry / rasters (entity and pixel merges instead of line merges, see
/// <see cref="MapMerge"/>) and as the diff text converter for rasters. Conflicts the driver cannot decide keep ours
/// and are listed in .git\atlas3k\conflicts until resolved.
/// </summary>
public sealed class CollabRepo
{
    public const string ProjectFile = ".atlas3k/project.json";

    public ProjectPaths Paths { get; }
    public GitService Git { get; }
    public string Root => Git.Root;

    private CollabRepo(ProjectPaths paths, string root)
    {
        Paths = paths;
        Git = new GitService(root);
    }

    /// <summary>The map's repository, or null when the map folder is not one.</summary>
    public static CollabRepo? Open(ProjectPaths paths) =>
        IsRepo(paths.AkTerrainDir) ? new CollabRepo(paths, paths.AkTerrainDir) : null;

    public static CollabRepo Require(ProjectPaths paths) =>
        Open(paths) ?? throw new InvalidOperationException($"{paths.AkTerrainDir} is not an Atlas3K project repository (run collab-init or collab-clone)");

    public static bool IsRepo(string dir) =>
        Directory.Exists(Path.Combine(dir, ".git")) && File.Exists(Path.Combine(dir, ProjectFile));

    public string StateDir => Path.Combine(Git.GitDir, "atlas3k");
    public ConflictSet Conflicts => new(Path.Combine(StateDir, "conflicts"));

    // ---------------------------------------------------------------- setup

    public const string GitAttributes = """
        # Atlas3K: rasters in Git LFS; map files merged per entity / per pixel by Atlas3K (see .atlas3k/project.json)
        *.tif filter=lfs diff=atlas3k merge=atlas3k -text
        *.tiff filter=lfs diff=atlas3k merge=atlas3k -text
        *.png filter=lfs diff=atlas3k merge=atlas3k -text
        *.layer merge=atlas3k -text
        *.terry merge=atlas3k -text

        """;

    public const string GitIgnore = """
        # Atlas3K: per-user Terry state and temporary files
        *.terry.user
        *.tmp

        """;

    /// <summary>
    /// Turns the map folder into a project repository (or finishes setting up an existing clone): .gitattributes,
    /// .gitignore, .atlas3k/project.json, the merge/diff drivers and LFS hooks, and a first commit. With
    /// <paramref name="github"/> ("owner/name" or "name") it creates that GitHub repository (private unless
    /// <paramref name="isPublic"/>) and pushes; with <paramref name="remote"/> it adds and pushes to that URL.
    /// </summary>
    public static CollabRepo Init(ProjectPaths paths, string cliExe, string? remote = null, string? github = null, bool isPublic = false)
    {
        var dir = paths.AkTerrainDir;
        if (!Directory.Exists(dir)) throw new DirectoryNotFoundException($"map folder not found: {dir}");
        RequireTools(github is not null);
        var git = new GitService(dir);
        if (!Directory.Exists(Path.Combine(dir, ".git"))) git.Git("init", "-b", "main");
        WriteIfMissing(Path.Combine(dir, ".gitattributes"), GitAttributes);
        WriteIfMissing(Path.Combine(dir, ".gitignore"), GitIgnore);
        var project = Path.Combine(dir, ProjectFile);
        if (!File.Exists(project))
        {
            Directory.CreateDirectory(Path.GetDirectoryName(project)!);
            File.WriteAllText(project, new JsonObject
            {
                ["map"] = paths.MapName,
                ["created"] = DateTime.Now.ToString("s"),
                ["kit_note"] = "Clone with Atlas3K (collab-clone) into an assembly kit that has this map's base data.",
            }.ToJsonString(new JsonSerializerOptions { WriteIndented = true }) + "\n");
        }
        var repo = new CollabRepo(paths, dir);
        repo.Configure(cliExe);
        if (!repo.Git.TryGit("rev-parse", "--verify", "HEAD").Ok)
        {
            repo.Git.Git("add", "-A");
            repo.Git.Git("commit", "-q", "-m", $"Atlas3K project: {paths.MapName}");
        }
        if (github is not null)
            repo.Git.Gh("repo", "create", github, isPublic ? "--public" : "--private", "--source", ".", "--remote", "origin", "--push");
        else if (remote is not null)
        {
            if (!repo.Git.TryGit("remote", "get-url", "origin").Ok) repo.Git.Git("remote", "add", "origin", remote);
            repo.Git.Git("push", "-u", "origin", "HEAD");
        }
        return repo;
    }

    /// <summary>
    /// Clones a project repository (URL, or GitHub "owner/name") into the kit as the map it holds, then registers
    /// the drivers. Refuses when that map folder already exists.
    /// </summary>
    public static CollabRepo Clone(ProjectPaths paths, string source, string cliExe)
    {
        RequireTools(false);
        var campaigns = Path.GetDirectoryName(paths.AkTerrainDir)!;
        Directory.CreateDirectory(campaigns);
        var temp = Path.Combine(campaigns, ".a3k_clone_" + Guid.NewGuid().ToString("N")[..8]);
        var git = new GitService(campaigns);
        var isUrl = source.Contains("://") || source.StartsWith("git@") || Directory.Exists(source);
        if (isUrl) git.Git("clone", source, temp);
        else git.Gh("repo", "clone", source, temp);
        try
        {
            var projectFile = Path.Combine(temp, ProjectFile);
            if (!File.Exists(projectFile)) throw new InvalidDataException($"{source} is not an Atlas3K project repository (no {ProjectFile})");
            var map = JsonNode.Parse(File.ReadAllText(projectFile))!["map"]!.GetValue<string>();
            var mapPaths = paths with { MapName = map };
            if (Directory.Exists(mapPaths.AkTerrainDir))
                throw new IOException($"{mapPaths.AkTerrainDir} already exists; move it away (or clone into another kit with --ak)");
            Directory.Move(temp, mapPaths.AkTerrainDir);
            var repo = new CollabRepo(mapPaths, mapPaths.AkTerrainDir);
            repo.Configure(cliExe);
            return repo;
        }
        finally
        {
            if (Directory.Exists(temp)) TryDelete(temp);
        }
    }

    /// <summary>Registers Atlas3K's merge driver and raster diff in this clone's local git config, and LFS hooks.</summary>
    public void Configure(string cliExe)
    {
        var exe = cliExe.Replace('\\', '/');
        Git.Git("config", "merge.atlas3k.name", "Atlas3K map merge (entities, pixels)");
        Git.Git("config", "merge.atlas3k.driver", $"\"{exe}\" merge-driver %O %A %B %P");
        Git.Git("config", "diff.atlas3k.textconv", $"\"{exe}\" textconv");
        Git.Git("config", "diff.atlas3k.cachetextconv", "true");
        Git.TryGit("lfs", "install", "--local");
        Directory.CreateDirectory(StateDir);
        File.WriteAllText(Path.Combine(StateDir, "user"), Identity());
    }

    private static void RequireTools(bool gh)
    {
        if (!GitService.Available("git")) throw new InvalidOperationException("git is not installed (https://git-scm.com)");
        if (!GitService.Available("git", "lfs", "version")) throw new InvalidOperationException("git-lfs is not installed (https://git-lfs.com)");
        if (gh && !GitService.Available("gh")) throw new InvalidOperationException("the GitHub CLI is not installed (https://cli.github.com), or pass a remote URL instead");
    }

    private static void WriteIfMissing(string path, string text)
    {
        if (!File.Exists(path)) File.WriteAllText(path, text.ReplaceLineEndings("\n"));
    }

    private static void TryDelete(string dir)
    {
        try { Directory.Delete(dir, recursive: true); } catch (Exception e) when (e is IOException or UnauthorizedAccessException) { }
    }

    /// <summary>Who this user is to collaborators: the GitHub login when gh is signed in, else git's user.name.</summary>
    public string Identity()
    {
        var cached = Path.Combine(StateDir, "user");
        if (File.Exists(cached) && File.ReadAllText(cached).Trim() is { Length: > 0 } known) return known;
        try
        {
            if (Git.TryGh("api", "user", "--jq", ".login") is { Ok: true } gh && gh.Text.Length > 0) return gh.Text;
        }
        catch (System.ComponentModel.Win32Exception) { }
        return Git.TryGit("config", "user.name") is { Ok: true } n && n.Text.Length > 0 ? n.Text : Environment.UserName;
    }

    public bool HasRemote => Git.TryGit("remote", "get-url", "origin").Ok;

    // ---------------------------------------------------------------- status & history

    public sealed record FileStatus(string Path, string Status);

    public sealed record Status(string Branch, string? Upstream, int Ahead, int Behind, List<FileStatus> Changes, List<string> Unmerged,
                                bool Merging, int OpenConflicts, string SuggestedMessage);

    public Status GetStatus()
    {
        var branch = Git.TryGit("rev-parse", "--abbrev-ref", "HEAD").Text;
        var upstream = Git.TryGit("rev-parse", "--abbrev-ref", "@{u}") is { Ok: true } u ? u.Text : null;
        int ahead = 0, behind = 0;
        if (upstream is not null && Git.TryGit("rev-list", "--left-right", "--count", "HEAD...@{u}") is { Ok: true } c)
        {
            var parts = c.Text.Split('\t', ' ');
            ahead = int.Parse(parts[0]);
            behind = int.Parse(parts[^1]);
        }
        var changes = new List<FileStatus>();
        var unmerged = new List<string>();
        foreach (var line in Git.Git("status", "--porcelain=v1", "--untracked-files=all").StdOut.Split('\n', StringSplitOptions.RemoveEmptyEntries))
        {
            var code = line[..2];
            var path = Unquote(line[3..]);
            if (code is "UU" or "AA" or "DU" or "UD" or "AU" or "UA" or "DD") unmerged.Add(path);
            changes.Add(new FileStatus(path, code.Trim() switch
            {
                "??" => "new",
                "M" or "MM" or "AM" => "modified",
                "A" => "added",
                "D" => "deleted",
                var s when s.StartsWith('R') => "renamed",
                var s => s,
            }));
        }
        var merging = File.Exists(Path.Combine(Git.GitDir, "MERGE_HEAD"));
        return new Status(branch, upstream, ahead, behind, changes, unmerged, merging, Conflicts.Open().Count, SuggestMessage());
    }

    private static string Unquote(string p) => p.Length > 1 && p[0] == '"' && p[^1] == '"' ? p[1..^1] : p;

    /// <summary>A commit message from the edit journals' labels since the last commit.</summary>
    public string SuggestMessage()
    {
        var since = Git.TryGit("log", "-1", "--format=%cI") is { Ok: true, Text.Length: > 0 } l ? DateTime.Parse(l.Text) : DateTime.MinValue;
        var labels = PatchSources.Journals(Paths).SelectMany(j => j.History()).Where(e => e.Time > since)
            .OrderBy(e => e.Time).Select(e => e.Label).Distinct().ToList();
        return labels.Count switch
        {
            0 => "",
            1 => labels[0],
            _ => $"{labels[0]} (+{labels.Count - 1} more edits)\n\n" + string.Join("\n", labels.Select(x => "- " + x)),
        };
    }

    /// <summary>Stages everything and commits (concluding a merge when one is in progress). Refuses while merge
    /// conflicts are open unless <paramref name="force"/>.</summary>
    public string Commit(string? message, bool force = false)
    {
        var open = Conflicts.Open();
        if (open.Count > 0 && !force)
            throw new InvalidOperationException($"{open.Count} merge conflict(s) are still open: resolve them (conflicts-resolve ours|theirs) or pass --force to keep ours");
        Git.Git("add", "-A");
        var merging = File.Exists(Path.Combine(Git.GitDir, "MERGE_HEAD"));
        if (!merging && Git.TryGit("diff", "--cached", "--quiet").Ok) throw new InvalidOperationException("nothing to commit");
        message = string.IsNullOrWhiteSpace(message) ? SuggestMessage() : message;
        if (merging && string.IsNullOrWhiteSpace(message)) Git.Git("commit", "-q", "--no-edit");
        else Git.Git("commit", "-q", "-m", string.IsNullOrWhiteSpace(message) ? "Map edits" : message);
        if (open.Count == 0 || force) Conflicts.Clear();
        return Git.Git("rev-parse", "--short", "HEAD").Text;
    }

    public sealed record CommitInfo(string Hash, string Author, DateTime Date, string Subject, List<string> Files);

    public List<CommitInfo> Log(int count = 30, string? rev = null)
    {
        var args = new List<string> { "log", $"-{count}", "--format=%x1e%H%x1f%an%x1f%aI%x1f%s", "--name-only" };
        if (rev is not null) args.Add(rev);
        var text = Git.Git([.. args]).StdOut;
        return text.Split('\x1e', StringSplitOptions.RemoveEmptyEntries).Select(block =>
        {
            var lines = block.Split('\n');
            var f = lines[0].Split('\x1f');
            return new CommitInfo(f[0], f[1], DateTime.Parse(f[2]), f[3], lines.Skip(1).Where(l => l.Trim().Length > 0).Select(l => l.Trim()).ToList());
        }).ToList();
    }

    public List<string> Branches() =>
        Git.Git("branch", "-a", "--format=%(refname:short)").StdOut.Split('\n', StringSplitOptions.RemoveEmptyEntries)
            .Where(b => !b.Contains("atlas3k/locks") && b != "origin").ToList();

    public void Switch(string branch, bool create)
    {
        if (create) Git.Git("switch", "-c", branch);
        else Git.Git("switch", branch);
    }

    // ---------------------------------------------------------------- sync

    public sealed record SyncResult(bool Ok, string Output, List<string> Unmerged, int Conflicts);

    /// <summary>git pull (merge, so Atlas3K's driver merges map files). Conflicts are returned, not thrown.</summary>
    public SyncResult Pull()
    {
        Conflicts.Clear();
        var r = Git.TryGit("pull", "--no-rebase", "--no-edit");
        return AfterMerge(r);
    }

    /// <summary>Merges another branch into the current one with Atlas3K's driver.</summary>
    public SyncResult Merge(string branch)
    {
        Conflicts.Clear();
        if (HasRemote) Git.TryGit("fetch", "origin");
        return AfterMerge(Git.TryGit("merge", "--no-edit", branch));
    }

    public SyncResult Revert(string rev)
    {
        Conflicts.Clear();
        return AfterMerge(Git.TryGit("revert", "--no-edit", rev));
    }

    private SyncResult AfterMerge(GitService.Output r)
    {
        var status = GetStatus();
        if (!r.Ok && status.Unmerged.Count == 0) throw new InvalidOperationException((r.StdErr + r.StdOut).Trim());
        return new SyncResult(r.Ok, (r.StdOut + r.StdErr).Trim(), status.Unmerged, status.OpenConflicts);
    }

    public string Push()
    {
        var r = Git.Git("push", "-u", "origin", "HEAD");
        return (r.StdOut + r.StdErr).Trim();
    }

    // ---------------------------------------------------------------- map-aware diff

    public sealed record FileDiff(string Path, string Status, string Kind, string Summary,
                                  List<TerryXmlMerge.EntityChange>? Entities = null, RasterMerge.Change? Pixels = null);

    /// <summary>What changed between two revisions (null <paramref name="to"/> = the working tree), per map file.</summary>
    public List<FileDiff> Diff(string from = "HEAD", string? to = null, int maxEntities = 500)
    {
        var args = new List<string> { "diff", "--name-status", "--no-renames", from };
        if (to is not null) args.Add(to);
        var result = new List<FileDiff>();
        var lines = Git.Git([.. args]).StdOut.Split('\n', StringSplitOptions.RemoveEmptyEntries).ToList();
        if (to is null)
            lines.AddRange(Git.Git("ls-files", "--others", "--exclude-standard").StdOut.Split('\n', StringSplitOptions.RemoveEmptyEntries)
                .Select(p => "A\t" + p));
        foreach (var line in lines)
        {
            var parts = line.Split('\t');
            var (code, path) = (parts[0], parts[^1]);
            var status = code switch { "A" => "added", "D" => "deleted", _ => "modified" };
            var before = Git.Show(from, path);
            var after = to is null
                ? File.Exists(Path.Combine(Root, path)) ? File.ReadAllBytes(Path.Combine(Root, path)) : null
                : Git.Show(to, path);
            result.Add(DiffFile(path, status, before, after, maxEntities));
        }
        return result;
    }

    public static FileDiff DiffFile(string path, string status, byte[]? before, byte[]? after, int maxEntities = 500)
    {
        switch (MapMerge.TypeOf(path))
        {
            case MapMerge.FileType.TerryXml:
                var changes = TerryXmlMerge.Diff(before is null ? null : Encoding.UTF8.GetString(before), after is null ? null : Encoding.UTF8.GetString(after));
                return new FileDiff(path, status, "terry", PatchPackage.Summarise(changes), changes.Take(maxEntities).ToList());
            case MapMerge.FileType.Raster when before is not null && after is not null:
                var dir = Directory.CreateTempSubdirectory("a3k_diff_").FullName;
                try
                {
                    var (b, a) = (System.IO.Path.Combine(dir, "b" + System.IO.Path.GetExtension(path)), System.IO.Path.Combine(dir, "a" + System.IO.Path.GetExtension(path)));
                    File.WriteAllBytes(b, before);
                    File.WriteAllBytes(a, after);
                    var change = RasterMerge.Diff(RasterImage.Load(b), RasterImage.Load(a));
                    return new FileDiff(path, status, "raster",
                        change.Pixels == 0 ? "no pixel changes" : $"{change.Pixels} pixel(s) in {change.Cells.Count} cell(s), bounds [{string.Join(", ", change.Bounds!)}]",
                        Pixels: change with { Cells = change.Cells.Take(maxEntities).ToList() });
                }
                catch (Exception e) when (e is InvalidDataException or IOException) { return new FileDiff(path, status, "raster", "unreadable raster"); }
                finally { Directory.Delete(dir, recursive: true); }
            default:
                return new FileDiff(path, status, MapMerge.TypeOf(path) == MapMerge.FileType.Raster ? "raster" : "file", status);
        }
    }

    /// <summary>A Markdown summary of a diff (for commits, PR descriptions and comments).</summary>
    public static string DiffMarkdown(List<FileDiff> diff, int maxRows = 40)
    {
        if (diff.Count == 0) return "_No map changes._";
        var sb = new StringBuilder();
        var entities = diff.Sum(d => d.Entities?.Count ?? 0);
        var pixels = diff.Sum(d => d.Pixels?.Pixels ?? 0);
        sb.AppendLine($"**Atlas3K map diff**: {diff.Count} file(s), {entities} entity change(s), {pixels:N0} raster pixel(s)\n");
        sb.AppendLine("| File | Change | Summary |");
        sb.AppendLine("|---|---|---|");
        foreach (var d in diff.Take(maxRows)) sb.AppendLine($"| `{d.Path}` | {d.Status} | {d.Summary} |");
        if (diff.Count > maxRows) sb.AppendLine($"| … | | {diff.Count - maxRows} more file(s) |");
        var located = diff.SelectMany(d => d.Entities ?? []).Where(e => e.Location is not null).Take(15).ToList();
        if (located.Count > 0)
        {
            sb.AppendLine("\n<details><summary>Changed entities (world x, z)</summary>\n");
            foreach (var e in located)
                sb.AppendLine($"- {e.Change} `{e.Id}` {e.Name} @ {e.Location![0]:0.#}, {e.Location[1]:0.#}{(e.Fields.Count > 0 ? ": " + string.Join(", ", e.Fields.Take(6)) : "")}");
            sb.AppendLine("\n</details>");
        }
        return sb.ToString();
    }

    // ---------------------------------------------------------------- git drivers

    /// <summary>
    /// git merge driver (%O %A %B %P): merges into %A and returns 0, or 1 with conflicts recorded (the file keeps ours
    /// for them). LFS pointers are resolved to content first and the result is stored back in LFS.
    /// </summary>
    public static int MergeDriver(string basePath, string oursPath, string theirsPath, string name)
    {
        var root = GitService.FindRoot(Environment.CurrentDirectory) ?? Environment.CurrentDirectory;
        var git = new GitService(root);
        var temp = Directory.CreateTempSubdirectory("a3k_merge_").FullName;
        try
        {
            var o = File.ReadAllBytes(oursPath);
            var lfs = GitService.IsLfsPointer(o);
            var ext = Path.GetExtension(name);
            string Stage(string tag, byte[] bytes)
            {
                var p = Path.Combine(temp, tag + ext);
                File.WriteAllBytes(p, git.Smudge(bytes, name));
                return p;
            }
            var b = File.ReadAllBytes(basePath);
            var t = File.ReadAllBytes(theirsPath);
            var bp = b.Length == 0 && (o.Length > 0 || t.Length > 0) ? null : Stage("base", b);
            var op = Stage("ours", o);
            var tp = Stage("theirs", t);
            var r = MapMerge.Merge(bp, op, tp, op, name);
            var merged = File.ReadAllBytes(op);
            File.WriteAllBytes(oursPath, lfs ? git.Clean(merged, name) : merged);
            Console.Error.WriteLine($"Atlas3K merge {name}: {r.Summary}");
            if (r.Clean) return 0;
            var set = new ConflictSet(Path.Combine(git.GitDir, "atlas3k", "conflicts"));
            set.Add(root, name, r.Conflicts, tp);
            foreach (var c in r.Conflicts.Take(10)) Console.Error.WriteLine($"  CONFLICT {c.Detail}");
            return 1;
        }
        finally { TryDelete(temp); }
    }

    /// <summary>git textconv for rasters: size and a hash per 64-pixel cell, so diffs show which cells changed.</summary>
    public static string TextConv(string path)
    {
        var bytes = File.ReadAllBytes(path);
        if (GitService.IsLfsPointer(bytes))
        {
            var root = GitService.FindRoot(Environment.CurrentDirectory) ?? Environment.CurrentDirectory;
            bytes = new GitService(root).Smudge(bytes, path);
        }
        var temp = Path.Combine(Path.GetTempPath(), $"a3k_tc_{Guid.NewGuid():N}{Path.GetExtension(path)}");
        try
        {
            File.WriteAllBytes(temp, bytes);
            var r = RasterImage.Load(temp);
            var sb = new StringBuilder($"{r.Kind} {r.Width}x{r.Height}\n");
            var cell = RasterMerge.Cell;
            for (var cy = 0; cy * cell < r.Height; cy++)
                for (var cx = 0; cx * cell < r.Width; cx++)
                {
                    using var h = System.Security.Cryptography.IncrementalHash.CreateHash(System.Security.Cryptography.HashAlgorithmName.SHA1);
                    var w = Math.Min(cell, r.Width - cx * cell) * r.BytesPerPixel;
                    for (var y = cy * cell; y < Math.Min(r.Height, (cy + 1) * cell); y++)
                        h.AppendData(r.Data, (y * r.Width + cx * cell) * r.BytesPerPixel, w);
                    sb.Append("cell ").Append(cx * cell).Append(',').Append(cy * cell).Append(' ')
                      .Append(Convert.ToHexString(h.GetHashAndReset())[..12]).Append('\n');
                }
            return sb.ToString();
        }
        catch (Exception e) when (e is InvalidDataException or IOException)
        {
            return $"binary {bytes.Length} bytes {FileJournal.Hash(bytes)}\n";
        }
        finally { File.Delete(temp); }
    }
}
