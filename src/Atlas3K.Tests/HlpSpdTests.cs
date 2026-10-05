using Atlas3K.Formats.Esf;

namespace Atlas3K.Tests;

/// <summary>hlp_data.esf / spd_data.esf (campaign AI pathfinding data): format round trip and native generation.</summary>
public class HlpSpdTests
{
    private const string KitMaps = @"C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\assembly_kit\working_data\campaign_maps";
    private const string Extracted = @"Z:\Claude\TerryClone\output\hlp_spd";

    /// <summary>Reference map folders that hold hlp_data.esf + spd_data.esf (kit copy of dlc07, plus extracted pack copies).</summary>
    public static IEnumerable<string> MapDirs()
    {
        var kit = Path.Combine(KitMaps, "3k_dlc07_main_map");
        if (File.Exists(Path.Combine(kit, "hlp_data.esf"))) yield return kit;
        if (!Directory.Exists(Extracted)) yield break;
        foreach (var d in Directory.GetDirectories(Extracted, "*", SearchOption.AllDirectories))
            if (File.Exists(Path.Combine(d, "hlp_data.esf")) && d.Contains("campaign_maps")) yield return d;
    }

    [Fact]
    public void Hlp_RoundTripsByteIdentical()
    {
        foreach (var dir in MapDirs())
        {
            var original = File.ReadAllBytes(Path.Combine(dir, "hlp_data.esf"));
            Assert.Equal(original, HlpData.Read(original).ToBytes());
        }
    }

    [Fact]
    public void Spd_RoundTripsByteIdentical()
    {
        foreach (var dir in MapDirs())
        {
            var path = Path.Combine(dir, "spd_data.esf");
            if (!File.Exists(path)) continue;
            var original = File.ReadAllBytes(path);
            Assert.Equal(original, SpdData.Read(original).ToBytes());
        }
    }
}
