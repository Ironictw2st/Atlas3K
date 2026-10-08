using System.Globalization;
using System.Text.Json;
using System.Text.Json.Nodes;
using Atlas3K.Core;
using Atlas3K.Core.Collab;
using Atlas3K.Core.Editing;

/// <summary>
/// Collaboration commands. Every command prints JSON (the terry MCP server wraps them); errors print {"error": ...}
/// and exit 1.
///   patch-export &lt;out.a3kpatch&gt; (--since "yyyy-MM-dd HH:mm" | --base &lt;map folder copy&gt;) [--label t] [--description t]
///   patch-info &lt;file.a3kpatch&gt;
///   patch-import &lt;file.a3kpatch&gt; [--dry-run]
///   patch-undo                        undo the last import
///   conflicts [--dir d]               open conflicts (of the last import, or a repo merge with --dir)
///   conflicts-resolve (ours|theirs) [--ids 1,2] [--dir d]
///   merge-file &lt;base&gt; &lt;ours&gt; &lt;theirs&gt; [--out f] [--name n]   one map-aware three-way merge
///   map-diff &lt;before&gt; &lt;after&gt;      entity / pixel diff of one file
/// Project repositories (git + GitHub; the repository is the kit's map folder):
///   collab-init [--github owner/name [--public] | --remote url]     collab-clone &lt;url|owner/name&gt;
///   collab-status   collab-commit [-m msg] [--force]   collab-pull   collab-push   collab-log [--count n]
///   collab-branch [name] [--create]   collab-merge &lt;branch&gt;   collab-revert &lt;rev&gt;   collab-diff [from] [to] [--markdown]
///   pr-create --title t [--body b] [--base main] [--draft]   pr-list [--state open]   pr-view &lt;n&gt;   pr-diff &lt;n&gt; [--post]
///   pr-checkout &lt;n&gt;   pr-comment &lt;n&gt; --body b   pr-review &lt;n&gt; approve|request-changes|comment [--body b]
///   pr-merge &lt;n&gt; [--method merge|squash|rebase]
///   pin-create --title t --x x --z z [--body b] [--layer l] [--entity id] [--assignee who]   pin-list [--state open]
///   pin-comment &lt;n&gt; --body b   pin-close &lt;n&gt; [--body b]
///   lock-list   lock-acquire (--file rel | --layer name | --rect x0,z0,x1,z1) [--reason r]   lock-release [ids] [--force]
/// merge-driver and textconv are what git calls (registered by collab-init / collab-clone).
/// </summary>
static class CollabCommands
{
    public static readonly string[] Names =
    [
        "patch-export", "patch-info", "patch-import", "patch-undo", "conflicts", "conflicts-resolve", "merge-file", "map-diff",
        "collab-init", "collab-clone", "collab-status", "collab-commit", "collab-pull", "collab-push", "collab-log", "collab-branch",
        "collab-merge", "collab-revert", "collab-diff",
        "pr-create", "pr-list", "pr-view", "pr-diff", "pr-checkout", "pr-comment", "pr-review", "pr-merge",
        "pin-create", "pin-list", "pin-comment", "pin-close", "lock-list", "lock-acquire", "lock-release",
        "merge-driver", "textconv",
    ];

    private static string CliExe => Environment.ProcessPath ?? throw new InvalidOperationException("cannot tell where Atlas3K.Cli is");

    private static readonly JsonSerializerOptions Indented = new() { WriteIndented = true };

    public static int Run(ProjectPaths paths, string command, string[] a)
    {
        // What git runs: plain output, exit code = result.
        if (command == "merge-driver")
            return a.Length >= 4 ? CollabRepo.MergeDriver(a[0], a[1], a[2], a[3]) : 2;
        if (command == "textconv")
        {
            Console.Out.Write(CollabRepo.TextConv(a[0]));
            return 0;
        }
        var args = new Args(a.Where(s => !s.Equals("--json", StringComparison.OrdinalIgnoreCase)));
        try
        {
            JsonNode result = command switch
            {
                "patch-export" => Export(paths, args),
                "patch-info" => Json(PatchPackage.ReadManifest(args.Positional(0, "package"))),
                "patch-import" => Import(paths, args),
                "patch-undo" => new JsonObject
                {
                    ["undone"] = Json(new FileJournal(PatchSources.ImportDir(paths)).Undo(1, args.Flag("--force"))),
                },
                "conflicts" => Conflicts(ConflictsOf(paths, args)),
                "conflicts-resolve" => Resolve(paths, args),
                "merge-file" => MergeFile(args),
                "map-diff" => MapDiff(args),
                _ when command.StartsWith("collab-") || command.StartsWith("pr-") || command.StartsWith("pin-") || command.StartsWith("lock-")
                    => Repo(paths, command, args),
                _ => throw new ArgumentException($"unknown command {command}"),
            };
            Console.WriteLine(result.ToJsonString(Indented));
            return 0;
        }
        catch (Exception ex) when (ex is not OutOfMemoryException)
        {
            Console.WriteLine(new JsonObject { ["error"] = ex.Message, ["type"] = ex.GetType().Name }.ToJsonString(Indented));
            return 1;
        }
    }

    private static JsonNode Json<T>(T value) => JsonSerializer.SerializeToNode(value)!;

    private static JsonNode Export(ProjectPaths paths, Args args)
    {
        var output = args.Positional(0, "output .a3kpatch");
        if (!output.EndsWith(PatchPackage.Extension, StringComparison.OrdinalIgnoreCase)) output += PatchPackage.Extension;
        List<PatchPackage.Source> sources;
        string label;
        if (args.Option("--base") is { } baseDir)
        {
            sources = PatchSources.FromFolder(paths, baseDir);
            label = $"changes against {Path.GetFileName(baseDir.TrimEnd('\\', '/'))}";
        }
        else if (args.Option("--since") is { } since)
        {
            var time = DateTime.Parse(since, CultureInfo.CurrentCulture);
            sources = PatchSources.FromJournals(paths, time);
            label = $"edits since {time:yyyy-MM-dd HH:mm}";
        }
        else throw new ArgumentException("pass --since \"yyyy-MM-dd HH:mm\" (edits from the journals) or --base <copy of the map folder>");
        var manifest = PatchPackage.Export(sources, Path.GetFullPath(output), paths.MapName, args.Option("--label") ?? label,
            args.Option("--description"));
        if (manifest.Files.Count == 0)
        {
            File.Delete(output);
            throw new InvalidOperationException("nothing changed: no package written");
        }
        var node = (JsonObject)Json(manifest);
        node["package"] = Path.GetFullPath(output);
        node["bytes"] = new FileInfo(output).Length;
        return node;
    }

    private static JsonNode Import(ProjectPaths paths, Args args)
    {
        var dir = PatchSources.ImportDir(paths);
        var package = args.Positional(0, "package");
        var manifest = PatchPackage.ReadManifest(package);
        if (!manifest.Map.Equals(paths.MapName, StringComparison.OrdinalIgnoreCase) && !args.Flag("--force"))
            throw new InvalidOperationException($"the package is for map {manifest.Map}, not {paths.MapName} (pass --map {manifest.Map}, or --force)");
        var r = PatchPackage.Import(package, paths.AssemblyKitRoot, new FileJournal(dir),
            new ConflictSet(Path.Combine(dir, "conflicts")), args.Flag("--dry-run"));
        return new JsonObject
        {
            ["package"] = Path.GetFullPath(package),
            ["label"] = manifest.Label,
            ["author"] = manifest.Author,
            ["dry_run"] = r.DryRun,
            ["seq"] = r.Seq,
            ["conflicts"] = r.Conflicts,
            ["files"] = new JsonArray(r.Files.Select(f => (JsonNode)new JsonObject
            {
                ["path"] = f.Path,
                ["action"] = f.Action,
                ["summary"] = f.Merge?.Summary,
                ["conflicts"] = f.Merge is { Clean: false } m ? Json(m.Conflicts) : null,
            }).ToArray()),
            ["next"] = r.Conflicts > 0 && !r.DryRun ? "review with `conflicts`, then `conflicts-resolve ours|theirs [--ids ..]`" : null,
        };
    }

    /// <summary>--dir, else the repository's merge conflicts when it has any, else the last package import's
    /// (--import forces those).</summary>
    private static ConflictSet ConflictsOf(ProjectPaths paths, Args args)
    {
        if (args.Option("--dir") is { } dir) return new ConflictSet(dir);
        if (!args.Flag("--import") && CollabRepo.Open(paths) is { } repo && repo.Conflicts.Entries().Count > 0) return repo.Conflicts;
        return new ConflictSet(Path.Combine(PatchSources.ImportDir(paths), "conflicts"));
    }

    private static JsonNode Conflicts(ConflictSet set) => new JsonObject
    {
        ["dir"] = set.Dir,
        ["open"] = Json(set.Open()),
        ["resolved"] = set.Entries().Count(e => e.Resolved),
    };

    private static JsonNode Resolve(ProjectPaths paths, Args args)
    {
        var set = ConflictsOf(paths, args);
        var n = ConflictResolver.Resolve(set, args.Positional(0, "ours|theirs"), args.Ints("--ids"));
        var node = (JsonObject)Conflicts(set);
        node["resolved_now"] = n;
        return node;
    }

    private static JsonNode MergeFile(Args args)
    {
        string b = args.Positional(0, "base"), o = args.Positional(1, "ours"), t = args.Positional(2, "theirs");
        var r = MapMerge.Merge(b, o, t, args.Option("--out") ?? o, args.Option("--name") ?? Path.GetFileName(o));
        return Json(r);
    }

    private static JsonNode MapDiff(Args args)
    {
        string before = args.Positional(0, "before"), after = args.Positional(1, "after");
        return MapMerge.TypeOf(after) switch
        {
            MapMerge.FileType.TerryXml => new JsonObject
            {
                ["entities"] = Json(TerryXmlMerge.Diff(File.Exists(before) ? File.ReadAllText(before) : null,
                                                       File.Exists(after) ? File.ReadAllText(after) : null)),
            },
            MapMerge.FileType.Raster => Json(RasterMerge.Diff(RasterImage.Load(before), RasterImage.Load(after))),
            _ => new JsonObject { ["same"] = FileJournal.Hash(File.ReadAllBytes(before)) == FileJournal.Hash(File.ReadAllBytes(after)) },
        };
    }

    // ---------------------------------------------------------------- repositories, GitHub, locks

    private static JsonNode Repo(ProjectPaths paths, string command, Args args)
    {
        switch (command)
        {
            case "collab-init":
            {
                var repo = CollabRepo.Init(paths, CliExe, args.Option("--remote"), args.Option("--github"), args.Flag("--public"));
                return new JsonObject
                {
                    ["root"] = repo.Root,
                    ["status"] = Json(repo.GetStatus()),
                    ["remote"] = repo.Git.TryGit("remote", "get-url", "origin").Text,
                };
            }
            case "collab-clone":
            {
                var repo = CollabRepo.Clone(paths, args.Positional(0, "repository (URL or owner/name)"), CliExe);
                new LockService(repo).Refresh();
                return new JsonObject { ["root"] = repo.Root, ["map"] = repo.Paths.MapName, ["next"] = $"open the map with --map {repo.Paths.MapName}" };
            }
        }
        var r = CollabRepo.Require(paths);
        var gh = new GitHubService(r);
        var locks = new LockService(r);
        int N() => int.Parse(args.Positional(0, "number"), CultureInfo.InvariantCulture);
        string Need(string option) => args.Option(option) ?? throw new ArgumentException($"{command} needs {option}");
        switch (command)
        {
            case "collab-status":
            {
                if (r.HasRemote) r.Git.TryGit("fetch", "-q", "origin");
                var node = (JsonObject)Json(r.GetStatus());
                node["locks"] = Json(locks.Refresh());
                node["me"] = r.Identity();
                return node;
            }
            case "collab-commit":
                return new JsonObject { ["commit"] = r.Commit(args.Option("-m") ?? args.Option("--message"), args.Flag("--force")) };
            case "collab-pull":
            {
                var result = r.Pull();
                locks.Refresh();
                return Sync(result, r);
            }
            case "collab-push": return new JsonObject { ["output"] = r.Push() };
            case "collab-log":
                return Json(r.Log(int.Parse(args.Option("--count") ?? "30", CultureInfo.InvariantCulture), args.PositionalOrNull(0)));
            case "collab-branch":
                if (args.PositionalOrNull(0) is { } branch) r.Switch(branch, args.Flag("--create"));
                return new JsonObject { ["current"] = r.GetStatus().Branch, ["branches"] = Json(r.Branches()) };
            case "collab-merge": return Sync(r.Merge(args.Positional(0, "branch")), r);
            case "collab-revert": return Sync(r.Revert(args.Positional(0, "revision")), r);
            case "collab-diff":
            {
                var diff = r.Diff(args.PositionalOrNull(0) ?? "HEAD", args.PositionalOrNull(1));
                return args.Flag("--markdown") ? new JsonObject { ["markdown"] = CollabRepo.DiffMarkdown(diff) } : Json(diff);
            }
            case "pr-create":
                return gh.CreatePr(Need("--title"), args.Option("--body"), args.Option("--base"), args.Flag("--draft"));
            case "pr-list": return gh.ListPrs(args.Option("--state") ?? "open");
            case "pr-view": return gh.ViewPr(N());
            case "pr-diff":
            {
                var diff = gh.PrDiff(N());
                var md = CollabRepo.DiffMarkdown(diff);
                if (args.Flag("--post")) gh.CommentPr(N(), md);
                return new JsonObject { ["files"] = Json(diff), ["markdown"] = md, ["posted"] = args.Flag("--post") };
            }
            case "pr-checkout": return new JsonObject { ["output"] = gh.CheckoutPr(N()) };
            case "pr-comment": return new JsonObject { ["output"] = gh.CommentPr(N(), Need("--body")) };
            case "pr-review":
                return new JsonObject { ["output"] = gh.ReviewPr(N(), args.Positional(1, "approve|request-changes|comment"), args.Option("--body")) };
            case "pr-merge": return new JsonObject { ["output"] = gh.MergePr(N(), args.Option("--method") ?? "merge") };
            case "pin-create":
                return Json(gh.CreatePin(Need("--title"), args.Option("--body"), Double(Need("--x")), Double(Need("--z")),
                    args.Option("--layer"), args.Option("--entity"), args.Option("--assignee") is { } who ? [who] : null));
            case "pin-list": return Json(gh.ListPins(args.Option("--state") ?? "open"));
            case "pin-comment": return new JsonObject { ["output"] = gh.CommentIssue(N(), Need("--body")) };
            case "pin-close": return new JsonObject { ["output"] = gh.ClosePin(N(), args.Option("--body")) };
            case "lock-list": return Json(locks.Refresh());
            case "lock-acquire":
            {
                if (args.Option("--rect") is { } rect)
                {
                    var v = rect.Split(',').Select(Double).ToArray();
                    if (v.Length != 4) throw new ArgumentException("--rect is x0,z0,x1,z1");
                    double[] norm = [Math.Min(v[0], v[2]), Math.Min(v[1], v[3]), Math.Max(v[0], v[2]), Math.Max(v[1], v[3])];
                    return Json(locks.Acquire("region", string.Join(',', norm.Select(x => x.ToString(CultureInfo.InvariantCulture))),
                        args.Option("--label"), args.Option("--reason"), norm));
                }
                if (args.Option("--layer") is { } layer)
                {
                    var file = new EntityEditor(paths).Layer(layer).FilePath ?? throw new InvalidOperationException($"layer {layer} has no file");
                    return Json(locks.Acquire("layer", Rel(r, file), layer, args.Option("--reason")));
                }
                var path = Need("--file");
                return Json(locks.Acquire("file", Rel(r, Path.IsPathRooted(path) ? path : Path.Combine(r.Root, path)), Path.GetFileName(path),
                    args.Option("--reason")));
            }
            case "lock-release":
            {
                var ids = args.PositionalOrNull(0)?.Split(',', StringSplitOptions.RemoveEmptyEntries);
                return new JsonObject { ["released"] = Json(locks.Release(ids, args.Flag("--force"))) };
            }
            default: throw new ArgumentException($"unknown command {command}");
        }
    }

    private static string Rel(CollabRepo repo, string path) => Path.GetRelativePath(repo.Root, path).Replace(Path.DirectorySeparatorChar, '/');

    private static double Double(string s) => double.Parse(s, CultureInfo.InvariantCulture);

    private static JsonNode Sync(CollabRepo.SyncResult result, CollabRepo repo)
    {
        var node = (JsonObject)Json(result);
        if (result.Conflicts > 0 || result.Unmerged.Count > 0)
        {
            node["conflict_list"] = Json(repo.Conflicts.Open());
            node["next"] = "review with `conflicts`, resolve with `conflicts-resolve ours|theirs [--ids ..]`, then `collab-commit`";
        }
        return node;
    }

    /// <summary>"--name value" options, "--flag" switches and positional arguments.</summary>
    internal sealed class Args(IEnumerable<string> raw)
    {
        private static readonly string[] Flags = ["--force", "--dry-run", "--all", "--draft", "--public", "--create", "--markdown", "--post", "--import"];
        private readonly List<string> _a = raw.ToList();

        public string? Option(string name)
        {
            var i = _a.FindIndex(s => s.Equals(name, StringComparison.OrdinalIgnoreCase));
            if (i < 0) return null;
            return i + 1 < _a.Count ? _a[i + 1] : throw new ArgumentException($"{name} needs a value");
        }

        public bool Flag(string name) => _a.Contains(name, StringComparer.OrdinalIgnoreCase);

        public int[]? Ints(string name) =>
            Option(name)?.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
                .Select(v => int.Parse(v, CultureInfo.InvariantCulture)).ToArray();

        public string Positional(int index, string what) =>
            PositionalOrNull(index) ?? throw new ArgumentException($"missing {what}");

        public string? PositionalOrNull(int index)
        {
            var positional = new List<string>();
            for (var i = 0; i < _a.Count; i++)
            {
                if (!_a[i].StartsWith("--", StringComparison.Ordinal)) { positional.Add(_a[i]); continue; }
                if (!Flags.Contains(_a[i], StringComparer.OrdinalIgnoreCase)) i++;
            }
            return index < positional.Count ? positional[index] : null;
        }
    }
}
