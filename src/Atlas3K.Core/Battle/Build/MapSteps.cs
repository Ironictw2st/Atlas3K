using System.Xml.Linq;
using Atlas3K.Core.Exporters;
using Atlas3K.Formats.Battle;
using Atlas3K.Formats.Maps;

namespace Atlas3K.Core.Battle.Build;

/// <summary>
/// lf_height_map / lf_sea_height_map (.compressed_map + .dds) from raw_data/terrain/battles/&lt;id&gt;/lf_heights.tif and
/// lf_sea_heights.tif. Same rule as the campaign export (<see cref="CompiledTerrainExporter.Normalise"/>): values
/// stretched to the source's own min..max, header f[1] = lo/65535, f[4] = hi/65535; a constant source is all zeros.
/// </summary>
[BattleStepOrder(110)]
public sealed class BattleLfStep : IBattleBuildStep
{
    public string Name => "lf";

    public void Run(BattleBuildContext ctx, Action<string> log)
    {
        foreach (var (src, name) in new[] { ("lf_heights.tif", "lf_height_map"), ("lf_sea_heights.tif", "lf_sea_height_map") })
        {
            var source = TiffMap.ReadGray16(Path.Combine(ctx.SourceMapDir, src));
            var (values, header) = Normalise(source);
            CompressedMap.Write(Path.Combine(ctx.OutMapDir, name + ".compressed_map"), values, header);
            TerrainDds.WriteL16(Path.Combine(ctx.OutMapDir, name + ".dds"), values);
            if (name == "lf_height_map") ctx.Shared["lf_height"] = values;
        }
    }

    /// <summary>BOB's normalisation, float32 throughout: h = s / 65535, lo/hi = min/max of h,
    /// v = trunc((h − lo) · (1 / (hi − lo)) · 65535). Multiplying by the reciprocal is what makes it exact (dividing by
    /// hi − lo is off by one on ~0.01% of pixels). Header f[1] = lo, f[4] = hi.</summary>
    public static (Raster<ushort> Values, float[] Header) Normalise(Raster<ushort> source)
    {
        var h = new float[source.Data.Length];
        float lo = float.MaxValue, hi = float.MinValue;
        for (var i = 0; i < h.Length; i++)
        {
            h[i] = source.Data[i] / 65535f;
            if (h[i] < lo) lo = h[i];
            if (h[i] > hi) hi = h[i];
        }
        var result = new Raster<ushort>(source.Width, source.Height);
        if (hi > lo)
        {
            var inv = 1f / (hi - lo);
            for (var i = 0; i < h.Length; i++)
            {
                var t = (h[i] - lo) * inv;
                result.Data[i] = (ushort)(t * 65535f);
            }
        }
        else lo = hi = 0;
        return (result, [0, lo, 0, 0, hi, 0]);
    }
}

/// <summary>
/// climate_map.cm from raw_data/terrain/battles/&lt;id&gt;/climate_map.png: each pixel's exact RGB matched against the
/// battle tile database's climates (_settings.bin, in order: default, arid, arid_fertile, cold, ...); the index of the
/// match, 0 when none matches. Header f[4] = 65535.
/// </summary>
[BattleStepOrder(120)]
public sealed class BattleClimateStep : IBattleBuildStep
{
    public string Name => "climate";

    public const string SettingsPath = "terrain/tiles/battle/_tile_database/_settings.bin";

    public void Run(BattleBuildContext ctx, Action<string> log)
    {
        var settings = ctx.ReadVfs(SettingsPath) ?? throw new FileNotFoundException($"{SettingsPath} not in the kit or the packs");
        var climates = BattleTileDatabase.ReadClimates(settings);
        var rgba = PngMap.Read(Path.Combine(ctx.SourceMapDir, "climate_map.png"));
        var cm = new Raster<ushort>(rgba.Width, rgba.Height);
        var unknown = 0;
        for (var y = 0; y < rgba.Height; y++)
        for (var x = 0; x < rgba.Width; x++)
        {
            var p = rgba[x, y]; // 0xAABBGGRR
            byte r = (byte)p, g = (byte)(p >> 8), b = (byte)(p >> 16);
            var match = climates.FindIndex(c => c.R == r && c.G == g && c.B == b);
            if (match < 0) unknown++;
            cm[x, y] = (ushort)Math.Max(0, match);
        }
        if (unknown > 0) log($"climate: {unknown:N0} pixels match no climate colour (written as 0)");
        CompressedMap.Write(Path.Combine(ctx.OutMapDir, "climate_map.cm"), cm, [0, 0, 0, 0, 65535, 0]);
    }
}

/// <summary>
/// map_info.xml, as ACTION_TERRY_TILE::save_user_created_map_data (bob_tile 0x180009b20) writes it: a QDomDocument
/// saved with indent 4 (LF line ends), from the tile project's &lt;user_created_map&gt; and environment. An empty
/// display name falls back to the .terry file's base name. Text is escaped as QDom does (&amp; &lt; &gt; only).
/// </summary>
[BattleStepOrder(130)]
public sealed class BattleMapInfoStep : IBattleBuildStep
{
    public string Name => "map_info";

    public void Run(BattleBuildContext ctx, Action<string> log)
    {
        var doc = XDocument.Load(ctx.TerryFile);
        var data = doc.Descendants("pc").First(e => (string?)e.Attribute("type") == "QTU::ProjectTileWithVista").Element("data")!;
        var user = data.Element("user_created_map") ?? throw new InvalidDataException("the tile project has no <user_created_map> (not a battle map project)");
        string A(XElement e, string n) => Escape((string?)e.Attribute(n) ?? "");
        var name = A(user, "display_name");
        if (name.Length == 0) name = Escape(Path.GetFileNameWithoutExtension(ctx.TerryFile).Split('.')[0]);
        var text = "<map_info>\n" +
                   $"    <display_name>{name}</display_name>\n" +
                   $"    <description>{A(user, "description")}</description>\n" +
                   $"    <author>{A(user, "author")}</author>\n" +
                   $"    <team_size_1>{A(user, "max_players_1")}</team_size_1>\n" +
                   $"    <team_size_2>{A(user, "max_players_2")}</team_size_2>\n" +
                   $"    <environment>{A(data, "env")}</environment>\n" +
                   $"    <battle_type>{A(user, "battle_type")}</battle_type>\n" +
                   "</map_info>\n";
        File.WriteAllBytes(Path.Combine(ctx.OutMapDir, "map_info.xml"), System.Text.Encoding.UTF8.GetBytes(text));
    }

    /// <summary>QDom text-node escaping: &amp;, &lt;, &gt; (quotes are only escaped in attributes).</summary>
    public static string Escape(string s) => s.Replace("&", "&amp;").Replace("<", "&lt;").Replace(">", "&gt;");
}

/// <summary>icon.tga: BOB keeps an icon already in the map's output folder, else copies the VFS file Terry/icon.tga
/// (the kit's working_data/Terry/icon.tga, the same 468x150 image for every map) — save_user_created_map_data.</summary>
[BattleStepOrder(140)]
public sealed class BattleIconStep : IBattleBuildStep
{
    public string Name => "icon";

    public void Run(BattleBuildContext ctx, Action<string> log)
    {
        var path = Path.Combine(ctx.OutMapDir, "icon.tga");
        if (File.Exists(path)) { log("icon: kept the existing icon.tga"); return; }
        var icon = ctx.ReadVfs("Terry/icon.tga") ?? throw new FileNotFoundException("Terry/icon.tga not in the kit's working_data or the packs");
        File.WriteAllBytes(path, icon);
    }
}
