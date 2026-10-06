using System.Globalization;
using System.Text;
using System.Xml.Linq;
using Atlas3K.Core.Campaign.Props;
using Atlas3K.Core.Campaign.Rivers;

namespace Atlas3K.Core.Battle.Build.Bmd;

/// <summary>
/// terrain/vegetation/battle/grass/grass_generation_spec.xml as QTU::GrassGenerationSpec reads it: per blend texture
/// name an optional threshold and, per climate (or "*"), a run of model specs and a density.
/// </summary>
public sealed class GrassSpec
{
    public sealed record ModelSpec(string Path, float AlphaMul, float AlphaAdd, float FarAddition);

    private sealed class TextureEntry
    {
        public float? Threshold;
        public readonly Dictionary<string, (int First, int Count, float Density)> Climates = new(StringComparer.Ordinal);
    }

    private readonly Dictionary<string, TextureEntry> _textures = new(StringComparer.Ordinal);

    public float DefaultDensity { get; private init; }
    public float DefaultThreshold { get; private init; }
    /// <summary>Every model of every climate entry, in document order (generated grass items index into this).</summary>
    public List<ModelSpec> Models { get; } = [];

    public const string PackPath = "terrain/vegetation/battle/grass/grass_generation_spec.xml";

    public static GrassSpec Parse(string xml)
    {
        var root = XDocument.Parse(xml).Root!;
        var spec = new GrassSpec
        {
            DefaultDensity = ParseF((string?)root.Element("default_density") ?? "0.1"),
            DefaultThreshold = ParseF((string?)root.Element("default_blendmap_value_treshold") ?? "0"),
        };
        foreach (var tex in root.Element("grass_types")?.Elements("texture") ?? [])
        {
            var name = ((string?)tex.Attribute("val") ?? "").Trim();
            if (!spec._textures.TryGetValue(name, out var entry)) spec._textures[name] = entry = new TextureEntry();
            if (tex.Attribute("treshold") is { } t) entry.Threshold = ParseF(t.Value);
            foreach (var climate in tex.Elements("climate"))
            {
                var first = spec.Models.Count;
                foreach (var m in climate.Elements("model"))
                    spec.Models.Add(new ModelSpec(m.Value.Trim(), Attr(m, "alpha_mul"), Attr(m, "alpha_add"), Attr(m, "far_addition")));
                var density = climate.Element("density") is { } d ? ParseF(d.Value) : -1f;
                foreach (var c in ((string?)climate.Attribute("values") ?? "").Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
                    entry.Climates[c] = (first, spec.Models.Count - first, density);
            }
        }
        return spec;
    }

    private static float Attr(XElement e, string name) => e.Attribute(name) is { } a ? ParseF(a.Value) : 0f;
    private static float ParseF(string s) => float.Parse(s.Trim(), NumberStyles.Float, CultureInfo.InvariantCulture);

    /// <summary>GrassGenerationSpec::texture_treshold: the texture's threshold, else the default.</summary>
    public float Threshold(string texture) =>
        texture.Length == 0 ? 0f : _textures.TryGetValue(texture, out var e) && e.Threshold is { } t ? t : DefaultThreshold;

    /// <summary>GrassGenerationSpec::climate_spec: (first model, model count, density) of a texture in a climate (or
    /// its "*" entry); null when the texture has no grass there. A density below 0 takes the default density.</summary>
    public (int First, int Count, float Density)? ClimateSpec(string climate, string texture)
    {
        if (!_textures.TryGetValue(texture, out var e)) return null;
        if (!e.Climates.TryGetValue(climate, out var c) && !e.Climates.TryGetValue("*", out c)) return null;
        return c.Density < 0f ? (c.First, c.Count, DefaultDensity) : c;
    }
}

/// <summary>One generated grass item: world x/z (tile space) and the index into <see cref="GrassSpec.Models"/>.</summary>
public readonly record struct GrassItem(float X, float Z, int Model);

/// <summary>
/// BOB's battle grass (bob_vegetation "Generate Grass" → qttoolutility QTU::generate_grass, FUN_1800788c0), bit-exact:
/// for every terrain-map texel whose tile cell is not masked, the texture is the first channel, in descending weight
/// order (stable insertion sort, FUN_1800bbae0), whose weight is above its threshold; its climate spec gives the models
/// and a density. Grid points spaced 1/√density, aligned to the tile's outer box, are walked inside the texel's world
/// rect; each gets a jitter (two xoroshiro128+ draws: angle and radius, BOB's sine) and a model (one rejection-sampled
/// draw). One generator per climate, each reseeded with the project's grass_seed.
/// </summary>
public static class GrassGenerator
{
    private const float Half = 0.5f;

    /// <summary>The Blend8 terrain map as the generator sees it (QTU TerrainMap::data_composited): channel c = v·(1/255),
    /// then channel 0 += 1 − Σ channels (summed in channel order), so an unpainted pixel is all channel 0.</summary>
    public static float[] BlendWeights(byte[] raw, int channels)
    {
        var k = 1f / 255f;
        var w = new float[raw.Length];
        for (var p = 0; p < raw.Length; p += channels)
        {
            var total = 0f;
            for (var c = 0; c < channels; c++)
            {
                w[p + c] = raw[p + c] * k;
                total += w[p + c];
            }
            w[p] += 1f - total;
        }
        return w;
    }

    // Transform2 (6 floats): X = m0 x + m1 y + m4, Y = m2 x + m3 y + m5.
    private static float[] Compose(float[] p2, float[] p3) =>   // FUN_1800d6110(out, p2, p3): p3 after p2
    [
        p3[0] * p2[0] + p3[1] * p2[2], p3[0] * p2[1] + p3[1] * p2[3],
        p3[3] * p2[2] + p3[2] * p2[0], p3[3] * p2[3] + p3[2] * p2[1],
        p3[4] + p3[0] * p2[4] + p3[1] * p2[5], p3[3] * p2[5] + p3[2] * p2[4] + p3[5],
    ];

    private static float[] Invert(float[] p)   // FUN_1800e5480
    {
        var f9 = 1f / (p[0] * p[3] - p[1] * p[2]);
        float f7 = -(f9 * p[1]), f8 = -(f9 * p[2]), f10 = f9 * p[0], a = f9 * p[3];
        return [a, f7, f8, f10, -(f7 * p[5] + a * p[4]), -(f10 * p[5] + f8 * p[4])];
    }

    /// <summary>QTU::TileMetrics::terrain_map_to_world(true): world = (map − (density + 1)) · cell / density.</summary>
    private static float[] TerrainMapToWorld(float density, float cell)
    {
        var t = density + 1f;
        var s = density / cell;
        return Invert(Compose([s, 0f, 0f, s, 0f, 0f], [1f, 0f, 0f, 1f, t, t]));
    }

    /// <summary>QTU::TileMetrics::cell_to_world: y flipped, origin at the top row (cell · cell size).</summary>
    private static float[] CellToWorld(int cellsHigh, float cell)
    {
        float[] t = [1f, 0f, -0f, -1f, 0f, 0f];
        var t5 = t[5];
        t[5] = t[4] * 0f + -1f * t5; t[4] = 1f * t[4] + t5 * 0f + 0f; t[5] += 0f;
        t5 = t[5];
        t[5] = 0f * t[4] + 1f * t[5]; t[4] = 1f * t[4] + 0f * t5 + 0f; t[5] = cellsHigh + t[5];
        return [cell * t[0], cell * t[1], cell * t[2], cell * t[3], cell * t[4], cell * t[5]];
    }

    private static int FloorI(float v) { var i = (int)v; return i != v && v < 0 ? i - 1 : i; }
    private static int CeilI(float v) { var i = (int)v; return i != v && v > 0 ? i + 1 : i; }

    /// <summary>Generates one climate's grass. <paramref name="weights"/>: pixel-major (y, x, channel) from
    /// <see cref="BlendWeights"/>; <paramref name="masked"/>: optional (cellX, cellY) → masked.</summary>
    public static List<GrassItem> Generate(float[] weights, int width, int height, int channels, IReadOnlyList<string> textures,
        GrassSpec spec, string climate, uint seed, int cellsWide, int cellsHigh, int density, float cell = 256f,
        Func<int, int, bool>? masked = null)
    {
        var rng = new Xoroshiro128Plus(seed);
        float minX = -cell, minZ = -cell, maxX = (cellsWide + 1) * cell, maxZ = (cellsHigh + 1) * cell;
        float boxW = maxX - minX, boxH = maxZ - minZ;
        var tmw = TerrainMapToWorld(density, cell);
        var m2c = Compose(tmw, Invert(CellToWorld(cellsHigh, cell)));
        var thresholds = new float[channels];
        var specs = new (int First, int Count, float Density)?[channels];
        for (var c = 0; c < channels; c++)
        {
            var name = c < textures.Count ? textures[c] : "";
            thresholds[c] = spec.Threshold(name);
            specs[c] = spec.ClimateSpec(climate, name);
        }
        var order = new int[channels];
        var output = new List<GrassItem>();
        for (var x = 0; x < width; x++)
        {
            float fx = x, l8 = m2c[0] * (fx + Half), lc = m2c[2] * (fx + Half);
            for (var y = 0; y < height; y++)
            {
                float fy = y;
                float cx = m2c[4] + m2c[1] * (fy + Half) + l8, cy = m2c[5] + m2c[3] * (fy + Half) + lc;
                int ci = FloorI(cx), cj = FloorI(cy);
                if (ci < 0 || cj < 0 || ci >= cellsWide || cj >= cellsHigh || (masked?.Invoke(ci, cj) ?? false)) continue;
                var p = (y * width + x) * channels;
                // FUN_1800792c0: channel indices insertion-sorted by descending weight (stable), first over its threshold
                for (var c = 0; c < channels; c++)
                {
                    var j = c;
                    while (j > 0 && weights[p + order[j - 1]] < weights[p + c]) { order[j] = order[j - 1]; j--; }
                    order[j] = c;
                }
                var tex = -1;
                foreach (var c in order)
                    if (thresholds[c] < weights[p + c]) { tex = c; break; }
                if (tex < 0 || specs[tex] is not { } cs || !(cs.Density >= 0f)) continue;
                var s = 1f / MathF.Sqrt(cs.Density);
                var inv = 1f / s;
                float x1 = x + 1, y1 = y + 1;
                var xe = tmw[4] + tmw[1] * y1 + tmw[0] * x1;
                var ze = tmw[5] + tmw[3] * y1 + tmw[2] * x1;
                var offX = (boxW - FloorI(inv * boxW) * s) * Half;
                var offZ = (boxH - FloorI(inv * boxH) * s) * Half;
                var gx = CeilI((tmw[4] + tmw[0] * fx + tmw[1] * fy - offX - minX) * inv) * s + minX + offX;
                var gz0 = CeilI((tmw[5] + tmw[3] * fy + tmw[2] * fx - offZ - minZ) * inv) * s + minZ + offZ;
                for (; gx < xe; gx += s)
                {
                    if (!(gz0 < ze)) continue;
                    var gz = gz0;
                    do
                    {
                        var angleBits = rng.NextHigh16();
                        var radiusBits = rng.NextHigh16();
                        var a = radiusBits * BitConverter.UInt32BitsToSingle(0x37800080);       // 1/65535
                        var angle = angleBits * BitConverter.UInt32BitsToSingle(0x38c910a4);    // 2π/65535
                        var (sin, cos) = QtuTransform.SinCos(angle);
                        var px = cos * a * s * Half + gx;
                        var pz = sin * a * s * Half + gz;
                        output.Add(new GrassItem(px, pz, rng.NextIndex((uint)cs.Count) + cs.First));
                        gz += s;
                    } while (gz < ze);
                }
            }
        }
        return output;
    }

    /// <summary>
    /// The grass_list.bin bob_vegetation writes (FUN_180003690 + EMPIREUTILITY::GRASS_LIST::save): items inside the
    /// tile's inner box become (x, height, z) halves (BOB's float-to-half), grouped per model description in BOB's
    /// hash-map order; the height is the Height map at (z/2 + density, x/2 + density). Null when no item is kept (BOB
    /// writes no file then).
    /// </summary>
    public static byte[]? WriteList(IReadOnlyList<GrassItem> items, GrassSpec spec, float[] heights, int heightWidth,
        int cellsWide, int cellsHigh, int density, float cell = 256f)
    {
        var k = 1f / (cell / density * 1f);
        float off = density, maxX = cellsWide * cell, maxZ = cellsHigh * cell;
        var map = new CaHashMapOrder<(string Path, float A, float B, float C)>(key => DescriptionHash(key.Path, key.A, key.B, key.C));
        var groups = new Dictionary<(string, float, float, float), List<(ushort, ushort, ushort)>>();
        foreach (var it in items)
        {
            if (!(0f <= it.X && 0f <= it.Z && it.X < maxX && it.Z < maxZ)) continue;
            var row = (int)(it.Z * k + off);
            var col = (int)(off + k * it.X);
            var idx = (long)row * heightWidth + col;
            if ((ulong)idx >= (ulong)heights.Length) continue;
            var m = spec.Models[it.Model];
            var key = (m.Path, m.AlphaMul, m.AlphaAdd, m.FarAddition);
            if (map.Insert(key)) groups[key] = [];
            groups[key].Add((BobRiver.HalfBits(it.X), BobRiver.HalfBits(heights[idx]), BobRiver.HalfBits(it.Z)));
        }
        if (map.Items.Count == 0) return null;
        using var ms = new MemoryStream();
        using var w = new BinaryWriter(ms);
        w.Write(Encoding.ASCII.GetBytes("FASTBIN0"));
        w.Write((ushort)2);
        w.Write((uint)map.Items.Count);
        foreach (var key in map.Items)
        {
            var path = Encoding.Latin1.GetBytes(key.Path);
            w.Write((ushort)1);
            w.Write((ushort)path.Length);
            w.Write(path);
            w.Write(key.A); w.Write(key.B); w.Write(key.C);
            var g = groups[key];
            w.Write((uint)g.Count);
            foreach (var (a, b, c) in g) { w.Write(a); w.Write(b); w.Write(c); }
        }
        w.Flush();
        return ms.ToArray();
    }

    // ---------------------------------------------------------------- EMPIREUTILITY::GRASS_DESCRIPTION hash (bob_vegetation FUN_1800340d0)

    private static uint Rot(uint x, int b) => (x << (b ^ 31)) | (x >> b);   // as written in the DLL (not a true rotate)

    /// <summary>FUN_180091030: big-endian chunks of up to 4 bytes mixed into the hash.</summary>
    public static uint StringHash(string s)
    {
        var d = Encoding.Latin1.GetBytes(s);
        uint h = 0;
        for (var i = 0; i < d.Length; i += 4)
        {
            uint c = 0;
            for (var j = i; j < Math.Min(i + 4, d.Length); j++) c = (c << 8) | d[j];
            h = Rot(h, (int)((((c ^ h) & 0xff) + 13) & 31)) ^ c;
        }
        return h;
    }

    /// <summary>The description hash (before the bucket modulo): the path's string hash mixed with the three floats'
    /// bits (alpha_mul, alpha_add, far_addition) and a zero flag byte.</summary>
    public static uint DescriptionHash(string path, float alphaMul, float alphaAdd, float farAddition)
    {
        uint f10 = BitConverter.SingleToUInt32Bits(alphaMul), f14 = BitConverter.SingleToUInt32Bits(alphaAdd),
            f18 = BitConverter.SingleToUInt32Bits(farAddition);
        var u6 = Rot(0, 13);
        var u2 = Rot(f14, (int)((((f18 ^ f14) & 0xff) + 13) & 31)) ^ f18;
        u6 = Rot(u2, (int)((((u2 ^ u6) & 0xff) + 13) & 31)) ^ u6;
        var h0 = StringHash(path);
        u2 = Rot(h0, (int)((((f10 ^ h0) & 0xff) + 13) & 31)) ^ f10;
        return Rot(u2, (int)((((u2 ^ u6) & 0xff) + 13) & 31)) ^ u6;
    }
}

/// <summary>
/// Iteration order of the CA hash map bob_vegetation keeps grass descriptions in (insert FUN_1800259d0, rehash
/// FUN_180037f40): one list ordered by bucket (hash % buckets), a new key at the end of its bucket; starts with one
/// bucket, max load 1.0, growing to max(⌈count⌉, 2·boundaries − 1) buckets, re-inserting the old list in order.
/// </summary>
public sealed class CaHashMapOrder<T>(Func<T, uint> hash) where T : notnull
{
    private readonly List<T> _items = [];
    private readonly HashSet<T> _set = [];
    private uint _boundaries = 2;

    public IReadOnlyList<T> Items => _items;

    /// <summary>Adds <paramref name="key"/> unless present; true when it was new.</summary>
    public bool Insert(T key)
    {
        if (!_set.Add(key)) return false;
        var count = (uint)_items.Count;
        if ((float)(count + 1) / (_boundaries - 1) > 1f)
        {
            _boundaries = Math.Max(count, 2 * _boundaries - 1) + 1;
            var old = _items.ToList();
            _items.Clear();
            foreach (var o in old) Place(o);
        }
        Place(key);
        return true;
    }

    private uint Bucket(T key) => hash(key) % (_boundaries - 1);

    private void Place(T key)
    {
        var b = Bucket(key);
        var pos = _items.FindIndex(o => Bucket(o) > b);
        _items.Insert(pos < 0 ? _items.Count : pos, key);
    }
}
