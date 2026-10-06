namespace Atlas3K.Core.Battle.Build.Bmd;

/// <summary>std::mt19937 (MSVC): seeded with x[i] = 1812433253 · (x[i−1] ^ x[i−1] &gt;&gt; 30) + i.</summary>
public sealed class Mt19937
{
    private readonly uint[] _mt = new uint[624];
    private int _i;

    public Mt19937(uint seed)
    {
        _mt[0] = seed;
        for (var i = 1; i < 624; i++) _mt[i] = 1812433253u * (_mt[i - 1] ^ (_mt[i - 1] >> 30)) + (uint)i;
        _i = 624;
    }

    public uint Next()
    {
        if (_i >= 624)
        {
            for (var k = 0; k < 624; k++)
            {
                var y = (_mt[k] & 0x80000000u) | (_mt[(k + 1) % 624] & 0x7fffffffu);
                _mt[k] = _mt[(k + 397) % 624] ^ (y >> 1) ^ ((y & 1) != 0 ? 0x9908b0dfu : 0u);
            }
            _i = 0;
        }
        var v = _mt[_i++];
        v ^= v >> 11;
        v ^= (v << 7) & 0x9d2c5680u;
        v ^= (v << 15) & 0xefc60000u;
        v ^= v >> 18;
        return v;
    }

    /// <summary>uniform_int_distribution&lt;int&gt;(0, 255): one draw, value % 256.</summary>
    public int Byte() => (int)(Next() % 256);

    /// <summary>uniform_real_distribution&lt;float&gt;(0, 1) through MSVC generate_canonical&lt;float, 24&gt; (one draw:
    /// float(u) / 2^32, which can round to 1).</summary>
    public float Uniform01() => (float)Next() / 4294967296f * (1f - 0f) + 0f;
}

/// <summary>One placed procedural object: the compiled object index, position, scale and yaw (radians).</summary>
public readonly record struct ProceduralInstance(int Object, float X, float Z, float Scale, float Rotation);

/// <summary>
/// qttoolutility QTU::ProceduralTerrainContent::generate, float-exact: three passes over one grid (category masks
/// 0x33 trees / props / prefabs / buildings, 0x04 decals, 0x08 vfx) sharing one std::mt19937 seeded with the tile's
/// vegetation_seed. Per pass (FUN_180086d30):
///  1. place (FUN_1800870d0): every non-excluded cell gets a jitter (two uniform bytes) and a group drawn by weight among
///     the groups of the channels weighing ≥ 0.05 at that point (group range test on the summed probability channels,
///     slope from a Sobel normal, height), then an object drawn by weight in the group (object range test on the group
///     channel, height); a single candidate is taken without a draw
///  2. resolve (FUN_1800872d0): keys (object separation &amp; 0x3f, column, x jitter, cell) sorted; ascending, grouping
///     converts neighbours inside the group's grouping radius (with its probability); descending, separation clears
///     same-channel neighbours inside the object's minimum separation (a "small object" neighbour uses its own)
///  3. emit: every placed, non-empty object, in cell order, with scale = low + range · u and yaw = 2π · u
/// Cell entry bits 0-10: group (0x7fe excluded, 0x7ff free), bits 11-15: object in the group. Three float orders for
/// cell positions are kept as BOB has them (<see cref="PosA"/>, <see cref="PosB"/>, <see cref="PosC"/>).
/// Matches BOB's instances bit for bit on the round-2 corpus (Frida dumps).
/// </summary>
public sealed class ProceduralGenerator
{
    private const float K255 = 0.003921568859368563f;
    private const float Threshold = 0.05f;
    private const float HeightScale = 0.15259021520614624f, HeightOffset = 5000f;
    private const float ProbScale = 0.00015259021893143654f;
    private const float TwoPi = 6.2831854820251465f;
    private const ushort Excluded = 0x7fe, Free = 0x7ff;
    private static readonly float[] Sobel = [1, 0, -1, 2, 0, -2, 1, 0, -1];

    private readonly ProceduralTables _t;
    private readonly float[] _height;       // composited height, w x h
    private readonly float[] _blend;        // composited Blend8, 8 floats per pixel
    private readonly int _w, _h;
    private readonly Mt19937 _rng;
    private readonly ushort[] _entry;
    private readonly byte[] _jx, _jz;
    private int _mask;
    private readonly float _invPix;
    private readonly float[] _w8 = new float[8];

    // decoded tables
    private readonly int[] _gProb, _gFirst, _gCount, _gMask, _gChan, _gLo, _gHi, _gFall, _gHLo, _gHHi, _gHFall, _gSMax, _gSMin, _gGp, _gGr;
    private readonly int[] _oProb, _oRad, _oFlags, _oLo, _oHi, _oFall, _oHLo, _oHHi, _oHFall;

    public ProceduralGenerator(ProceduralTables tables, float[] height, float[] blend, int width, int height_, uint seed)
    {
        _t = tables;
        _height = height;
        _blend = blend;
        _w = width;
        _h = height_;
        _rng = new Mt19937(seed);
        var n = tables.Nx * tables.Ny;
        _entry = new ushort[n];
        Array.Fill(_entry, Free);
        _jx = new byte[n];
        _jz = new byte[n];
        _invPix = 1f / tables.Pixel;
        var g = tables.Groups;
        int G(int i, int at) => g[i][at];
        int G16(int i, int at) => g[i][at] | g[i][at + 1] << 8;
        _gProb = Arr(g.Length, i => G16(i, 0)); _gFirst = Arr(g.Length, i => G16(i, 2)); _gCount = Arr(g.Length, i => G(i, 4));
        _gMask = Arr(g.Length, i => G(i, 5)); _gChan = Arr(g.Length, i => (sbyte)g[i][6]);
        _gLo = Arr(g.Length, i => G(i, 7)); _gHi = Arr(g.Length, i => G(i, 8)); _gFall = Arr(g.Length, i => G(i, 9));
        _gHLo = Arr(g.Length, i => G16(i, 10)); _gHHi = Arr(g.Length, i => G16(i, 12)); _gHFall = Arr(g.Length, i => G16(i, 14));
        _gSMax = Arr(g.Length, i => G(i, 16)); _gSMin = Arr(g.Length, i => G(i, 17));
        _gGp = Arr(g.Length, i => G(i, 18)); _gGr = Arr(g.Length, i => G(i, 19));
        var o = tables.Objects;
        int O(int i, int at) => o[i][at];
        int O16(int i, int at) => o[i][at] | o[i][at + 1] << 8;
        _oProb = Arr(o.Length, i => O(i, 0)); _oRad = Arr(o.Length, i => O(i, 1)); _oFlags = Arr(o.Length, i => O(i, 2));
        _oLo = Arr(o.Length, i => O(i, 3)); _oHi = Arr(o.Length, i => O(i, 4)); _oFall = Arr(o.Length, i => O(i, 5));
        _oHLo = Arr(o.Length, i => O16(i, 6)); _oHHi = Arr(o.Length, i => O16(i, 8)); _oHFall = Arr(o.Length, i => O16(i, 10));
    }

    private static int[] Arr(int n, Func<int, int> f)
    {
        var a = new int[n];
        for (var i = 0; i < n; i++) a[i] = f(i);
        return a;
    }

    /// <summary>The three passes' instances.</summary>
    public List<ProceduralInstance>[] Run() => [RunPass(0x33), RunPass(0x04), RunPass(0x08)];

    public List<ProceduralInstance> RunPass(int mask)
    {
        _mask = mask;
        Place();
        Resolve();
        return Emit();
    }

    // ---- positions: BOB computes them in three float orders ----

    /// <summary>FUN_1800e51e0, grouping / separation centres: ((j·k − 0.5) + col) · s + o.</summary>
    private (float X, float Z) PosA(int i)
    {
        int col = i % _t.Nx, row = i / _t.Nx;
        var x = ((_jx[i] * K255 - 0.5f) + col) * _t.Spacing + _t.OriginX;
        var z = ((_jz[i] * K255 - 0.5f) + row) * _t.Spacing + _t.OriginZ;
        return (x, z);
    }

    /// <summary>Emitted instances and the separation neighbours: ((j·k + col) − 0.5) · s + o.</summary>
    private (float X, float Z) PosB(int i)
    {
        int col = i % _t.Nx, row = i / _t.Nx;
        var x = ((_jx[i] * K255 + col) - 0.5f) * _t.Spacing + _t.OriginX;
        var z = ((_jz[i] * K255 + row) - 0.5f) * _t.Spacing + _t.OriginZ;
        return (x, z);
    }

    /// <summary>Grouping neighbours (FUN_1800c4830): x as <see cref="PosB"/>, z as <see cref="PosA"/>.</summary>
    private (float X, float Z) PosC(int i)
    {
        int col = i % _t.Nx, row = i / _t.Nx;
        var x = ((_jx[i] * K255 + col) - 0.5f) * _t.Spacing + _t.OriginX;
        var z = ((_jz[i] * K255 - 0.5f) + row) * _t.Spacing + _t.OriginZ;
        return (x, z);
    }

    // ---- sampling (FUN_1800ed670): the nearest composited pixel, no interpolation ----

    private float Sample(float x, float z, bool slope, out float nz)
    {
        var fx = _invPix * x + _t.OffsetX;
        var fy = _invPix * z + _t.OffsetY;
        int ix = (int)MathF.Floor(fx), iy = (int)MathF.Floor(fy);
        var p = iy * _w + ix;
        Array.Copy(_blend, p * 8, _w8, 0, 8);
        nz = slope ? NormalZ(ix, iy) : -1f;
        return _height[p];
    }

    private float At(int x, int y)
    {
        x = x < 0 ? 0 : x > _w - 1 ? _w - 1 : x;
        y = y < 0 ? 0 : y > _h - 1 ? _h - 1 : y;
        return _height[y * _w + x];
    }

    /// <summary>FUN_1800dc460: Sobel gradients (FUN_1800bf7d0 / bf4e0) of height · (1/unit scale), z = 1, normalised; the
    /// normal's z (cos of the slope).</summary>
    private float NormalZ(int x, int y)
    {
        var sc = _t.InvUnitScale;
        float ga = 0f, gb = 0f;
        for (var j = 0; j < 3; j++)
            for (var i = 0; i < 3; i++)
            {
                var v = sc * At(x - 1 + i, y - 1 + j);
                ga += v * Sobel[3 * i + j];
                gb += v * Sobel[3 * j + i];
            }
        ga /= 8f;
        gb /= 8f;
        const float f4 = 1f;
        var inv = 1f / MathF.Sqrt(gb * gb + ga * ga + f4 * f4);
        return f4 * inv;
    }

    private static float HeightValue(int u) => u * HeightScale - HeightOffset;

    /// <summary>The shared range test: 1 inside [low, high], linear falloff outside, NaN when out (BOB's "0").</summary>
    private static float Falloff(float low, float high, float fall, float v)
    {
        var f = low - v;
        if (!(f <= fall)) return float.NaN;
        if (f <= 0f)
        {
            f = v - high;
            if (f < 0f) return 1f;
            if (fall <= f) return float.NaN;
        }
        var r = 1f - f / fall;
        return r == 0f ? float.NaN : r;
    }

    /// <summary>FUN_180087710: the group's weight at a sample.</summary>
    private float GroupWeight(int gi, float h, float nz, bool slope)
    {
        var m = _gMask[gi];
        var s = 0f;
        var first = true;
        for (var b = 0; b < 8; b++)
            if ((m & (1 << b)) != 0)
            {
                s = first ? _w8[b] : s + _w8[b];
                first = false;
            }
        var f5 = _gFall[gi] * K255;
        var f2 = _gLo[gi] * K255 - s;
        if (f5 < f2) return 0f;
        float f3;
        if (f2 <= 0f)
        {
            f2 = s - _gHi[gi] * K255;
            f3 = 1f;
            if (f2 >= 0f)
            {
                if (f5 <= f2) return 0f;
                f3 = 1f - f2 / f5;
                if (f3 == 0f) return 0f;
            }
        }
        else
        {
            f3 = 1f - f2 / f5;
            if (f3 == 0f) return 0f;
        }
        var prob = _gProb[gi] * ProbScale;
        if (!slope) return prob * (0f + f3);
        int smax = _gSMax[gi], smin = _gSMin[gi];
        if ((smax == 0xff && smin == 0) || (nz <= smax * K255 && smin * K255 <= nz))
        {
            var f4 = HeightValue(_gHFall[gi]);
            var f5b = HeightValue(_gHLo[gi]) - h;
            if (f5b <= f4)
            {
                if (f5b <= 0f)
                {
                    f5b = h - HeightValue(_gHHi[gi]);
                    if (f5b < 0f) return prob * (1f + f3);
                    if (f4 <= f5b) return 0f;
                }
                var r = 1f - f5b / f4;
                if (r != 0f) return prob * (r + f3);
            }
        }
        return 0f;
    }

    private readonly List<(float Cum, int Index)> _cands = [];

    /// <summary>FUN_1800874d0: a group drawn by weight; -1 when none.</summary>
    private int ChooseGroup(float h, float nz)
    {
        _cands.Clear();
        var tot = 0f;
        var start = 0;
        for (var ch = 0; ch < 8; ch++)
        {
            int end = _t.ChannelEnds[ch];
            if (Threshold <= _w8[ch])
                for (var gi = start; gi < end; gi++)
                {
                    var v = GroupWeight(gi, h, nz, true);
                    if (v != 0f)
                    {
                        tot += v;
                        _cands.Add((tot, gi));
                    }
                }
            start = end;
        }
        return Pick(tot);
    }

    private int Pick(float tot)
    {
        if (_cands.Count == 0) return -1;
        if (_cands.Count == 1) return _cands[0].Index;
        var r = _rng.Uniform01() * tot;
        foreach (var (cum, idx) in _cands)
            if (!(cum < r)) return idx;
        return _cands[^1].Index;
    }

    /// <summary>FUN_180087920: an object of the group drawn by weight; -1 when none.</summary>
    private int ChooseObject(int gi, float h)
    {
        _cands.Clear();
        var tot = 0f;
        var cw = _w8[_gChan[gi]];
        var first = _gFirst[gi];
        for (var k = 0; k < _gCount[gi]; k++)
        {
            var oi = first + k;
            if ((_oFlags[oi] & _mask & 0x3f) == 0) continue;
            var r1 = Falloff(_oLo[oi] * K255, _oHi[oi] * K255, _oFall[oi] * K255, cw);
            if (float.IsNaN(r1)) continue;
            var r2 = Falloff(HeightValue(_oHLo[oi]), HeightValue(_oHHi[oi]), HeightValue(_oHFall[oi]), h);
            if (float.IsNaN(r2)) continue;
            var p = _oProb[oi] * K255 * (r2 + r1);
            if (p != 0f)
            {
                tot += p;
                _cands.Add((tot, k));
            }
        }
        return Pick(tot);
    }

    // ---- passes ----

    private void Place()
    {
        for (var i = 0; i < _entry.Length; i++)
        {
            if ((_entry[i] & 0x7ff) == Excluded) continue;
            _entry[i] |= Free;
            _jx[i] = (byte)_rng.Byte();
            _jz[i] = (byte)_rng.Byte();
            var (x, z) = PosA(i);
            var h = Sample(x, z, true, out var nz);
            var gi = ChooseGroup(h, nz);
            if (gi < 0) continue;
            var k = ChooseObject(gi, h);
            if (k >= 0) _entry[i] = (ushort)((gi & 0x7ff) | (k << 11));
        }
    }

    private int ObjectIndex(int e) => _gFirst[e & 0x7ff] + (e >> 11);

    private static int CeilDiv(float r, float s)
    {
        var q = r / s;
        var t = (int)q;
        return t == q ? t : t + 1;
    }

    private void Resolve()
    {
        int nx = _t.Nx, ny = _t.Ny;
        var keys = new List<(int Prio, int Col, int Jx, int Cell, int Gp, int Gr)>();
        for (var i = 0; i < _entry.Length; i++)
        {
            var e = _entry[i];
            if ((e & 0x7ff) >= Excluded) continue;
            var gi = e & 0x7ff;
            keys.Add((_oRad[_gFirst[gi] + (e >> 11)] & 0x3f, i % nx, _jx[i], i, _gGp[gi], _gGr[gi]));
        }
        keys.Sort((a, b) => a.Prio != b.Prio ? a.Prio.CompareTo(b.Prio) : a.Col != b.Col ? a.Col.CompareTo(b.Col)
            : a.Jx != b.Jx ? a.Jx.CompareTo(b.Jx) : a.Cell.CompareTo(b.Cell));

        // FUN_1800c3dc0: grouping, ascending
        foreach (var (_, col, _, i, gp, gr) in keys)
        {
            if (gp == 0 || gr == 0) continue;
            if ((_entry[i] & 0x7ff) >= Excluded) continue;
            if (!(_rng.Uniform01() <= gp * K255)) continue;
            var gi = _entry[i] & 0x7ff;
            float r = gr, r2 = r * r;
            var (px, pz) = PosA(i);
            var ir = CeilDiv(r, _t.Spacing);
            var row = i / nx;
            int x0 = Math.Max(col - ir, 0), y0 = Math.Max(row - ir, 0);
            int x1 = Math.Min(col + 1 + ir, nx), y1 = Math.Min(row + 1 + ir, ny);
            for (var yy = y0; yy < y1; yy++)
                for (var xx = x0; xx < x1; xx++)
                {
                    if (xx == col && yy == row) continue;
                    var j = yy * nx + xx;
                    var ej = _entry[j] & 0x7ff;
                    if (ej >= Excluded || ej == (_entry[i] & 0x7ff)) continue;
                    var (qx, qz) = PosC(j);
                    var dz = pz - qz;
                    var d2 = dz * dz + (px - qx) * (px - qx);
                    if (!(d2 <= r2)) continue;
                    var h = Sample(qx, qz, false, out var nz);
                    if (!(Threshold <= _w8[_gChan[gi]])) continue;
                    if (GroupWeight(gi, h, nz, false) == 0f) continue;
                    var k = ChooseObject(gi, h);
                    if (k >= 0) _entry[j] = (ushort)((_entry[i] & 0x7ff) | (k << 11));
                }
        }

        // FUN_1800c4030: separation, descending
        for (var n = keys.Count - 1; n >= 0; n--)
        {
            var (_, col, _, i, _, _) = keys[n];
            var e = _entry[i];
            if ((e & 0x7ff) >= Excluded) continue;
            var gi = e & 0x7ff;
            var oi = ObjectIndex(e);
            float r = _oRad[oi];
            if (r == 0f) continue;
            var ch = _gChan[gi];
            var r2 = r * r;
            var flag = _oFlags[oi] >> 7;
            var (px, pz) = PosA(i);
            var ir = CeilDiv(r, _t.Spacing);
            var row = i / nx;
            int x0 = Math.Max(col - ir, 0), y0 = Math.Max(row - ir, 0);
            int x1 = Math.Min(col + 1 + ir, nx), y1 = Math.Min(row + 1 + ir, ny);
            for (var yy = y0; yy < y1; yy++)
                for (var xx = x0; xx < x1; xx++)
                {
                    var j = yy * nx + xx;
                    if (j == i) continue;
                    var ej = _entry[j];
                    if ((ej & 0x7ff) >= Excluded) continue;
                    var (qx, qz) = PosB(j);
                    var dx = px - qx;
                    var dz = pz - qz;
                    var thr = r2;
                    if (flag == 0)
                    {
                        var oj = ObjectIndex(ej);
                        if ((_oFlags[oj] & 0x80) != 0)
                        {
                            float t = _oRad[oj];
                            thr = t * t;
                        }
                    }
                    if (dz * dz + dx * dx <= thr && _gChan[ej & 0x7ff] == ch) _entry[j] = (ushort)(ej | 0x7ff);
                }
        }
    }

    private List<ProceduralInstance> Emit()
    {
        var outp = new List<ProceduralInstance>();
        for (var i = 0; i < _entry.Length; i++)
        {
            var e = _entry[i];
            if ((e & 0x7ff) >= Excluded) continue;
            var oi = ObjectIndex(e);
            if ((_oFlags[oi] & 0x40) != 0) continue;
            var (x, z) = PosB(i);
            var o = _t.ObjectList[oi];
            var sc = _rng.Uniform01() * o.SizeRange + o.SizeLow;
            var rot = _rng.Uniform01() * TwoPi;
            outp.Add(new ProceduralInstance(oi, x, z, sc, rot));
        }
        return outp;
    }
}
