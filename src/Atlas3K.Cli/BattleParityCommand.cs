using System.Text.Json;
using Atlas3K.Core;

/// <summary>
/// battle-parity: compares a native battle-map build with the BOB ground-truth corpus
/// (Z:\Claude\BattleMaps\out\battle_parity, made by research/battle_build). Per file: identical, masked-identical
/// (only bytes that differ between BOB runs differ), identical to another BOB run (record-order variants), differs
/// (first offset), or missing.
/// </summary>
internal static class BattleParityCommand
{
    public static readonly HashSet<string> Names = ["battle-parity"];

    private const string Usage =
        "battle-parity <corpus project dir | corpus root> <native out dir> [--run bob_run1] [--json]\n" +
        "  native out dir: the corpus snapshot layout (map/, tile/, tile_db/) or a working_data-like tree\n" +
        "  (terrain/battles/<id>, terrain/tiles/battle/_assembly_kit/<id>, .../_tile_database/TILES).\n" +
        "  With a corpus root, every project folder is compared against <native out dir>/<id>.";

    // Terry writes these when the project is saved; BOB only reads them.
    private static readonly HashSet<string> Inputs = ["map/rules.bob", "tile/rules.bob"];

    public static int Run(ProjectPaths paths, string command, string[] a)
    {
        var pos = a.Where((x, i) => !x.StartsWith("--") && (i == 0 || a[i - 1] != "--run")).ToList();
        if (pos.Count < 2) { Console.Error.WriteLine(Usage); return 2; }
        var run = Opt(a, "--run") ?? "bob_run1";
        var json = a.Contains("--json");
        var corpus = Path.GetFullPath(pos[0]);
        var native = Path.GetFullPath(pos[1]);
        List<(string Proj, string Out)> projects = Directory.Exists(Path.Combine(corpus, run))
            ? [(corpus, native)]
            : Directory.GetDirectories(corpus).Where(d => Directory.Exists(Path.Combine(d, run)))
                .Select(d => (d, Path.Combine(native, Path.GetFileName(d)))).ToList();
        if (projects.Count == 0) { Console.Error.WriteLine($"no {run} snapshot under {corpus}"); return 2; }

        var all = new List<object>();
        var bad = 0;
        foreach (var (proj, outDir) in projects)
        {
            var rows = Compare(proj, outDir, run);
            bad += rows.Count(r => r.Verdict is "differs" or "missing");
            if (json) { all.Add(new { project = Path.GetFileName(proj), files = rows }); continue; }
            Console.WriteLine($"== {Path.GetFileName(proj)}  (reference {run}, native {outDir})");
            foreach (var r in rows)
                Console.WriteLine($"  {r.Verdict,-16} {r.File}{(r.Detail is null ? "" : "  " + r.Detail)}");
            var n = rows.Count(r => r.Verdict != "input");
            Console.WriteLine($"  -> {rows.Count(r => r.Verdict.StartsWith("identical") || r.Verdict == "masked-identical")}/{n} match");
        }
        if (json) Console.WriteLine(JsonSerializer.Serialize(all, new JsonSerializerOptions { WriteIndented = true }));
        return bad == 0 ? 0 : 1;
    }

    public sealed record Row(string File, string Verdict, string? Detail);

    public static List<Row> Compare(string proj, string native, string run)
    {
        var id = Path.GetFileName(proj.TrimEnd('\\', '/'));
        var refDir = Path.Combine(proj, run);
        var variants = Directory.GetDirectories(proj, "bob_run*").Where(d => !PathEq(d, refDir)).OrderBy(d => d).ToList();
        var masks = LoadMasks(Path.Combine(proj, "masks.json"));
        var rows = new List<Row>();
        foreach (var refFile in Directory.EnumerateFiles(refDir, "*", SearchOption.AllDirectories).OrderBy(f => f, StringComparer.Ordinal))
        {
            var rel = Path.GetRelativePath(refDir, refFile).Replace('\\', '/');
            if (Inputs.Contains(rel)) { rows.Add(new(rel, "input", "written by Terry, not BOB")); continue; }
            var mine = Locate(native, id, rel);
            if (mine is null) { rows.Add(new(rel, "missing", null)); continue; }
            var want = File.ReadAllBytes(refFile);
            var got = File.ReadAllBytes(mine);
            if (want.AsSpan().SequenceEqual(got)) { rows.Add(new(rel, "identical", null)); continue; }
            var ranges = masks.GetValueOrDefault(rel, []);
            if (ranges.Count > 0 && want.Length == got.Length && FirstDiff(want, got, ranges) < 0)
            { rows.Add(new(rel, "masked-identical", $"{ranges.Sum(r => r[1] - r[0])} masked bytes")); continue; }
            var other = variants.FirstOrDefault(v =>
            {
                var f = Path.Combine(v, rel.Replace('/', Path.DirectorySeparatorChar));
                if (!File.Exists(f)) return false;
                var b = File.ReadAllBytes(f);
                return b.Length == got.Length && FirstDiff(b, got, ranges) < 0;
            });
            if (other is not null) { rows.Add(new(rel, "identical-variant", $"matches {Path.GetFileName(other)} (BOB record order varies)")); continue; }
            var at = FirstDiff(want, got, ranges);
            rows.Add(new(rel, "differs", $"first offset {at} (0x{at:X}), sizes bob {want.Length} native {got.Length}"));
        }
        return rows;
    }

    /// <summary>The native file for a corpus-relative path, in the snapshot layout or a working_data-like tree.</summary>
    private static string? Locate(string native, string id, string rel)
    {
        var direct = Path.Combine(native, rel.Replace('/', Path.DirectorySeparatorChar));
        if (File.Exists(direct)) return direct;
        var slash = rel.IndexOf('/');
        var (part, name) = (rel[..slash], rel[(slash + 1)..].Replace('/', Path.DirectorySeparatorChar));
        string[] roots = part switch
        {
            "map" => [Path.Combine("terrain", "battles", id)],
            "tile" => [Path.Combine("terrain", "tiles", "battle", "_assembly_kit", id)],
            "tile_db" => [Path.Combine("terrain", "tiles", "battle", "_tile_database", "TILES")],
            _ => [],
        };
        foreach (var r in roots)
            foreach (var baseDir in new[] { native, Path.Combine(native, "working_data") })
            {
                var f = Path.Combine(baseDir, r, name);
                if (File.Exists(f)) return f;
            }
        return null;
    }

    /// <summary>First differing offset outside the masked [start, end) ranges, or −1 (length mismatch = min length).</summary>
    private static long FirstDiff(byte[] a, byte[] b, List<long[]> masked)
    {
        var n = Math.Min(a.Length, b.Length);
        for (var i = 0; i < n; i++)
        {
            if (a[i] == b[i]) continue;
            if (masked.Any(r => i >= r[0] && i < r[1])) continue;
            return i;
        }
        return a.Length == b.Length ? -1 : n;
    }

    private static Dictionary<string, List<long[]>> LoadMasks(string path)
    {
        var d = new Dictionary<string, List<long[]>>();
        if (!File.Exists(path)) return d;
        using var doc = JsonDocument.Parse(File.ReadAllText(path));
        foreach (var p in doc.RootElement.EnumerateObject())
        {
            if (p.Name.StartsWith('_')) continue;
            d[p.Name] = p.Value.EnumerateArray().Select(r => new[] { r[0].GetInt64(), r[1].GetInt64() }).ToList();
        }
        return d;
    }

    private static bool PathEq(string a, string b) =>
        string.Equals(Path.GetFullPath(a).TrimEnd('\\'), Path.GetFullPath(b).TrimEnd('\\'), StringComparison.OrdinalIgnoreCase);

    private static string? Opt(string[] a, string name)
    {
        var i = Array.IndexOf(a, name);
        return i >= 0 && i + 1 < a.Length ? a[i + 1] : null;
    }
}
