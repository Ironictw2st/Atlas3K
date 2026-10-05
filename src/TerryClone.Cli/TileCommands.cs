using System.Globalization;
using System.Text.Json;
using System.Text.Json.Nodes;
using TerryClone.Core;
using TerryClone.Core.Campaign.TileMapCheck;
using TerryClone.Formats.Maps;

/// <summary>
/// tiles-* commands: validated editing of the kit's campaign tile_map.png (see <see cref="TileMapEditor"/>).
/// Every command prints JSON (the terry MCP server wraps them); errors print {"error": ...} and exit 1.
/// <c>--tilemap &lt;png&gt;</c> edits another tile map (a copy) instead of the kit's.
/// </summary>
static class TileCommands
{
    public static readonly string[] Names =
    [
        "tiles-info", "tiles-get", "tiles-edit", "tiles-validate", "tiles-preview", "tiles-undo", "tiles-checkpoint",
        "tiles-rollback", "tiles-history", "tiles-replay", "tiles-holes", "tiles-simulate",
    ];

    private static readonly JsonSerializerOptions Indented = new() { WriteIndented = true };

    public static int Run(ProjectPaths paths, string command, string[] a)
    {
        var args = new Args(a.Where(s => !s.Equals("--json", StringComparison.OrdinalIgnoreCase)));
        try
        {
            var editor = new TileMapEditor(paths, args.Option("--tilemap"));
            JsonNode result = command switch
            {
                "tiles-info" => Info(editor),
                "tiles-get" => Get(editor, args),
                "tiles-edit" => Edit(editor, paths, args),
                "tiles-validate" => Validate(editor, paths, args),
                "tiles-preview" => Preview(editor, paths, args),
                "tiles-undo" => Undone(editor.Undo(int.Parse(args.Option("--steps") ?? "1"), args.Flag("--force"))),
                "tiles-checkpoint" => new JsonObject { ["checkpoint"] = args.Positional(0, "label"), ["seq"] = editor.Journal.Checkpoint(args.Positional(0, "label")) },
                "tiles-rollback" => Undone(editor.Rollback(args.Positional(0, "label"), args.Flag("--force"))),
                "tiles-history" => History(editor),
                "tiles-replay" => EditResultJson(editor, paths, args, editor.Replay(int.Parse(args.Option("--from") ?? "1"),
                    int.Parse(args.Option("--to") ?? int.MaxValue.ToString(CultureInfo.InvariantCulture)), args.Flag("--dry-run"),
                    args.Flag("--force"), args.Flag("--allow-warnings"))),
                "tiles-holes" => Holes(editor, paths, args),
                "tiles-simulate" => Simulate(editor, args),
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

    private static JsonNode Info(TileMapEditor editor)
    {
        var map = editor.Load();
        var db = editor.Database;
        var counts = map.HexColours().GroupBy(c => c).ToDictionary(g => g.Key, g => g.Count());
        var sets = new JsonArray();
        foreach (var s in db.TileSets)
        {
            var tiles = db.Tiles.Where(t => t.TileSet.Equals(s.Name, StringComparison.OrdinalIgnoreCase)).ToList();
            sets.Add(new JsonObject
            {
                ["name"] = s.Name, ["colour"] = $"#{s.Rgb:x6}", ["hexes"] = counts.GetValueOrDefault(s.Rgb),
                ["kind"] = TileMapValidator.Category(s.Name) == TileMapValidator.Category(null) ? "area" : "line/coast",
                ["tiles"] = tiles.Count,
            });
        }
        var known = db.TileSets.Select(s => s.Rgb).ToHashSet();
        return new JsonObject
        {
            ["tile_map"] = editor.TileMapPath, ["hexes"] = new JsonArray(map.Width, map.Height),
            ["note"] = "hex [col,row], row 0 = south; ops take a tile set by name or \"#rrggbb\"",
            ["sets"] = sets,
            ["other_colours"] = new JsonObject(counts.Where(k => !known.Contains(k.Key)).OrderByDescending(k => k.Value).Take(20)
                .Select(k => KeyValuePair.Create($"#{k.Key:x6}", (JsonNode?)k.Value))),
        };
    }

    private static JsonNode Get(TileMapEditor editor, Args a)
    {
        var map = editor.Load();
        var ops = new TileMapOps(map, editor.Database);
        var hexes = new List<(int Col, int Row)>();
        if (a.Ints("--hexes") is { } h) for (var i = 0; i + 1 < h.Length; i += 2) hexes.Add((h[i], h[i + 1]));
        if (a.Doubles("--world") is { } w) for (var i = 0; i + 1 < w.Length; i += 2) hexes.Add(TileMapEditor.WorldToHex(w[i], w[i + 1]));
        if (a.Ints("--rect") is [var c0, var r0, var c1, var r1]) hexes.AddRange(ops.Rect(c0, r0, c1, r1));
        if (hexes.Count == 0) throw new ArgumentException("--hexes c,r[,c,r...] | --world x,z[,x,z...] | --rect c0,r0,c1,r1");
        var limit = int.Parse(a.Option("--limit") ?? "400");
        return new JsonObject
        {
            ["total"] = hexes.Count,
            ["hexes"] = new JsonArray(hexes.Take(limit).Select(x =>
            {
                if (!ops.InMap(x.Col, x.Row)) return (JsonNode)new JsonObject { ["hex"] = new JsonArray(x.Col, x.Row), ["outside"] = true };
                var (wx, wz) = TileMapEditor.HexToWorld(x.Col, x.Row);
                return new JsonObject
                {
                    ["hex"] = new JsonArray(x.Col, x.Row), ["set"] = ops.SetAt(x.Col, x.Row), ["colour"] = $"#{ops.Colour(x.Col, x.Row):x6}",
                    ["world"] = new JsonArray(Math.Round(wx, 3), Math.Round(wz, 3)),
                };
            }).ToArray()),
        };
    }

    private static JsonNode Edit(TileMapEditor editor, ProjectPaths paths, Args a)
    {
        var source = a.Option("--ops") ?? throw new ArgumentException("--ops <file | - | inline JSON array>");
        var text = source == "-" ? Console.In.ReadToEnd() : source.TrimStart().StartsWith('[') || source.TrimStart().StartsWith('{') ? source : File.ReadAllText(source);
        var node = JsonNode.Parse(text);
        var ops = node as JsonArray ?? new JsonArray(node!.DeepClone());
        var result = editor.Edit(ops, a.Option("--label"), a.Flag("--dry-run"), a.Flag("--force"), allowWarnings: a.Flag("--allow-warnings"));
        return EditResultJson(editor, paths, a, result);
    }

    private static JsonNode EditResultJson(TileMapEditor editor, ProjectPaths paths, Args a, TileMapEditor.EditResult r)
    {
        var allowWarnings = a.Flag("--allow-warnings");
        var o = new JsonObject
        {
            ["written"] = r.Written, ["seq"] = r.Seq, ["changed_hexes"] = r.Changed.Count,
            ["results"] = r.OpResults.DeepClone(),
            ["new_issues"] = Findings(r.NewIssues, allowWarnings),
            ["existing_issue_hexes_in_area"] = r.ExistingIssues,
        };
        if (r.Changed.Count > 0)
            o["bounds"] = new JsonArray(r.Changed.Min(h => h.Col), r.Changed.Min(h => h.Row), r.Changed.Max(h => h.Col), r.Changed.Max(h => h.Row));
        o["status"] = r.Written ? "written; run BOB Terrain / Tilemap, then tiles-holes, then build steps global_map, global_mesh"
            : r.Changed.Count == 0 ? "nothing changed"
            : a.Flag("--dry-run") ? "dry run: not written"
            : "NOT written: the edit causes the blocking issues listed (fix them, or pass --allow-warnings / --force)";
        if (a.Flag("--preview") && r.Changed.Count > 0)
        {
            var pad = 6;
            var marks = r.NewIssues.SelectMany(f => f.AllHexes.Select(h => new TileMapPreview.Mark(h[0], h[1], TileMapEditor.Blocks(f, allowWarnings))));
            o["png"] = TileMapPreview.Render(r.Map, new TileMapOps(r.Map, editor.Database).SetOf,
                r.Changed.Min(h => h.Col) - pad, r.Changed.Min(h => h.Row) - pad, r.Changed.Max(h => h.Col) + pad, r.Changed.Max(h => h.Row) + pad,
                PreviewPath(paths, "edit"), int.Parse(a.Option("--width") ?? "1024"), r.Changed, marks);
        }
        return o;
    }

    private static JsonArray Findings(IEnumerable<TileMapFinding> findings, bool allowWarnings) =>
        new(findings.Select(f => (JsonNode)new JsonObject
        {
            ["code"] = f.Code, ["severity"] = f.Severity, ["blocking"] = TileMapEditor.Blocks(f, allowWarnings), ["count"] = f.Count,
            ["message"] = f.Message, ["hexes"] = new JsonArray(f.Hexes.Take(40).Select(h => (JsonNode)new JsonArray(h[0], h[1])).ToArray()),
        }).ToArray());

    private static JsonNode Validate(TileMapEditor editor, ProjectPaths paths, Args a)
    {
        var map = editor.Load();
        IEnumerable<(int, int)>? region = a.Ints("--rect") is [var c0, var r0, var c1, var r1]
            ? new TileMapOps(map, editor.Database).Rect(c0, r0, c1, r1).ToList() : null;
        var findings = TileMapValidator.CheckMap(map, editor.Database, region, TileMapValidator.DefaultVanillaTileMap(paths));
        return new JsonObject
        {
            ["tile_map"] = editor.TileMapPath, ["area"] = region is null ? "whole map" : a.Option("--rect"),
            ["errors"] = findings.Count(f => f.Severity == TileMapFinding.Error),
            ["warnings"] = findings.Count(f => f.Severity == TileMapFinding.Warning),
            ["findings"] = Findings(findings, true),
            ["note"] = "validate-tilemap checks the kit inputs around the tile map too",
        };
    }

    private static JsonNode Preview(TileMapEditor editor, ProjectPaths paths, Args a)
    {
        var map = editor.Load();
        int c0, r0, c1, r1;
        if (a.Ints("--rect") is [var ac, var ar, var bc, var br]) (c0, r0, c1, r1) = (ac, ar, bc, br);
        else if (a.Ints("--center") is [var cc, var cr])
        {
            var half = int.Parse(a.Option("--size") ?? "30") / 2;
            (c0, r0, c1, r1) = (cc - half, cr - half, cc + half, cr + half);
        }
        else throw new ArgumentException("--rect c0,r0,c1,r1 or --center c,r [--size n]");
        IEnumerable<(int, int)>? edited = a.Flag("--edits") ? editor.EditedHexes(int.Parse(a.Option("--since") ?? "0")) : null;
        IEnumerable<TileMapPreview.Mark>? marks = null;
        if (a.Flag("--issues"))
        {
            var region = new TileMapOps(map, editor.Database).Rect(c0, r0, c1, r1).ToList();
            marks = TileMapValidator.CheckMap(map, editor.Database, region, TileMapValidator.DefaultVanillaTileMap(paths))
                .Where(f => f.Severity != TileMapFinding.Info)
                .SelectMany(f => f.AllHexes.Select(h => new TileMapPreview.Mark(h[0], h[1], f.Severity == TileMapFinding.Error)));
        }
        var png = TileMapPreview.Render(map, new TileMapOps(map, editor.Database).SetOf, c0, r0, c1, r1,
            a.Option("--out") ?? PreviewPath(paths, $"{c0}_{r0}_{c1}_{r1}"), int.Parse(a.Option("--width") ?? "1024"), edited, marks);
        return new JsonObject { ["png"] = png, ["rect"] = new JsonArray(c0, r0, c1, r1) };
    }

    private static string PreviewPath(ProjectPaths paths, string what) =>
        Path.Combine(paths.OutputRoot, "previews", "tiles", $"{paths.MapName}_{what}_{DateTime.Now:HHmmss_fff}.png");

    private static JsonNode Holes(TileMapEditor editor, ProjectPaths paths, Args a)
    {
        var listPath = a.Option("--tile-list") ?? Path.Combine(paths.AkWorkingDir, "terrain", "campaigns", paths.MapName, "tile_list.bin");
        if (!File.Exists(listPath)) throw new FileNotFoundException("tile_list.bin not found (run BOB Terrain / Tilemap, or pass --tile-list)", listPath);
        var edited = editor.EditedHexes(int.Parse(a.Option("--since") ?? "0"));
        var report = TileHoles.Check(TileList.Read(listPath), editor.Database, edited);
        var limit = int.Parse(a.Option("--limit") ?? "40");
        var tileMapTime = File.Exists(editor.TileMapPath) ? File.GetLastWriteTime(editor.TileMapPath) : DateTime.MinValue;
        var o = new JsonObject
        {
            ["tile_list"] = listPath, ["cells"] = new JsonArray(report.Width, report.Height), ["records"] = report.Records,
            ["unknown_tile_paths"] = new JsonArray(report.UnknownPaths.Take(20).Select(p => (JsonNode)p).ToArray()),
            ["uncovered_cells"] = report.UncoveredCells,
            ["clusters"] = new JsonObject(report.Clusters.GroupBy(c => c.Kind).Select(g => KeyValuePair.Create(g.Key, (JsonNode?)g.Count()))),
            ["clusters_in_edited_hexes"] = report.Clusters.Count(c => c.Edited),
            ["largest"] = new JsonArray(report.Clusters.Take(limit).Select(c => (JsonNode)new JsonObject
            {
                ["cells"] = c.Cells, ["kind"] = c.Kind, ["hex"] = new JsonArray(c.Col, c.Row), ["edited"] = c.Edited,
                ["hexes"] = new JsonArray(c.Hexes.Take(12).Select(h => (JsonNode)new JsonArray(h[0], h[1])).ToArray()),
            }).ToArray()),
            ["note"] = "settlement holes are not separated here (research/main190/tile_holes.py does that with map.hex)",
        };
        if (File.GetLastWriteTime(listPath) < tileMapTime)
            o["warning"] = "tile_list.bin is older than tile_map.png: run BOB Terrain / Tilemap first";
        return o;
    }

    /// <summary>BOB Tilemap simulation of the current tile map: where tiles would be missing, edited hexes first.</summary>
    private static JsonNode Simulate(TileMapEditor editor, Args a)
    {
        var r = editor.Simulate(sinceSeq: int.Parse(a.Option("--since") ?? "0"));
        var limit = int.Parse(a.Option("--limit") ?? "60");
        var inEdited = r.InEdited.Select(h => (h[0], h[1])).ToHashSet();
        return new JsonObject
        {
            ["tile_map"] = editor.TileMapPath, ["seconds"] = Math.Round(r.Elapsed.TotalSeconds, 1),
            ["placed"] = r.Summary.Placed,
            ["placed_per_pass"] = new JsonObject(r.Summary.PlacedPerPass.Select(p => KeyValuePair.Create(p.Key, (JsonNode?)p.Value))),
            ["no_tile_points"] = r.NoTilePoints, ["no_tile_hexes"] = r.NoTileHexes.Count,
            ["no_tile_hexes_in_edits"] = r.InEdited.Count,
            ["edited"] = new JsonArray(r.InEdited.Take(limit).Select(h => (JsonNode)new JsonArray(h[0], h[1])).ToArray()),
            ["other"] = new JsonArray(r.NoTileHexes.Where(h => !inEdited.Contains((h[0], h[1]))).Take(limit)
                .Select(h => (JsonNode)new JsonArray(h[0], h[1])).ToArray()),
            ["note"] = "port of BOB's tile matching (TileMatchSimulator): main190 matched all 54 of BOB's holes (+4 extra). " +
                       "Hexes listed get no tile = see-through holes in game",
        };
    }

    private static JsonNode Undone(List<TerryClone.Core.Editing.FileJournal.HistoryEntry> undone) => new JsonObject
    {
        ["undone"] = new JsonArray(undone.Select(h => (JsonNode)new JsonObject { ["seq"] = h.Seq, ["label"] = h.Label }).ToArray()),
    };

    private static JsonNode History(TileMapEditor editor)
    {
        var ops = editor.Ops().ToDictionary(r => r.Seq);
        return new JsonObject
        {
            ["tile_map"] = editor.TileMapPath, ["journal"] = editor.Journal.Dir,
            ["edits"] = new JsonArray(editor.Journal.History().Select(h => (JsonNode)new JsonObject
            {
                ["seq"] = h.Seq, ["time"] = h.Time.ToString("s", CultureInfo.InvariantCulture), ["label"] = h.Label,
                ["hexes"] = ops.TryGetValue(h.Seq, out var r) ? r.Hexes?.Count ?? 0 : 0,
                ["ops"] = ops.TryGetValue(h.Seq, out r) ? r.Ops.Count : 0,
            }).ToArray()),
            ["checkpoints"] = new JsonObject(editor.Journal.Checkpoints().Select(c => KeyValuePair.Create(c.Key, (JsonNode?)c.Value))),
        };
    }

    /// <summary>"--name value" options, "--flag" switches and positional arguments.</summary>
    private sealed class Args(IEnumerable<string> raw)
    {
        private static readonly string[] Flags = ["--force", "--dry-run", "--allow-warnings", "--preview", "--edits", "--issues"];
        private readonly List<string> _a = raw.ToList();

        public string? Option(string name)
        {
            var i = _a.FindIndex(s => s.Equals(name, StringComparison.OrdinalIgnoreCase));
            if (i < 0) return null;
            return i + 1 < _a.Count ? _a[i + 1] : throw new ArgumentException($"{name} needs a value");
        }

        public bool Flag(string name) => _a.Contains(name, StringComparer.OrdinalIgnoreCase);

        public double[]? Doubles(string name) =>
            Option(name)?.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
                .Select(v => double.Parse(v, CultureInfo.InvariantCulture)).ToArray();

        public int[]? Ints(string name) =>
            Option(name)?.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
                .Select(v => int.Parse(v, CultureInfo.InvariantCulture)).ToArray();

        public string Positional(int index, string what)
        {
            var positional = new List<string>();
            for (var i = 0; i < _a.Count; i++)
            {
                if (!_a[i].StartsWith("--", StringComparison.Ordinal)) { positional.Add(_a[i]); continue; }
                if (!Flags.Contains(_a[i], StringComparer.OrdinalIgnoreCase)) i++;
            }
            return index < positional.Count ? positional[index] : throw new ArgumentException($"missing {what}");
        }
    }
}
