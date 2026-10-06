using Atlas3K.Core.Battle.Build;
using Atlas3K.Core.Battle.Build.Bmd;
using Atlas3K.Formats.Battle;
using Xunit;

namespace Atlas3K.Tests;

/// <summary>The native bmd_data.bin against BOB's on every battle-parity corpus project that has one (siege walls and AI
/// nodes, forest ambush hints, capture locations, deployment). BOB's grass and tree lists are copied in first (those
/// steps are other workers'), and the CAPTURE_LOCATION_LISTs are compared as a set: BOB writes them in a random
/// order (pointer-keyed map; 3 runs, 3 orders on 5a2e0002).</summary>
public class BattleBmdDataTests
{
    public static IEnumerable<object[]> Projects() =>
        Directory.Exists(BattleBmdTests.Corpus)
            ? Directory.EnumerateDirectories(BattleBmdTests.Corpus)
                .Where(d => File.Exists(Path.Combine(d, "bob_run1", "tile", "bmd_data.bin")) && Directory.Exists(Path.Combine(d, "src", "tile")))
                .Select(d => new object[] { Path.GetFileName(d) })
            : [new object[] { "" }];

    [Theory]
    [MemberData(nameof(Projects))]
    public void MatchesABobRun(string id)
    {
        if (id.Length == 0) return;   // corpus not available
        var project = Path.Combine(BattleBmdTests.Corpus, id);
        var outRoot = Path.Combine(Path.GetTempPath(), "atlas3k_bmd_data_" + id);
        try
        {
            var ctx = new BattleBuildContext(TestKits.Vanilla, id, outRoot)
            {
                SourceTileDir = Path.Combine(project, "src", "tile"), SourceMapDir = Path.Combine(project, "src", "map"),
            };
            Directory.CreateDirectory(ctx.OutTileDir);
            foreach (var f in Directory.EnumerateFiles(Path.Combine(project, "bob_run1", "tile"))
                         .Where(f => f.EndsWith(".grass_list.bin") || f.EndsWith(".tree_list.bin")))
                File.Copy(f, Path.Combine(ctx.OutTileDir, Path.GetFileName(f)));
            new BattleBmdDataStep().Run(ctx, _ => { });
            var native = Canonical(File.ReadAllBytes(Path.Combine(ctx.OutTileDir, "bmd_data.bin")));
            var runs = Directory.GetDirectories(project, "bob_run*").Select(r => Path.Combine(r, "tile", "bmd_data.bin")).Where(File.Exists).ToList();
            Assert.Contains(runs, r => Canonical(File.ReadAllBytes(r)).AsSpan().SequenceEqual(native));
        }
        finally
        {
            if (Directory.Exists(outRoot)) Directory.Delete(outRoot, true);
        }
    }

    /// <summary>The bmd with its CAPTURE_LOCATION_LISTs sorted by their meta tag flags.</summary>
    private static byte[] Canonical(byte[] bmd)
    {
        var root = BattleBmd.Read(bmd);
        var set = root.Child("CAPTURE_LOCATION_SET").Child("CAPTURE_LOCATION_SET");
        var lists = set.Children.OrderBy(l => Convert.ToUInt64(l.Child("meta_tags").Get("flags"))).ToList();
        set.Children.Clear();
        set.Children.AddRange(lists);
        return BattleBmd.Write(root);
    }

    [Fact]
    public void ForestClipKeepsInsidePointsAndCutsTheBoundary()
    {
        List<(float X, float Y)> square = [(-10, -10), (-10, 10), (10, 10), (10, -10)];
        var clipped = ForestHints.Clip(square, (0, 0, 100, 100));
        Assert.Equal(100f, ForestHints.Area(clipped));
        Assert.All(clipped, p => Assert.True(p.X is >= 0 and <= 10 && p.Y is >= 0 and <= 10));
    }
}
