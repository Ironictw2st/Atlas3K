using System.Buffers.Binary;
using System.Text;
using Atlas3K.Formats.Maps;

namespace Atlas3K.Core.Campaign.GlobalMesh;

/// <summary>
/// The height BOB samples for a global-mesh grid point (tooldatabuilder FUN_18016ae30), float32 in BOB's order:
///  - the tile instances under the point, skipping tile sets marked exclude_from_global_mesh (campaign
///    _tile_database/_settings.bin) and tiles whose use_alt_lf differs from the mesh kind (sea meshes: alt lf);
///  - per tile, WARSCAPE::TERRAIN_RENDER_SETUP::get_height (hf + lf, see <see cref="Terrain.TileHfHeight"/>) at the point and
///    at the 4 diagonal probes ±0.001; the centre wins when the tile answers there, else the lowest answering probe;
///    a tile that answers nowhere passes to the next;
///  - no tile answers: −20 (a hole).
/// </summary>
public sealed class BobGlobalHeight
{
    public const float Hole = -20f;
    internal static readonly int Variant = int.TryParse(Environment.GetEnvironmentVariable("ATLAS3K_GMESH_VARIANT"), out var v) ? v : 0;
    private const float Probe = 0.001f;
    private const float K = 1f / 65535f;

    private sealed record Map(ushort[] Data, int W, int H, float Lo, float Hi);

    private readonly TileList _list;
    private readonly TileInfo?[] _tileOfPath;
    private readonly bool[] _usable;
    private readonly Map?[] _hfOfPath;
    private readonly List<int>?[] _cells;
    private readonly int _tilesW, _tilesH;
    private readonly float _t, _invT, _f, _fLf, _maxX, _maxZ;
    private readonly Map _lf, _altLf;

    /// <summary>TERRAIN_RENDER_SETUP +0x324: the terrain's tile size, (1/tilesW) · (tilesW · T).</summary>
    public float TileSize => _t;

    public BobGlobalHeight(TileList list, IReadOnlyDictionary<string, TileInfo> db, IReadOnlySet<string> excludedSets,
        Func<string, byte[]?> readPack, CompressedMap.Map lf, CompressedMap.Map altLf, float tileSize)
    {
        _list = list;
        _tilesW = list.Ints[1];
        _tilesH = list.Ints[2];
        _maxX = _tilesW * tileSize;
        _maxZ = _tilesH * tileSize;
        // TERRAIN_RENDER_SETUP +0x324: the terrain width / tiles (main190: 0x3eaaca80, an ulp under 595.1/1784)
        _t = (Variant & 32) != 0 ? tileSize : 1f / _tilesW * _maxX;
        _invT = 1f / _t;
        _f = 1f / 128f * ((Variant & 64) != 0 ? tileSize : _t);
        _fLf = 0.0390625f * _t;
        if ((Variant & 128) == 0)
        {
            // the terrain bounds (+0x340..+0x34c) in that tile size
            _maxX = _tilesW * _t;
            _maxZ = _tilesH * _t;
        }
        if (int.TryParse(Environment.GetEnvironmentVariable("ATLAS3K_GMESH_MAXX_ULP"), out var ulp))
            _maxX = BitConverter.Int32BitsToSingle(BitConverter.SingleToInt32Bits(_maxX) + ulp);
        if (int.TryParse(Environment.GetEnvironmentVariable("ATLAS3K_GMESH_MAXZ_ULP"), out var ulpZ))
            _maxZ = BitConverter.Int32BitsToSingle(BitConverter.SingleToInt32Bits(_maxZ) + ulpZ);
        _lf = new Map(lf.Raster.Data, lf.Raster.Width, lf.Raster.Height, lf.Header[1], lf.Header[4]);
        _altLf = new Map(altLf.Raster.Data, altLf.Raster.Width, altLf.Raster.Height, altLf.Header[1], altLf.Header[4]);
        _tileOfPath = new TileInfo?[list.Paths.Count];
        _usable = new bool[list.Paths.Count];
        _hfOfPath = new Map?[list.Paths.Count];
        var cache = new Dictionary<string, Map?>(StringComparer.OrdinalIgnoreCase);
        for (var i = 0; i < list.Paths.Count; i++)
        {
            var key = TileDatabase.NormalisePath(list.Paths[i]);
            db.TryGetValue(key, out var tile);
            _tileOfPath[i] = tile;
            _usable[i] = tile is not null && !excludedSets.Contains(tile.Category);
            if (!cache.TryGetValue(key, out var hf))
            {
                hf = null;
                if (readPack(key.Replace('\\', '/') + "hf_height_map.compressed_map") is { } bytes)
                {
                    try
                    {
                        var m = CompressedMap.Decode(bytes);
                        if (m.Header[1] != 0f || m.Header[4] != 0f)
                            hf = new Map(m.Raster.Data, m.Raster.Width, m.Raster.Height, m.Header[1], m.Header[4]);
                    }
                    catch (InvalidDataException) { }
                }
                cache[key] = hf;
            }
            _hfOfPath[i] = hf;
        }
        _cells = new List<int>[_tilesW * _tilesH];
        for (var r = 0; r < list.Records.Count; r++)
        {
            var rec = list.Records[r];
            var tile = _tileOfPath[rec.Path];
            if (tile is null) continue;
            var (w, h) = Size(tile, rec.Orientation);
            for (var y = rec.Y; y <= Math.Min(rec.Y + h, _tilesH - 1); y++)
                for (var x = rec.X; x <= Math.Min(rec.X + w, _tilesW - 1); x++)
                    (_cells[y * _tilesW + x] ??= []).Add(r);
        }
    }

    private static (int W, int H) Size(TileInfo t, byte orientation) =>
        (orientation & 0xF0) is 0x20 or 0x80 ? (t.Height, t.Width) : (t.Width, t.Height);

    /// <summary>The grid point's height for a land (alt = false) or sea (alt = true) mesh, or <see cref="Hole"/>.</summary>
    public float Height(float x, float z, bool alt)
    {
        var seen = new HashSet<int>();
        // the tiles near the point: the cells under the centre and the probes
        foreach (var (px, pz) in (ReadOnlySpan<(float, float)>)[(x, z), (x + Probe, z + Probe), (x - Probe, z + Probe), (x + Probe, z - Probe), (x - Probe, z - Probe)])
        {
            int cx = (int)(_invT * px), cy = (int)(_invT * pz);
            if (px < 0 || pz < 0 || cx < 0 || cy < 0 || cx >= _tilesW || cy >= _tilesH) continue;
            if (_cells[cy * _tilesW + cx] is { } cell) foreach (var r in cell) seen.Add(r);
        }
        if (seen.Count == 0) return Hole;
        var order = seen.ToList();
        order.Sort();
        foreach (var r in order)
        {
            var path = _list.Records[r].Path;
            if (!_usable[path] || _tileOfPath[path]!.UseAltLf != alt) continue;
            if (TileHeight(r, x, z, alt, out var c)) return c;
            var any = false;
            var best = 0f;
            foreach (var (px, pz) in (ReadOnlySpan<(float, float)>)[(x + Probe, z + Probe), (x - Probe, z + Probe), (x + Probe, z - Probe), (x - Probe, z - Probe)])
                if (TileHeight(r, px, pz, alt, out var h))
                {
                    if (!any || h <= best) best = h;
                    any = true;
                }
            if (any) return best;
        }
        return Hole;
    }

    private static float Sample(Map m, float u, float v)
    {
        var fx = m.W * u;
        var fy = m.H * v;
        var fx0 = MathF.Floor(fx);
        var fy0 = MathF.Floor(fy);
        float xi = (int)fx, yi = (int)fy;
        float maxC = m.W - 1, maxR = m.H - 1;
        static float Clamp(float a, float hi) => a < 0f ? 0f : a > hi ? hi : a;
        float Value(float c, float r)
        {
            var raw = m.Data[(int)Clamp(r, maxR) * m.W + (int)Clamp(c, maxC)];
            return raw * K * (m.Hi - m.Lo) + m.Lo;
        }
        var a = Value(xi, yi - 1f);
        var b = Value(xi + 1f, yi - 1f);
        var top = (b - a) * (fx - fx0) + a;
        var c = Value(xi, yi);
        var d = Value(xi + 1f, yi);
        var bot = (d - c) * (fx - fx0) + c;
        return (bot - top) * (fy - fy0) + top;
    }

    /// <summary>FUN_1803a1e30 (COMPRESSED_HEIGHT_MAP bilinear): rows int((v - 1/H)·H) and int(v·H), columns int(u·W) and
    /// int((u + 1/W)·W), clamped; value = lo + raw/65535 · (hi - lo).</summary>
    private static float SampleCompressed(Map m, float u, float v)
    {
        var fx = u * m.W;
        var fy = v * m.H;
        var x0 = MathF.Floor(fx);
        var y0 = MathF.Floor(fy);
        var fyu = (v - 1f / m.H) * m.H;
        var fxr = (u + 1f / m.W) * m.W;
        float Value(float col, float row)
        {
            var c = (int)Math.Clamp(col, 0f, m.W - 1);
            var r = (int)Math.Clamp(row, 0f, m.H - 1);
            var raw = m.Data[r * m.W + c] * K;
            return m.Lo == 0f && m.Hi == 1f ? raw : m.Lo + raw * (m.Hi - m.Lo);
        }
        var a = Value(fx, fyu);
        var b = Value(fxr, fyu);
        var top = (b - a) * (fx - x0) + a;
        var c2 = Value(fx, fy);
        var d = Value(fxr, fy);
        var bot = (d - c2) * (fx - x0) + c2;
        return (bot - top) * (fy - y0) + top;
    }

    /// <summary>get_height for one tile instance: hf + lf, false when the tile doesn't answer at the point.</summary>
    private bool TileHeight(int r, float x, float z, bool alt, out float height)
    {
        height = 0f;
        if (x < 0f || x > _maxX || z < 0f || z > _maxZ) return false;
        var rec = _list.Records[r];
        var tile = _tileOfPath[rec.Path]!;
        var rot = rec.Orientation & 0xF0;
        var (w, h) = Size(tile, rec.Orientation);
        var tx = _invT * x;
        var ty = _invT * z;
        float x0 = rec.X, y0 = rec.Y, x1 = rec.X + w, y1 = rec.Y + h;
        if (tx < x0 || x1 < tx || ty < y0 || y1 < ty) return false;
        int ix = (int)(tx - x0), iy = (int)(ty - y0), col = ix, row = iy;
        switch (rot)
        {
            case 0x20: col = tile.Width - iy - 1; row = ix; break;
            case 0x40: col = tile.Width - ix - 1; row = tile.Height - iy - 1; break;
            case 0x80: col = iy; row = tile.Height - ix - 1; break;
        }
        var valid = tile.SubtileValid(col, tile.Height - row - 1);
        if (tile.Mask.Length > 0 && !valid) return false;
        var a = (tx - x0) / (x1 - x0);
        var b = (ty - y0) / (y1 - y0);
        float u = a, v = b;
        switch (rot)
        {
            case 0x10: break;
            case 0x20: u = 1f - b; v = a; break;
            case 0x40: u = 1f - a; v = 1f - b; break;
            case 0x80: u = b; v = 1f - a; break;
            default: u = 0f; v = 0f; break;
        }
        var hfMap = _hfOfPath[rec.Path];
        var hf = hfMap is null ? 0f : Sample(hfMap, u, v) * _f;
        if (!(valid || hf != 0f)) return false;
        var lu = (x - 0f) / (_maxX - 0f);
        var lv = 1f - (z - 0f) / (_maxZ - 0f);
        var l = (Variant & 4) != 0 ? SampleCompressed(alt ? _altLf : _lf, lu, lv) : Sample(alt ? _altLf : _lf, lu, lv);
        var lf = (Variant & 1) != 0 ? l * 5500f * _f - _f * 1200f : l * 1100f * _fLf - _fLf * 240f;
        height = (Variant & 2) != 0 ? lf + hf : hf + lf;
        return true;
    }

    /// <summary>Tile set names with exclude_from_global_mesh from campaign _tile_database/_settings.bin: the sets are the
    /// file's tail, u32 count then per set u16 version, name, linking_tile, shared_geometry, also_place_tile_set,
    /// link_as_set (u16 length + ASCII), 3 colour floats (v &lt; 3) or bytes, bool exclude_from_global_mesh (v &gt; 1).</summary>
    public static HashSet<string> ExcludedTileSets(byte[] settings)
    {
        for (var start = settings.Length - 8; start >= 10; start--)
        {
            var n = BinaryPrimitives.ReadUInt32LittleEndian(settings.AsSpan(start));
            if (n is 0 or > 500) continue;
            var result = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            var o = start + 4;
            var ok = true;
            for (var s = 0; s < n && ok; s++)
            {
                if (o + 2 > settings.Length) { ok = false; break; }
                var version = BinaryPrimitives.ReadUInt16LittleEndian(settings.AsSpan(o));
                if (version is 0 or > 10) { ok = false; break; }
                o += 2;
                var name = "";
                for (var k = 0; k < 5; k++)
                {
                    if (o + 2 > settings.Length) { ok = false; break; }
                    var len = BinaryPrimitives.ReadUInt16LittleEndian(settings.AsSpan(o));
                    if (o + 2 + len > settings.Length) { ok = false; break; }
                    if (k == 0) name = Encoding.ASCII.GetString(settings, o + 2, len);
                    o += 2 + len;
                }
                if (!ok || name.Length == 0) { ok = false; break; }
                o += version < 3 ? 12 : 3;
                if (version > 1)
                {
                    if (o >= settings.Length) { ok = false; break; }
                    if (settings[o] != 0) result.Add(name);
                    o++;
                }
            }
            if (ok && o == settings.Length) return result;
        }
        return [];
    }
}
