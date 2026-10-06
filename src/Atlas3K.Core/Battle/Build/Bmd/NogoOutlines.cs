namespace Atlas3K.Core.Battle.Build.Bmd;

/// <summary>
/// The terrain no-go outlines of a battle tile's bmd_nogo_data (empireutility no_go_outlines_from_heights), float32
/// bit for bit (research/battle_build/nogo_outlines.py is the reference prototype; decompiles under
/// Z:/Claude/BattleMaps/research/bob_re/bmd_nogo):
///  1. a cell of the height field is no-go when its normal's y is below sin(90° − 30°) (30 =
///     maximum_passable_slope_angle_degrees, a runtime value read with Frida); central differences, clamped at edges
///  2. BLUR_OUTLINE_DATA_PROVIDER: separable 3-tap triangle blur over [0, w−1) × [0, h−1), > 0.1 → 1; no-go = ≥ 0.5
///  3. OUTLINE_CALCULATOR: marching boundary from start patterns 1 / 9 (move table at 0x18171c250), skipping starts
///     inside outlines already found; outlines whose box is ≤ 6 cells on both axes are dropped
///  4. corners → world: corner · cell size (+ offset 0); the closing point is dropped
///  5. three simplification passes (FUN_180efc6c0): (3×, 0.99, lookahead 10, expand + contract),
///     (1×, 3.0, 4, expand only), (1×, 1.0, 4, expand + contract), each shortcut checked against the outlines' edges
/// Identical to BOB on dfe064a6 and df46bdbc (4 outlines) with the Frida-dumped field (2026-10-06).
/// </summary>
public static class NogoOutlines
{
    public const float MaxPassableSlopeDegrees = 30f;

    public static List<List<(float X, float Y)>> Compute(float[] field, int w, int h, float cell, float offsetX = 0, float offsetY = 0,
                                                      float slopeDegrees = MaxPassableSlopeDegrees)
    {
        var nogo = NogoCells(field, w, h, cell, slopeDegrees);
        var blurred = Blur(nogo, w, h);
        var data = new int[w * h];
        for (var i = 0; i < data.Length; i++) data[i] = blurred[i] >= 0.5f ? 1 : 0;
        var raw = new Calculator(data, w, h).Compute(6);
        var outlines = raw.Select(e => e.Take(e.Count - 1).Select(p => ((float)p.X * cell + offsetX, (float)p.Y * cell + offsetY)).ToList()).ToList();
        Simplify(outlines, 3, 0.99f, 10, true, true);
        Simplify(outlines, 1, 3.0f, 4, true, false);
        Simplify(outlines, 1, 1.0f, 4, true, true);
        return outlines;
    }

    public static bool[] NogoCells(float[] H, int w, int h, float cell, float slopeDegrees)
    {
        var thr = (float)Math.Sin((90f - slopeDegrees) * 0.0174532924f);
        var outp = new bool[w * h];
        var f = cell + cell;
        var f7 = f * f;
        for (var y = 0; y < h; y++)
            for (var x = 0; x < w; x++)
            {
                var c = H[y * w + x];
                var l = x > 0 ? H[y * w + x - 1] : c;
                var r = x < w - 1 ? H[y * w + x + 1] : c;
                var u = y > 0 ? H[(y - 1) * w + x] : c;
                var d = y < h - 1 ? H[(y + 1) * w + x] : c;
                var f6 = (u - d) * f;
                var f5 = (l - r) * f;
                var len = MathF.Sqrt(f7 * f7 + f5 * f5 + f6 * f6);
                var ny = f7 * (1f / len);
                outp[y * w + x] = ny < thr;
            }
        return outp;
    }

    public static float[] Blur(bool[] field, int w, int h, int taps = 3, float threshold = 0.1f)
    {
        var buf1 = new float[w * h];
        for (var i = 0; i < buf1.Length; i++) buf1[i] = field[i] ? 1f : 0f;
        var buf2 = new float[w * h];
        int x1 = w - 1, y1 = h - 1;
        var f = 1f / taps;
        var wts = new float[2 * taps + 1];
        for (var i = -taps; i <= taps; i++) wts[i + taps] = (taps - Math.Abs(i)) * f * f;
        for (var y = 0; y < y1; y++)
            for (var x = 0; x < x1; x++)
            {
                var acc = 0f;
                for (var i = -taps; i <= taps; i++)
                {
                    var xi = Math.Clamp(x + i, 0, x1 - 1);
                    acc += buf1[y * w + xi] * wts[i + taps];
                }
                buf2[y * w + x] = acc;
            }
        for (var y = 0; y < y1; y++)
            for (var x = 0; x < x1; x++)
            {
                var acc = 0f;
                for (var i = -taps; i <= taps; i++)
                {
                    var yi = Math.Clamp(y + i, 0, y1 - 1);
                    acc += buf2[yi * w + x] * wts[i + taps];
                }
                buf1[y * w + x] = acc > threshold ? 1f : 0f;
            }
        return buf1;
    }

    // move table (empireutility 0x18171c250): move x/y, three corner offsets, cells to mark (bit 1: x,y; 2: x-1,y;
    // 4: x,y-1; 8: x-1,y-1)
    private static readonly Dictionary<int, (int Mx, int My, (int, int) P1, (int, int) P2, (int, int) P3, int Mark)> Table = new()
    {
        [0] = (1, 0, (0, 0), (0, 0), (0, 0), 0),
        [1] = (1, 0, (-1, 0), (-1, -1), (0, -1), 1),
        [2] = (0, 1, (-2, -1), (-1, -1), (-1, 0), 2),
        [3] = (1, 0, (-2, -1), (-1, -1), (0, -1), 3),
        [4] = (0, -1, (0, -1), (-1, -1), (-1, -2), 4),
        [5] = (0, -1, (-1, 0), (-1, -1), (-1, -2), 5),
        [6] = (0, 1, (-2, -1), (-1, -1), (-1, 0), 2),
        [7] = (0, -1, (-2, -1), (-1, -1), (-1, -2), 7),
        [8] = (-1, 0, (-1, -2), (-1, -1), (-2, -1), 8),
        [9] = (-1, 0, (-1, -2), (-1, -1), (-2, -1), 8),
        [10] = (0, 1, (-1, -2), (-1, -1), (-1, 0), 10),
        [11] = (1, 0, (-1, -2), (-1, -1), (0, -1), 11),
        [12] = (-1, 0, (0, -1), (-1, -1), (-2, -1), 12),
        [13] = (-1, 0, (-1, 0), (-1, -1), (-2, -1), 13),
        [14] = (0, 1, (0, -1), (-1, -1), (-1, 0), 14),
        [16] = (0, -1, (0, -1), (-1, -1), (-1, -2), 4),
        [17] = (1, 0, (-1, 0), (-1, -1), (0, -1), 1),
    };

    /// <summary>UTILITYLIB::OUTLINE_CALCULATOR::compute_outlines.</summary>
    private sealed class Calculator(int[] data, int w, int h)
    {
        private int _sx, _sy;
        private readonly List<(int X0, int Y0, int X1, int Y1)> _boxes = [];

        private int Get(int x, int y) => data[y * w + x];

        private int Pattern(int x, int y)
        {
            var b = 0;
            if (y < h)
            {
                if (x < w && Get(x, y) != 0) b = 1;
                if (x != 0 && x - 1 < w && Get(x - 1, y) != 0) b |= 2;
            }
            if (y != 0 && y - 1 < h)
            {
                if (x != 0 && x - 1 < w && Get(x - 1, y - 1) != 0) b |= 8;
                if (x < w && Get(x, y - 1) != 0) b |= 4;
            }
            return b;
        }

        private bool Scan()
        {
            while (_sy < h)
            {
                var x = _sx;
                while (x < w)
                {
                    if (Get(x, _sy) == 1)
                    {
                        var p = Pattern(x, _sy);
                        if (p == 1 || (p == 9 && Get(x - 1, _sy - 1) > 1)) { _sx = x; return true; }
                    }
                    x++;
                    _sx = x;
                }
                _sy++;
                _sx = 0;
            }
            return false;
        }

        private static void AddPoint(List<(int X, int Y)> e, (int X, int Y) p, ref bool closed)
        {
            if (closed) return;
            if (e.Count > 0 && e[0] == p) closed = true;
            if (e.Count < 3) { e.Add(p); return; }
            var a = e[^2];
            var b = e[^1];
            if (a.X == b.X && b.X == p.X) { if (p.Y != b.Y) e[^1] = (b.X, p.Y); return; }
            if (a.Y == b.Y && b.Y == p.Y) { if (p.X != b.X) e[^1] = (p.X, b.Y); return; }
            e.Add(p);
        }

        /// <summary>OUTLINE_DATA_CONTAINER::is_point_inside_outline over the outlines found so far.</summary>
        private bool InsideExisting(int x, int y, List<List<(int X, int Y)>> outlines)
        {
            for (var k = 0; k < outlines.Count; k++)
            {
                var (x0, y0, x1, y1) = _boxes[k];
                if (x < x0 || x > x1 || y < y0 || y > y1) continue;
                var e = outlines[k];
                bool inside = false, onEdge = false;
                for (var i = 0; i < e.Count - 1; i++)
                {
                    var a = e[i];
                    var b = i == e.Count - 2 ? e[0] : e[i + 1];
                    if (a.X == b.X)
                    {
                        int lo = Math.Min(a.Y, b.Y), hi = Math.Max(a.Y, b.Y);
                        if (a.X < x) { if (lo <= y && y < hi) inside = !inside; }
                        else if (x == a.X && lo <= y && y <= hi) { onEdge = true; break; }
                    }
                    else if (y == a.Y && Math.Min(a.X, b.X) <= x && x <= Math.Max(a.X, b.X)) { onEdge = true; break; }
                }
                if (inside && !onEdge) return true;
            }
            return false;
        }

        public List<List<(int X, int Y)>> Compute(int minSize)
        {
            var outlines = new List<List<(int X, int Y)>>();
            _sx = _sy = 0;
            var label = 2;
            var maxCount = (w * h) >> 2;
            var found = Scan();
            while (found)
            {
                if (InsideExisting(_sx, _sy, outlines))
                {
                    _sx++;
                    found = Scan();
                    continue;
                }
                int x = _sx, y = _sy, px = x, py = y, prev = 0;
                int mnx = x, mny = y, mxx = x, mxy = y;
                var edges = new List<(int X, int Y)>();
                var closed = false;
                var count = 0;
                while (true)
                {
                    var pat = Pattern(x, y);
                    var e = pat;
                    if (pat == 9) { if (prev == 0 || y < py) e = 17; }
                    else if (pat == 6) { if (x < px) e = 16; }
                    var (mx, my, p1, p2, p3, mark) = Table[e];
                    if (!closed)
                    {
                        (int, int) q1 = (x + 1 + p1.Item1, y + 1 + p1.Item2), q2 = (x + 1 + p2.Item1, y + 1 + p2.Item2),
                                   q3 = (x + 1 + p3.Item1, y + 1 + p3.Item2);
                        if (edges.Count < 3)
                        {
                            AddPoint(edges, q1, ref closed);
                            AddPoint(edges, q2, ref closed);
                            AddPoint(edges, q3, ref closed);
                        }
                        else
                        {
                            if (q1 != edges[^2] && q2 != edges[^1])
                            {
                                AddPoint(edges, q1, ref closed);
                                AddPoint(edges, q2, ref closed);
                            }
                            AddPoint(edges, q3, ref closed);
                        }
                    }
                    if ((mark & 1) != 0) data[y * w + x] = label;
                    if ((mark & 2) != 0) data[y * w + x - 1] = label;
                    if ((mark & 4) != 0) data[(y - 1) * w + x] = label;
                    if ((mark & 8) != 0) data[(y - 1) * w + x - 1] = label;
                    px = x; py = y; prev = pat;
                    x += mx; y += my;
                    mnx = Math.Min(mnx, x); mny = Math.Min(mny, y); mxx = Math.Max(mxx, x); mxy = Math.Max(mxy, y);
                    count++;
                    if (closed || count >= maxCount) break;
                }
                if (count != maxCount && !(minSize > 0 && mxx - mnx <= minSize && mxy - mny <= minSize))
                {
                    outlines.Add(edges);
                    _boxes.Add((mnx, mny, mxx, mxy));
                }
                label++;
                _sx++;
                found = Scan();
            }
            return outlines;
        }
    }

    // ---- simplification (FUN_180efc6c0 / FUN_180efa230 / FUN_180efb820) ----

    private static bool SegHits((float X0, float Y0, float X1, float Y1) s, (float X, float Y) a, (float X, float Y) b)
    {
        float f16 = s.X1 - s.X0, f17 = s.Y1 - s.Y0;
        var d = (b.X - a.X) * f17 - (b.Y - a.Y) * f16;
        if (!(MathF.Abs(d) > 0)) return false;
        float f18 = a.X - s.X0, f19 = a.Y - s.Y0, inv = 1f / d;
        var t = (f19 * f16 - f18 * f17) * inv;
        if (!(0 <= t && t <= 1)) return false;
        var u = ((b.X - a.X) * f19 - (b.Y - a.Y) * f18) * inv;
        return 0 <= u && u <= 1 && t != 0 && t != 1;
    }

    private static bool SegHitsNew((float X0, float Y0, float X1, float Y1) s, (float X, float Y) a, (float X, float Y) b)
    {
        var d = (s.Y1 - s.Y0) * (b.X - a.X) - (s.X1 - s.X0) * (b.Y - a.Y);
        if (!(MathF.Abs(d) > 0)) return false;
        var inv = 1f / d;
        var t = ((s.X1 - s.X0) * (a.Y - s.Y0) - (s.Y1 - s.Y0) * (a.X - s.X0)) * inv;
        if (!(0 <= t && t <= 1)) return false;
        var u = ((b.X - a.X) * (a.Y - s.Y0) - (b.Y - a.Y) * (a.X - s.X0)) * inv;
        return 0 <= u && u <= 1 && t != 0 && t != 1;
    }

    private static bool ShortcutOk(List<List<(float X, float Y)>> outlines, int k, int j, List<(float X, float Y)> made)
    {
        var s = (made[^1].X, made[^1].Y, outlines[k][j].X, outlines[k][j].Y);
        for (var o = 0; o < outlines.Count; o++)
        {
            var pts = outlines[o];
            if (o == k)
                for (var m = 0; m + 1 < made.Count; m++)
                    if (SegHitsNew(s, made[m], made[m + 1])) return false;
            var n = pts.Count;
            if (n > 1 && j < n)
                for (var e = j; e < n; e++)
                    if (SegHits(s, pts[e], e == n - 1 ? pts[0] : pts[e + 1])) return false;
        }
        return true;
    }

    private static void Simplify(List<List<(float X, float Y)>> outlines, int iterations, float err, int lookahead, bool expand, bool contract)
    {
        var done = new bool[outlines.Count];
        for (var it = 0; it < iterations; it++)
            for (var k = 0; k < outlines.Count; k++)
            {
                if (done[k]) continue;
                var pts = outlines[k];
                var n = pts.Count;
                var made = new List<(float X, float Y)>();
                var i = 0;
                while (i < n)
                {
                    var p = pts[i];
                    made.Add(p);
                    int best = -1, count = 0;
                    var bestErr = err + err;
                    for (var j = i + 2; j < n - 1; j++)
                    {
                        if (count >= lookahead) break;
                        var q = pts[j];
                        float dx = q.X - p.X, dy = q.Y - p.Y;
                        var segLen = MathF.Sqrt(dy * dy + dx * dx);
                        var maxd = 0f;
                        var fail = false;
                        for (var m = i + 1; m < j; m++)
                        {
                            var r = pts[m];
                            float rx = r.X - p.X, ry = r.Y - p.Y;
                            float t;
                            if (segLen <= 0) t = 0;
                            else
                            {
                                var inv = 1f / segLen;
                                t = ry * inv * dy * inv + rx * inv * dx * inv;
                                if (!(t >= 0)) t = 0;
                            }
                            if (t >= 1) t = 1;
                            float ex = dx * t + p.X - r.X, ey = dy * t + p.Y - r.Y;
                            var dist = MathF.Sqrt(ey * ey + ex * ex);
                            if (maxd <= dist) maxd = dist;
                            if (err <= dist) break;
                            var side = dy * rx - dx * ry > 0;
                            if ((!contract && side) || (!expand && !side)) { fail = true; break; }
                        }
                        if (!(fail || err <= maxd || bestErr < maxd)) { best = j; bestErr = maxd; }
                        count++;
                    }
                    i = best != -1 && ShortcutOk(outlines, k, best, made) ? best : i + 1;
                }
                if (made.Count > 2)
                {
                    if (made.Count == n) done[k] = true;
                    outlines[k] = made;
                }
            }
    }
}
