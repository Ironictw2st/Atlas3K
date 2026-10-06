using System.Buffers.Binary;
using System.IO.Hashing;
using System.Text;
using System.Xml.Linq;
using Atlas3K.Formats.Maps;

namespace Atlas3K.Core.Battle.Build;

/// <summary>
/// The BOB inputs Terry writes when a battle tile project is saved ("Terry save"), into
/// &lt;out&gt;/terry_save/{raw_data,working_data}/... (never into the kit):
///  - raw_data/terrain/battles/&lt;id&gt;/: the vista's (raw_data/terrain/vistas/&lt;vista&gt;) tile_map.png, lf_heights.tif and
///    lf_sea_heights.tif copied byte for byte; climate_map.png re-encoded the way Qt/libpng saves it (<see cref="QtPng"/>);
///    explicit_tiles.txt = the tile centred on the tile map ("x,y,terrain/tiles/battle/_assembly_kit/&lt;id&gt;,0" + CRLF);
///  - working_data rules.bob in the map and tile folders ([Pack] … PackFile = &lt;retail&gt;/data/&lt;.terry stem&gt;_&lt;id&gt;.pack);
///  - the tile database entry Terry saves (all 8 texture channels; BOB's TerryTile step then rewrites it, <see cref="BattleTileDbStep"/>).
/// </summary>
[BattleStepOrder(90)]
public sealed class TerrySaveStep : IBattleBuildStep
{
    public string Name => "terry_save";

    public void Run(BattleBuildContext ctx, Action<string> log)
    {
        var root = Path.Combine(ctx.OutRoot, "terry_save");
        var tileId = ctx.TileFolder;
        var doc = XDocument.Load(ctx.TerryFile);
        var data = doc.Descendants("pc").First(e => (string?)e.Attribute("type") == "QTU::ProjectTileWithVista").Element("data")!;
        var vista = (string?)data.Attribute("vista") ?? throw new InvalidDataException("tile project without a vista");
        var vistaDir = Path.Combine(ctx.RawData, vista.Replace('/', Path.DirectorySeparatorChar));
        var mapDir = Path.Combine(root, "raw_data", "terrain", "battles", ctx.MapId);
        Directory.CreateDirectory(mapDir);
        foreach (var f in new[] { "tile_map.png", "lf_heights.tif", "lf_sea_heights.tif" })
            File.Copy(Path.Combine(vistaDir, f), Path.Combine(mapDir, f), overwrite: true);
        var climate = PngMap.Read(Path.Combine(vistaDir, "climate_map.png"));
        File.WriteAllBytes(Path.Combine(mapDir, "climate_map.png"), QtPng.EncodeRgb(climate));

        var tileMap = PngMap.Read(Path.Combine(vistaDir, "tile_map.png"));
        var size = ((string?)data.Attribute("size") ?? "8x8").Split('x').Select(int.Parse).ToArray();
        int ex = (tileMap.Width - size[0]) / 2, ey = (tileMap.Height - size[1]) / 2;
        File.WriteAllText(Path.Combine(mapDir, "explicit_tiles.txt"), $"{ex},{ey},terrain/tiles/battle/_assembly_kit/{tileId},0\r\n");

        var stem = Path.GetFileNameWithoutExtension(ctx.TerryFile).Split('.')[0];
        var rules = $"[Pack]\r\n\tBasePath = /\r\n\tPackFile = <retail>/data/{stem}_{ctx.MapId}.pack\r\n\tPackType = mod";
        foreach (var dir in new[] { Path.Combine(root, "working_data", "terrain", "battles", ctx.MapId),
                                    Path.Combine(root, "working_data", "terrain", "tiles", "battle", "_assembly_kit", tileId) })
        {
            Directory.CreateDirectory(dir);
            File.WriteAllText(Path.Combine(dir, "rules.bob"), rules);
        }

        var db = Path.Combine(root, "working_data", "terrain", "tiles", "battle", "_tile_database", "TILES");
        Directory.CreateDirectory(db);
        var entry = TileDbEntry.FromTerry(ctx.TerryFile, tileId);
        File.WriteAllBytes(Path.Combine(db, ctx.TileDbStem + ".bin"), entry.ToBytes());
        File.WriteAllText(Path.Combine(db, ctx.TileDbStem + ".xml"), entry.ToXml(), new UTF8Encoding(false));
    }
}

/// <summary>
/// A PNG the way Terry (Qt's QImage::save → libpng) writes the climate map: RGB 8-bit, pHYs 3780 px/m (96 dpi), no
/// compression (zlib level 0: header 68 05, one stored block per ≤ 16 KiB window, adler32), libpng's adaptive row filter
/// (the minimum sum of |signed byte| over None, Sub, Up, Average, Paeth, first minimum wins), IDAT chunks of 8192 bytes.
/// </summary>
public static class QtPng
{
    public static byte[] EncodeRgb(Raster<uint> rgba)
    {
        int w = rgba.Width, h = rgba.Height, stride = w * 3;
        var raw = new List<byte>(h * (stride + 1));
        var prev = new byte[stride];
        var cur = new byte[stride];
        for (var y = 0; y < h; y++)
        {
            for (var x = 0; x < w; x++)
            {
                var p = rgba[x, y];
                cur[x * 3] = (byte)p; cur[x * 3 + 1] = (byte)(p >> 8); cur[x * 3 + 2] = (byte)(p >> 16);
            }
            var best = 0; var bestSum = long.MaxValue; byte[]? bestRow = null;
            for (var f = 0; f < 5; f++)
            {
                var row = Filter(f, cur, prev, 3);
                long sum = 0;
                foreach (var b in row) sum += Math.Abs((sbyte)b);
                if (sum < bestSum) { bestSum = sum; best = f; bestRow = row; }
            }
            raw.Add((byte)best);
            raw.AddRange(bestRow!);
            (prev, cur) = (cur, prev);
        }
        var z = new List<byte> { 0x68, 0x05 };
        var all = raw.ToArray();
        const int block = 16384;
        for (var o = 0; o < all.Length || o == 0; o += block)
        {
            var n = Math.Min(block, all.Length - o);
            var final = o + n >= all.Length;
            z.Add((byte)(final ? 1 : 0));
            z.Add((byte)n); z.Add((byte)(n >> 8)); z.Add((byte)~n); z.Add((byte)(~n >> 8));
            z.AddRange(all.AsSpan(o, n).ToArray());
            if (final) break;
        }
        uint a = 1, b2 = 0;
        foreach (var c in all) { a = (a + c) % 65521; b2 = (b2 + a) % 65521; }
        var adler = b2 << 16 | a;
        z.Add((byte)(adler >> 24)); z.Add((byte)(adler >> 16)); z.Add((byte)(adler >> 8)); z.Add((byte)adler);

        using var ms = new MemoryStream();
        ms.Write([0x89, (byte)'P', (byte)'N', (byte)'G', 0x0D, 0x0A, 0x1A, 0x0A]);
        var ihdr = new byte[13];
        BinaryPrimitives.WriteUInt32BigEndian(ihdr, (uint)w);
        BinaryPrimitives.WriteUInt32BigEndian(ihdr.AsSpan(4), (uint)h);
        ihdr[8] = 8; ihdr[9] = 2;
        Chunk(ms, "IHDR", ihdr);
        var phys = new byte[9];
        BinaryPrimitives.WriteUInt32BigEndian(phys, 3780);
        BinaryPrimitives.WriteUInt32BigEndian(phys.AsSpan(4), 3780);
        phys[8] = 1;
        Chunk(ms, "pHYs", phys);
        var zz = z.ToArray();
        for (var o = 0; o < zz.Length; o += 8192) Chunk(ms, "IDAT", zz.AsSpan(o, Math.Min(8192, zz.Length - o)).ToArray());
        Chunk(ms, "IEND", []);
        return ms.ToArray();
    }

    private static byte[] Filter(int f, byte[] cur, byte[] prev, int bpp)
    {
        var r = new byte[cur.Length];
        for (var i = 0; i < cur.Length; i++)
        {
            int a = i >= bpp ? cur[i - bpp] : 0, b = prev[i], c = i >= bpp ? prev[i - bpp] : 0;
            r[i] = f switch
            {
                0 => cur[i],
                1 => (byte)(cur[i] - a),
                2 => (byte)(cur[i] - b),
                3 => (byte)(cur[i] - ((a + b) >> 1)),
                _ => (byte)(cur[i] - Paeth(a, b, c)),
            };
        }
        return r;
    }

    private static int Paeth(int a, int b, int c)
    {
        int p = a + b - c, pa = Math.Abs(p - a), pb = Math.Abs(p - b), pc = Math.Abs(p - c);
        return pa <= pb && pa <= pc ? a : pb <= pc ? b : c;
    }

    private static void Chunk(Stream s, string type, byte[] data)
    {
        Span<byte> len = stackalloc byte[4];
        BinaryPrimitives.WriteUInt32BigEndian(len, (uint)data.Length);
        s.Write(len);
        var t = Encoding.ASCII.GetBytes(type);
        s.Write(t);
        s.Write(data);
        var crc = new Crc32();
        crc.Append(t); crc.Append(data);
        var c = crc.GetCurrentHashAsUInt32();
        BinaryPrimitives.WriteUInt32BigEndian(len, c);
        s.Write(len);
    }
}
