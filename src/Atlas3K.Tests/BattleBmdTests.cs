using Atlas3K.Formats.Battle;
using Xunit;

namespace Atlas3K.Tests;

/// <summary>The battle bmd codec against BOB's own files (the battle-parity corpus of the four kit battle maps).</summary>
public class BattleBmdTests
{
    internal const string Corpus = @"Z:\Claude\BattleMaps\out\battle_parity";

    public static IEnumerable<string> CorpusBmds() =>
        Directory.Exists(Corpus)
            ? Directory.EnumerateDirectories(Corpus).SelectMany(d => Directory.EnumerateFiles(Path.Combine(d, "bob_run1", "tile"), "*bmd*.bin"))
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
