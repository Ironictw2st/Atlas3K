using System.Text.RegularExpressions;
using System.Xml.Linq;
using Atlas3K.Core.Battle.Build.Meshes;
using BitMiracle.LibTiff.Classic;

namespace Atlas3K.Core.Battle.Build;

/// <summary>The tile project's 8-channel blend TIF (Blend8 map, 1280×1280 for 8×8 at density 128), or null.</summary>
internal static class TileBlend
{
    public static (int W, int H, byte[] Data)? Read(string tileDir)
    {
        var tif = Directory.EnumerateFiles(tileDir, "*.blend.*.tif").FirstOrDefault();
        if (tif is null) return null;
        using var t = Tiff.Open(tif, "r") ?? throw new IOException($"Cannot open {tif}");
        var w = t.GetField(TiffTag.IMAGEWIDTH)[0].ToInt();
        var h = t.GetField(TiffTag.IMAGELENGTH)[0].ToInt();
        var spp = t.GetField(TiffTag.SAMPLESPERPIXEL)[0].ToInt();
        if (spp != 8) throw new InvalidDataException($"{tif}: {spp} samples per pixel, 8 expected");
        var data = new byte[w * h * 8];
        var row = new byte[t.ScanlineSize()];
        for (var y = 0; y < h; y++)
        {
            t.ReadScanline(row, y);
            Buffer.BlockCopy(row, 0, data, y * w * 8, w * 8);
        }
        return (w, h, data);
    }
}

/// <summary>
/// blend0.dds / blend1.dds (TOOLDATABUILDER::convert_blend_map): the blend channels the tile uses (channel 0 always,
/// in channel order, as in the rewritten tile database entry) packed four per texture, R G B A = used channel 0..3 into
/// blend0 and 4..7 into blend1, full 1280×1280, DXT5 with BOB's mip chain (<see cref="AmdCompress"/>). Written only
/// when the blend map has painted data (a non-zero weight in any channel).
/// </summary>
[BattleStepOrder(170)]
public sealed class BattleBlendStep : IBattleBuildStep
{
    public string Name => "blend";

    public void Run(BattleBuildContext ctx, Action<string> log)
    {
        var blend = TileBlend.Read(ctx.SourceTileDir);
        foreach (var f in new[] { "blend0.dds", "blend1.dds" })
        {
            var p = Path.Combine(ctx.OutTileDir, f);
            if (File.Exists(p)) File.Delete(p);
        }
        if (blend is not { } b || !b.Data.Any(v => v != 0)) { log("blend: no painted blend data, no blend0/1.dds"); return; }
        var used = BattleTileDbStep.UsedBlendChannels(ctx.SourceTileDir);
        var order = Enumerable.Range(0, 8).Where(c => used[c]).ToList();
        AmdCompress.Load(ctx.KitRoot);
        for (var tex = 0; tex < 2; tex++)
        {
            var bgra = new byte[b.W * b.H * 4];
            for (var i = 0; i < b.W * b.H; i++)
            {
                byte Ch(int k) => tex * 4 + k < order.Count ? b.Data[i * 8 + order[tex * 4 + k]] : (byte)0;
                bgra[i * 4] = Ch(2); bgra[i * 4 + 1] = Ch(1); bgra[i * 4 + 2] = Ch(0); bgra[i * 4 + 3] = Ch(3);
            }
            File.WriteAllBytes(Path.Combine(ctx.OutTileDir, $"blend{tex}.dds"), AmdCompress.WriteDds(bgra, b.W, b.H, AmdCompress.FormatDxt5, minMipShift: 1));
        }
    }
}

/// <summary>
/// normal.dds of the tile ("Process Terry tile (heightmap)"): the 3×3 Sobel of the full float Height TIF (edges
/// clamped), normal = normalise(gx/8, gy/8, 1/normal_strength) (the mesh normal rule), pixel B,G,R,A = 0,
/// (ny+1)·127.5, 255, (nx+1)·127.5 truncated, DXT5 via <see cref="AmdCompress"/>. Written with the blend textures
/// (projects with painted blend data).
/// </summary>
[BattleStepOrder(175)]
public sealed class BattleTileNormalStep : IBattleBuildStep
{
    public string Name => "tile_normal";

    public void Run(BattleBuildContext ctx, Action<string> log)
    {
        var path = Path.Combine(ctx.OutTileDir, "normal.dds");
        if (File.Exists(path)) File.Delete(path);
        if (TileBlend.Read(ctx.SourceTileDir) is not { } b || !b.Data.Any(v => v != 0)) return;
        var project = TerryTileProject.Load(ctx.TerryFile);
        if (project.HeightTif is null) return;
        var (w, h, v) = TerryTileProject.ReadFloatTif(project.HeightTif);
        var z = 1f / project.NormalStrength;
        float H(int x, int y) => v[Math.Clamp(y, 0, h - 1) * w + Math.Clamp(x, 0, w - 1)];
        var bgra = new byte[w * h * 4];
        for (var y = 0; y < h; y++)
            for (var x = 0; x < w; x++)
            {
                var gx = (H(x - 1, y - 1) - H(x + 1, y - 1) + 2f * (H(x - 1, y) - H(x + 1, y)) + (H(x - 1, y + 1) - H(x + 1, y + 1))) / 8f;
                var gy = (H(x - 1, y - 1) - H(x - 1, y + 1) + 2f * (H(x, y - 1) - H(x, y + 1)) + (H(x + 1, y - 1) - H(x + 1, y + 1))) / 8f;
                var inv = 1f / MathF.Sqrt(gx * gx + gy * gy + z * z);
                var o = (y * w + x) * 4;
                bgra[o] = 0;
                bgra[o + 1] = (byte)(int)((gy * inv + 1f) * 127.5f);
                bgra[o + 2] = 255;
                bgra[o + 3] = (byte)(int)((gx * inv + 1f) * 127.5f);
            }
        AmdCompress.Load(ctx.KitRoot);
        File.WriteAllBytes(path, AmdCompress.WriteDds(bgra, w, h, AmdCompress.FormatDxt5, minMipShift: 1));
    }
}

/// <summary>
/// ground_types.dds: per pixel the EMPIREUTILITY::GROUND_TYPE (forest 0, grass 1, mud 2, sand 3, scrub 4, rock 5, …) of the
/// blend channel with the highest weight (first on ties), each channel's texture group (.terry texture_channel_N) mapped
/// by db ground_type_to_texture_groups; the blend TIF cropped by triangle_density on each side (1280 → 1024),
/// uncompressed L8 with BOB's bare header. No blend data → channel 0 everywhere.
/// </summary>
[BattleStepOrder(180)]
public sealed class BattleGroundTypesStep : IBattleBuildStep
{
    public string Name => "ground_types";

    public static readonly string[] GroundTypes =
    [
        "forest", "grass", "mud", "sand", "scrub", "rock", "deep_water", "shallow_water", "road", "wooden_floor", "snow",
        "sharp_stones", "burnt", "wet_mud", "long_grass", "light_forest", "caltrops", "oil",
    ];

    public void Run(BattleBuildContext ctx, Action<string> log)
    {
        var map = TextureGroundTypes(ctx);
        var doc = XDocument.Load(ctx.TerryFile);
        var inner = doc.Descendants("pc").First(e => (string?)e.Attribute("type") == "QTU::ProjectTileWithVista").Element("data")!.Element("data")!;
        var gt = Enumerable.Range(0, 8).Select(i => (byte)map.GetValueOrDefault((string?)inner.Attribute($"texture_channel_{i}") ?? "", 1)).ToArray();
        var project = TerryTileProject.Load(ctx.TerryFile);
        var density = project.TriangleDensity;
        int size = project.TilesWide * density, sizeH = project.TilesHigh * density;
        var blend = TileBlend.Read(ctx.SourceTileDir);
        var pixels = new byte[size * sizeH];
        for (var y = 0; y < sizeH; y++)
            for (var x = 0; x < size; x++)
            {
                var best = 0;
                if (blend is { } b)
                {
                    var o = ((y + density) * b.W + x + density) * 8;
                    for (var c = 1; c < 8; c++) if (b.Data[o + c] > b.Data[o + best]) best = c;
                }
                pixels[y * size + x] = gt[best];
            }
        using var ms = new MemoryStream();
        using var w = new BinaryWriter(ms);
        w.Write("DDS "u8); w.Write(124); w.Write(0); w.Write(sizeH); w.Write(size);
        for (var i = 0; i < 14; i++) w.Write(0);
        w.Write(32); w.Write(0x20000); w.Write(0); w.Write(8); w.Write(0xFF); w.Write(0); w.Write(0); w.Write(0);
        for (var i = 0; i < 5; i++) w.Write(0);
        w.Write(pixels);
        File.WriteAllBytes(Path.Combine(ctx.OutTileDir, "ground_types.dds"), ms.ToArray());
    }

    /// <summary>db ground_type_to_texture_groups (texture group → ground type index), read from the game packs.</summary>
    public static Dictionary<string, int> TextureGroundTypes(BattleBuildContext ctx)
    {
        var result = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        foreach (var key in ctx.Packs.Packs.SelectMany(p => p.Entries.Keys)
                     .Where(k => k.StartsWith(@"db\ground_type_to_texture_groups_tables\", StringComparison.Ordinal)).Distinct())
        {
            var bytes = ctx.Packs.TryRead(key);
            if (bytes is null) continue;
            var table = Atlas3K.Formats.Db.DbBinaryTable.Read("ground_type_to_texture_groups_tables", bytes);
            int gi = table.Index("texture_group"), ti = table.Index("ground_type");
            foreach (var row in table.Rows)
            {
                var i = Array.IndexOf(GroundTypes, (string?)row[ti]);
                if (i >= 0) result.TryAdd((string)row[gi]!, i);
            }
        }
        return result;
    }

}

/// <summary>
/// debug_protection_map.png (TerryTile "excluding heightmap"): the tile's protection map (the mask buildings put on the
/// mesh's vertex lattice) as an RGB PNG of tiles × density pixels (1024² for 8×8), written by Qt/libpng with zlib level
/// 6 (<see cref="QtPng"/>). Only the empty map is reproduced: building protection is not ported (every corpus
/// project's map is empty, the same 3,150-byte file).
/// </summary>
[BattleStepOrder(185)]
public sealed class BattleDebugProtectionStep : IBattleBuildStep
{
    public string Name => "debug_protection";

    public void Run(BattleBuildContext ctx, Action<string> log)
    {
        var project = TerryTileProject.Load(ctx.TerryFile);
        int w = project.TilesWide * project.TriangleDensity, h = project.TilesHigh * project.TriangleDensity;
        var black = new Atlas3K.Formats.Maps.Raster<uint>(w, h);
        Array.Fill(black.Data, 0xFF000000u);
        File.WriteAllBytes(Path.Combine(ctx.OutTileDir, "debug_protection_map.png"), QtPng.EncodeRgb(black, stored: false));
    }
}
