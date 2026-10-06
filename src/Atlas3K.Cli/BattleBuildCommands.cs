using Atlas3K.Core;
using Atlas3K.Core.Battle.Build;

/// <summary>
/// build-battle &lt;kit root&gt; &lt;map id&gt; [--out dir] [--only step,...] [--compare] [--tile id]: the native battle-map
/// build (BOB's battle export without BOB) into &lt;out&gt;/terrain/battles/&lt;id&gt; and terrain/tiles/battle/... (default
/// output/battle_native/&lt;id&gt;). --compare byte-compares every written file with BOB's working_data copy.
/// battle-steps lists the steps in run order.
/// </summary>
static class BattleBuildCommands
{
    public static readonly HashSet<string> Names = ["build-battle", "battle-steps"];

    public static int Run(ProjectPaths paths, string command, string[] a)
    {
        if (command == "battle-steps")
        {
            foreach (var s in BattleMapBuild.Steps()) Console.WriteLine(s.Name);
            return 0;
        }
        var pos = a.Where((v, i) => !v.StartsWith("--") && (i == 0 || a[i - 1] is not ("--out" or "--only" or "--tile"))).ToList();
        if (pos.Count < 2) { Console.Error.WriteLine("usage: build-battle <kit root> <map id> [--out dir] [--only a,b] [--compare] [--tile id]"); return 2; }
        var outRoot = Option(a, "--out") ?? Path.Combine("output", "battle_native", pos[1]);
        var ctx = new BattleBuildContext(pos[0], pos[1], outRoot) { TileId = Option(a, "--tile") ?? "" };
        var only = Option(a, "--only")?.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        var failed = BattleMapBuild.Run(ctx, Console.WriteLine, only);
        var mismatches = a.Contains("--compare") ? Compare(ctx) : 0;
        return failed.Count > 0 || mismatches > 0 ? 1 : 0;
    }

    /// <summary>Byte-compares each native output file with BOB's copy; prints one line per file.</summary>
    static int Compare(BattleBuildContext ctx)
    {
        var bad = 0;
        foreach (var (outDir, bobDir) in new[] { (ctx.OutMapDir, ctx.BobMapDir), (ctx.OutTileDir, ctx.BobTileDir), (ctx.OutTileDbDir, ctx.BobTileDbDir) })
        {
            if (!Directory.Exists(outDir)) continue;
            foreach (var f in Directory.EnumerateFiles(outDir).OrderBy(f => f, StringComparer.OrdinalIgnoreCase))
            {
                var name = Path.GetFileName(f);
                var bob = Path.Combine(bobDir, name);
                if (!File.Exists(bob)) { Console.WriteLine($"  ?  {name}: no BOB copy"); continue; }
                var x = File.ReadAllBytes(f);
                var y = File.ReadAllBytes(bob);
                var same = x.AsSpan().SequenceEqual(y);
                if (!same) bad++;
                var first = same ? -1 : FirstDiff(x, y);
                Console.WriteLine(same ? $"  =  {name} ({x.Length} bytes)" : $"  X  {name}: {x.Length} vs BOB {y.Length} bytes, first diff at {first}, {DiffCount(x, y)} bytes differ");
            }
        }
        return bad;
    }

    static int FirstDiff(byte[] x, byte[] y)
    {
        var n = Math.Min(x.Length, y.Length);
        for (var i = 0; i < n; i++) if (x[i] != y[i]) return i;
        return n;
    }

    static int DiffCount(byte[] x, byte[] y)
    {
        var n = Math.Min(x.Length, y.Length);
        var c = Math.Abs(x.Length - y.Length);
        for (var i = 0; i < n; i++) if (x[i] != y[i]) c++;
        return c;
    }

    static string? Option(string[] a, string name)
    {
        var i = Array.IndexOf(a, name);
        return i >= 0 && i + 1 < a.Length ? a[i + 1] : null;
    }
}
