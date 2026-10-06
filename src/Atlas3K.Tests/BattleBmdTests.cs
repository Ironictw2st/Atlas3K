using Atlas3K.Formats.Battle;
using Xunit;

namespace Atlas3K.Tests;

/// <summary>The battle bmd codec against BOB's own files (the battle-parity corpus of the four kit battle maps).</summary>
public class BattleBmdTests
{
    internal const string Corpus = @"Z:\Claude\BattleMaps\out\battle_parity";

    public static IEnumerable<string> CorpusBmds() =>
        Directory.Exists(Corpus)
            ? Directory.EnumerateDirectories(Corpus).Where(d => Directory.Exists(Path.Combine(d, "bob_run1", "tile")))
                .SelectMany(d => Directory.EnumerateFiles(Path.Combine(d, "bob_run1", "tile"), "*bmd*.bin"))
            : [];

    [Fact]
    public void RoundTripsBinAndXml()
    {
        var files = CorpusBmds().ToList();
        if (files.Count == 0) return;   // data not available
        foreach (var f in files)
        {
            var data = File.ReadAllBytes(f);
            var tree = BattleBmd.Read(data);
            Assert.True(data.AsSpan().SequenceEqual(BattleBmd.Write(tree)), $"bin differs: {f}");
            var xml = Path.ChangeExtension(f, ".xml");
            if (File.Exists(xml)) Assert.Equal(File.ReadAllText(xml), BattleBmd.ToXml(tree));
        }
    }

    [Fact]
    public void FormatsFloatsLikeBob()
    {
        Assert.Equal("-966818018806904626816175490648", BattleBmd.Format("f32", -9.668180188069046e+35f));
        Assert.Equal("-0.000000", BattleBmd.Format("f32", -5.9e-17f));
        Assert.Equal("0.174533", BattleBmd.Format("f32", 0.17453292f));
        Assert.Equal("1428.039063", BattleBmd.Format("f32", 1428.0390625f));   // exact tie: away from zero (MSVC)
        Assert.Equal("-0.000000", BattleBmd.Format("f32", -0f));
    }
}

/// <summary>Native bmd_nogo_data terrain outlines against BOB's (corpus tiles with steep terrain and flat ones).</summary>
public class BattleNogoTests
{
    [Fact]
    public void NogoOutlinesMatchBob()
    {
        if (!Directory.Exists(BattleBmdTests.Corpus)) return;   // data not available
        foreach (var dir in Directory.EnumerateDirectories(BattleBmdTests.Corpus).Where(d => Directory.Exists(Path.Combine(d, "src", "tile"))))
        {
            var terry = Directory.EnumerateFiles(Path.Combine(dir, "src", "tile"), "*.terry").SingleOrDefault();
            var bob = Path.Combine(dir, "bob_run1", "tile", "bmd_nogo_data.bin");
            if (terry is null || !File.Exists(bob)) continue;
            var project = Atlas3K.Core.Battle.Build.Meshes.TerryTileProject.Load(terry);
            var field = project.HeightField(out var w, out var h);
            var ours = Atlas3K.Core.Battle.Build.Bmd.NogoOutlines.Compute(field, w, h, project.TilesWide * 256f / (w - 1));
            var theirs = BattleBmd.Read(File.ReadAllBytes(bob)).Child("TERRAIN_OUTLINES").Children
                .Select(o => o.Child("OUTLINE").Children.Select(p => ((float)p.Get("x"), (float)p.Get("y"))).ToList()).ToList();
            Assert.Equal(theirs.Count, ours.Count);
            for (var k = 0; k < ours.Count; k++) Assert.Equal(theirs[k], ours[k]);
        }
    }
}
