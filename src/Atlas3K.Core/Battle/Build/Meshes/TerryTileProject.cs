using System.Globalization;
using System.Xml.Linq;
using BitMiracle.LibTiff.Classic;

namespace Atlas3K.Core.Battle.Build.Meshes;

/// <summary>
/// The parts of a Terry battle tile project (<c>QTU::ProjectTileWithVista</c>, raw_data/terrain/tiles/battle/_assembly_kit/&lt;id&gt;)
/// the mesh steps read: tile size in tiles, triangle density, the tile database flags and the Height terrain map's TIF.
/// Terry stores each serializable terrain map layer as <c>&lt;project&gt;.&lt;map&gt;.&lt;layer id&gt;.tif</c> next to the .terry.
/// </summary>
public sealed class TerryTileProject
{
    public required string TerryPath { get; init; }
    /// <summary>Tile size in tile-map cells (the <c>size="8x8"</c> attribute).</summary>
    public int TilesWide { get; init; }
    public int TilesHigh { get; init; }
    /// <summary>Vertices per tile cell edge (<c>triangle_density</c>; the variation's raw_data_tri_density).</summary>
    public int TriangleDensity { get; init; }
    public float NormalStrength { get; init; }
    /// <summary>tile_database <c>infield_tile</c>: BOB's requires_infield_lodding (mesh + outfield mesh).</summary>
    public bool InfieldTile { get; init; }
    /// <summary>The cells/mask string ('0'/'1' per cell, row-major); empty = every cell valid.</summary>
    public string Mask { get; init; } = "";
    /// <summary>The Height map's serializable layer TIF (float32), null when the project has none.</summary>
    public string? HeightTif { get; init; }

    public bool Masked => Mask.Length > 0;

    public static TerryTileProject Load(string terryPath)
    {
        var doc = XDocument.Load(terryPath);
        var tile = doc.Descendants("pc").First(e => (string?)e.Attribute("type") == "QTU::ProjectTileWithVista").Element("data")!;
        var size = ((string?)tile.Attribute("size") ?? "8x8").Split('x');
        var inner = tile.Element("data");
        var db = inner?.Element("tile_database");
        string? heightTif = null;
        foreach (var map in doc.Descendants("pc").Where(e => (string?)e.Attribute("type") == "QTU::TerrainMap"))
        {
            if ((string?)map.Element("data")?.Attribute("type") != "Height") continue;
            var layer = map.Elements("pc").Select(e => e.Element("data")).FirstOrDefault(d => (string?)d?.Attribute("serializable") == "1");
            if (layer is null) continue;
            var path = Path.Combine(Path.GetDirectoryName(terryPath)!,
                $"{Path.GetFileNameWithoutExtension(terryPath)}.height.{(string?)layer.Attribute("id")}.tif");
            if (File.Exists(path)) heightTif = path;
        }
        return new TerryTileProject
        {
            TerryPath = terryPath,
            TilesWide = int.Parse(size[0], CultureInfo.InvariantCulture),
            TilesHigh = int.Parse(size[1], CultureInfo.InvariantCulture),
            TriangleDensity = int.Parse((string?)tile.Attribute("triangle_density") ?? "128", CultureInfo.InvariantCulture),
            NormalStrength = float.Parse((string?)db?.Attribute("normal_strength") ?? "2", CultureInfo.InvariantCulture),
            InfieldTile = ((string?)db?.Attribute("infield_tile") ?? "true") == "true",
            Mask = ((string?)tile.Element("cells")?.Element("mask") ?? "").Trim(),
            HeightTif = heightTif,
        };
    }

    /// <summary>A single-channel float32 TIF as (width, height, row-major values).</summary>
    public static (int Width, int Height, float[] Values) ReadFloatTif(string path)
    {
        using var tif = Tiff.Open(path, "r") ?? throw new IOException($"Cannot open {path}");
        var w = tif.GetField(TiffTag.IMAGEWIDTH)[0].ToInt();
        var h = tif.GetField(TiffTag.IMAGELENGTH)[0].ToInt();
        if (tif.GetField(TiffTag.BITSPERSAMPLE)[0].ToInt() != 32)
            throw new InvalidDataException($"{Path.GetFileName(path)} is not a 32-bit float map.");
        var values = new float[w * h];
        var row = new byte[tif.ScanlineSize()];
        for (var y = 0; y < h; y++)
        {
            tif.ReadScanline(row, y);
            Buffer.BlockCopy(row, 0, values, y * w * 4, w * 4);
        }
        return (w, h, values);
    }

    /// <summary>
    /// The tile height field BOB meshes (WS_SCENE_NODE_TERRAIN_EDITOR_V3::load_and_process_height_map, warscape
    /// FUN_18039bac0 / FUN_18039bf80): the Height map minus an overlap border, (W − (2·density − 1)) square, sample
    /// (r, c) = map[r + density + 1, c + density + 1]. For an 8×8 tile at density 128 that is 1025² of the 1280² map.
    /// </summary>
    public float[] HeightField(out int width, out int height)
    {
        if (HeightTif is null) throw new FileNotFoundException($"no Height map TIF next to {TerryPath}");
        var (w, h, v) = ReadFloatTif(HeightTif);
        var trim = TriangleDensity * 2 - 1;
        var offset = TriangleDensity + 1;
        width = w - trim;
        height = h - trim;
        var field = new float[width * height];
        for (var r = 0; r < height; r++)
            Array.Copy(v, (r + offset) * w + offset, field, r * width, width);
        return field;
    }
}
