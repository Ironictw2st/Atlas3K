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
/// </summary>
static class CollabCommands
{
    public static readonly string[] Names =
    [
        "patch-export", "patch-info", "patch-import", "patch-undo", "conflicts", "conflicts-resolve", "merge-file", "map-diff",
    ];

    private static readonly JsonSerializerOptions Indented = new() { WriteIndented = true };

    public static int Run(ProjectPaths paths, string command, string[] a)
    {
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

    private static ConflictSet ConflictsOf(ProjectPaths paths, Args args) =>
        new(args.Option("--dir") ?? Path.Combine(PatchSources.ImportDir(paths), "conflicts"));

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

    /// <summary>"--name value" options, "--flag" switches and positional arguments.</summary>
    internal sealed class Args(IEnumerable<string> raw)
    {
        private static readonly string[] Flags = ["--force", "--dry-run", "--all", "--draft", "--web", "--no-push"];
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
