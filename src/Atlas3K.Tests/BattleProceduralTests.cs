using Atlas3K.Core;
using Atlas3K.Core.Battle.Build;
using Atlas3K.Core.Battle.Build.Bmd;
using Atlas3K.Formats.Battle;
using Xunit;

namespace Atlas3K.Tests;

/// <summary>Native procedural vegetation (procedural bmds and tree lists) against BOB's on the battle-parity corpus.</summary>
public class BattleProceduralTests
{
    [Fact]
    public void ParsesFloatsLikeCalibs()
    {
        Assert.Equal(BitConverter.SingleToUInt32Bits(0.900000036f), BitConverter.SingleToUInt32Bits(ProceduralParameters.ParseFloat("0.9")));
        Assert.Equal(-5000f, ProceduralParameters.ParseFloat("-5000"));
        Assert.Equal(0f, ProceduralParameters.ParseFloat("1.0 "));   // trailing text: not parsed
        Assert.Equal((0.6000000238f, 0.7000000477f, 0.2000000030f), ProceduralParameters.Normalise(0.4f, ProceduralParameters.ParseFloat("0.9"), 0.1f));
    }

    [Fact]
    public void TreeListRotationByte()
    {
        Assert.Equal(79, BattleTreeList.RotationByte(112f * 3.14159274f * 0.00555555569f));
        Assert.Equal(0, BattleTreeList.RotationByte(0f));
    }

    [Fact]
    public void ProceduralFilesMatchBob()
    {
        var kit = TestKits.Vanilla;
        if (!Directory.Exists(BattleBmdTests.Corpus) || !Directory.Exists(kit)) return;   // data not available
        var checkedFiles = 0;
        foreach (var dir in Directory.EnumerateDirectories(BattleBmdTests.Corpus).Where(d => Directory.Exists(Path.Combine(d, "src", "tile"))
                     && Directory.Exists(Path.Combine(d, "bob_run1", "tile"))))
        {
            var id = Path.GetFileName(dir);
            var outRoot = Path.Combine(Path.GetTempPath(), "atlas3k_proc_" + id);
            var ctx = new BattleBuildContext(kit, id, outRoot)
            {
                SourceMapDir = Path.Combine(dir, "src", "map"), SourceTileDir = Path.Combine(dir, "src", "tile"),
            };
            ctx.EnsureOutDirs();
            new ProceduralVegetationStep().Run(ctx, _ => { });
            foreach (var f in Directory.EnumerateFiles(ctx.OutTileDir).Where(f => f.Contains("procedural_bmd") || f.Contains("tree_list")))
            {
                var bob = Path.Combine(dir, "bob_run1", "tile", Path.GetFileName(f));
                Assert.True(File.Exists(bob), $"{id}: BOB has no {Path.GetFileName(f)}");
                Assert.True(File.ReadAllBytes(f).AsSpan().SequenceEqual(File.ReadAllBytes(bob)), $"{id}: {Path.GetFileName(f)} differs");
                checkedFiles++;
            }
            Directory.Delete(outRoot, true);
        }
        Assert.True(checkedFiles > 0);
    }
}
