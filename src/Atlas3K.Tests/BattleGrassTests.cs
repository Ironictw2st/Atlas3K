using Atlas3K.Core.Battle.Build;
using Atlas3K.Core.Battle.Build.Bmd;
using Xunit;

namespace Atlas3K.Tests;

/// <summary>The native battle grass lists (<see cref="GrassListStep"/>) against BOB's own &lt;climate&gt;.grass_list.bin in
/// the battle-parity corpus: byte-identical, and no file where BOB wrote none.</summary>
public class BattleGrassTests
{
    [Theory]
    [MemberData(nameof(BattleTileMeshTests.Projects), MemberType = typeof(BattleTileMeshTests))]
    public void MatchesBob(string id)
    {
        if (id.Length == 0) return;   // corpus not available
        var project = Path.Combine(BattleBmdTests.Corpus, id);
        var outRoot = Path.Combine(Path.GetTempPath(), "atlas3k_grass_" + id);
        try
        {
            var ctx = new BattleBuildContext(TestKits.Vanilla, id, outRoot)
            {
                SourceTileDir = Path.Combine(project, "src", "tile"), SourceMapDir = Path.Combine(project, "src", "map"),
            };
            ctx.EnsureOutDirs();
            new GrassListStep().Run(ctx, _ => { });
            var bob = Directory.EnumerateFiles(Path.Combine(project, "bob_run1", "tile"), "*.grass_list.bin").Select(Path.GetFileName).Order().ToList();
            var native = Directory.EnumerateFiles(ctx.OutTileDir, "*.grass_list.bin").Select(Path.GetFileName).Order().ToList();
            Assert.Equal(bob, native);
            foreach (var f in bob)
                Assert.True(File.ReadAllBytes(Path.Combine(project, "bob_run1", "tile", f!)).AsSpan()
                    .SequenceEqual(File.ReadAllBytes(Path.Combine(ctx.OutTileDir, f!))), $"{id} {f} differs");
        }
        finally
        {
            if (Directory.Exists(outRoot)) Directory.Delete(outRoot, true);
        }
    }

    [Fact]
    public void Xoroshiro_matches_the_inlined_generator()
    {
        // seed 0 takes the generator's constants; the first draw after the discarded step
        var a = new Xoroshiro128Plus(0);
        var b = new Xoroshiro128Plus(0);
        Assert.Equal(a.Next(), b.Next());
        var r = new Xoroshiro128Plus(541807483);
        // reference values from research/battle_build/grass_proto.py Xoro(541807483)
        Assert.Equal(0xbd800000001025a9UL, r.Next());
    }
}
