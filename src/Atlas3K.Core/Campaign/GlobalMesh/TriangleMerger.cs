namespace Atlas3K.Core.Campaign.GlobalMesh;

/// <summary>
/// BOB's TRIANGLE_MERGER (tooldatabuilder rigidmodel_optimise.cpp), a vertex-removal decimator. See
/// docs/bob_re_global_mesh.md. Per pass k (edge limit L = k · span / N, N = min(span/6, 50) passes, 4 stagnant passes
/// end it) every vertex v in index order with flag ≥ 2 whose neighbours' normals are all within the factor collapses
/// into the nearest neighbour w (x/z distance) that keeps every rewired triangle non-sliver, within L and correctly
/// wound. Flags: 0 pinned, 2 free, 3 slides only onto 3/0 (map edges).
/// </summary>
public sealed class TriangleMerger
{
    private readonly float[] _x, _y, _z;
    private readonly float[] _n; // 3 per vertex
    private readonly byte[] _flags;

    /// <summary>Research: per-pass / per-vertex trace lines in the format of research/bob_re/frida_gmerge_trace.js.</summary>
    public Action<string>? Trace { get; init; }

    public TriangleMerger(float[] x, float[] y, float[] z, float[] normals, byte[] flags)
    {
        _x = x; _y = y; _z = z; _n = normals; _flags = flags;
    }

    public List<int[]> Run(List<int[]> triangles, float factor, float span = 64f, float heightTolerance = float.MaxValue)
    {
        // FUN_18009b4d0 is max: 50 passes of 64/50 = 1.28 (BOB trace, main190)
        var passes = Math.Max((int)(span * (1f / 6f)), 50);
        var step = span / passes;
        var current = triangles.Select(t => (int[])t.Clone()).ToList();
        int stall = 0, k = 0, multiplier = 1;
        var nv = _x.Length;
        while (k < passes)
        {
            var limit = multiplier * step;
            var limit2 = limit * limit;
            var tri = current;
            Trace?.Invoke($"pass limit {limit.ToString("R", System.Globalization.CultureInfo.InvariantCulture)} tris {tri.Count * 3}");
            var adj = new List<int>[nv];
            for (var t = 0; t < tri.Count; t++)
                foreach (var c in tri[t]) (adj[c] ??= []).Add(t);

            for (var v = 0; v < nv; v++)
            {
                if (_flags[v] < 2 || adj[v] is null) continue;
                var removable = Removable(v, tri, adj[v], factor, heightTolerance);
                Trace?.Invoke($"rem v {v} {(removable ? 1 : 0)}");
                if (!removable) continue;
                var target = Target(v, tri, adj, limit2);
                if (target < 0) continue;
                (adj[target] ??= []).AddRange(adj[v]);
                adj[v] = [];
                foreach (var t in adj[target])
                {
                    var tr = tri[t];
                    for (var q = 0; q < 3; q++) if (tr[q] == v) tr[q] = target;
                    if (Degenerate(tr)) { tr[0] = tr[1] = tr[2] = 0; }
                }
            }
            var next = tri.Where(t => !Degenerate(t)).ToList();
            if (next.Count == current.Count && ++stall > 3)
            {
                k += 10; multiplier += 10; stall = 0;
            }
            current = next;
            k++; multiplier++;
        }
        return current;
    }

    private static bool Degenerate(int[] t) => t[0] == t[1] || t[0] == t[2] || t[1] == t[2];

    private float Dot(int a, int b) =>
        _n[a * 3 + 1] * _n[b * 3 + 1] + _n[a * 3] * _n[b * 3] + _n[a * 3 + 2] * _n[b * 3 + 2];

    private bool Removable(int v, List<int[]> tri, List<int> adj, float factor, float tolerance)
    {
        foreach (var ti in adj)
        {
            var t = tri[ti];
            if (Degenerate(t)) continue;
            int a, b;
            if (t[0] == v) { a = t[1]; b = t[2]; }
            else if (t[1] == v) { a = t[0]; b = t[2]; }
            else if (t[2] == v) { a = t[0]; b = t[1]; }
            else continue;
            foreach (var w in (ReadOnlySpan<int>)[a, b])
            {
                if (MathF.Abs(Dot(v, w)) < factor) return false;
                if (_flags[v] != 4 && _flags[w] is not 1 and not 4 && MathF.Abs(_y[w] - _y[v]) > tolerance) return false;
            }
        }
        return true;
    }

    private int Target(int v, List<int[]> tri, List<int>?[] adj, float limit2)
    {
        var candidates = new List<int>();
        foreach (var ti in adj[v]!)
        {
            var t = tri[ti];
            if (Degenerate(t)) continue;
            foreach (var w in t)
                if (w != v && CanCollapse(v, w, tri, adj, limit2)) candidates.Add(w);
        }
        float vx = _x[v], vz = _z[v];
        if (Trace is not null)
        {
            // stable insertion sort by squared x/z distance, as BOB's (n <= 32)
            var sorted = candidates.OrderBy(w => Dist2(w, vx, vz)).ToList();
            Trace($"cand v {v} ok {(candidates.Count > 0 ? 1 : 0)} target {(sorted.Count > 0 ? sorted[0] : 0)} n {candidates.Count} [{string.Join(",", sorted)}]");
        }
        if (candidates.Count == 0) return -1;
        // stable ordering by squared x/z distance (MSVC insertion sort for small lists)
        var best = candidates[0];
        var bestD = Dist2(best, vx, vz);
        for (var i = 1; i < candidates.Count; i++)
        {
            var d = Dist2(candidates[i], vx, vz);
            if (d < bestD) { best = candidates[i]; bestD = d; }
        }
        return best;
    }

    private float Dist2(int w, float vx, float vz)
    {
        var dz = _z[w] - vz;
        var dx = _x[w] - vx;
        return dz * dz + dx * dx;
    }

    private bool CanCollapse(int v, int w, List<int[]> tri, List<int>?[] adj, float limit2)
    {
        var fv = _flags[v];
        var fw = _flags[w];
        if (fv == 0) return false;
        if (fv == 3 && fw is not 3 and not 0) return false;
        if (fv == 4 && fw is not 4 and not 1) return false;
        foreach (var u in (ReadOnlySpan<int>)[v, w])
        {
            if (adj[u] is null) continue;
            foreach (var ti in adj[u]!)
            {
                var t = tri[ti];
                if (Degenerate(t)) continue;
                var a = t[0] == v ? w : t[0];
                var b = t[1] == v ? w : t[1];
                var c = t[2] == v ? w : t[2];
                var degenerate = a == b || a == c || b == c;
                if (fw > 1 && degenerate && Math.Min(_flags[a], Math.Min(_flags[b], _flags[c])) < 2) return false;
                if (degenerate) continue;
                if (Sliver(a, b, c) || BadShape(a, b, c, limit2)) return false;
            }
        }
        return true;
    }

    /// <summary>FUN_1800cf140: nearly collinear in x/z (|cross of the normalised edges| &lt; 0.1).</summary>
    private bool Sliver(int a, int b, int c)
    {
        if ((_z[a] == _z[b] && _z[b] == _z[c]) || (_x[a] == _x[b] && _x[b] == _x[c])) return true;
        var cx = _x[c] - _x[a]; var cz = _z[c] - _z[a];
        var bx = _x[b] - _x[a]; var bz = _z[b] - _z[a];
        var lac = cz * cz + cx * cx;
        var lab = bz * bz + bx * bx;
        if (lac == 0 || lab == 0) return true;
        var iab = 1f / MathF.Sqrt(lab);
        var iac = 1f / MathF.Sqrt(lac);
        return MathF.Abs(iac * cx * bz * iab - iac * cz * bx * iab) < 0.1f;
    }

    /// <summary>FUN_1800cf290: an edge longer than the pass limit, or the wrong winding in x/z.</summary>
    private bool BadShape(int a, int b, int c, float limit2)
    {
        float abx = _x[b] - _x[a], abz = _z[b] - _z[a];
        float acx = _x[c] - _x[a], acz = _z[c] - _z[a];
        float bcx = _x[c] - _x[b], bcz = _z[c] - _z[b];
        if (abz * abz + abx * abx <= limit2 && acz * acz + acx * acx <= limit2 && bcx * bcx + bcz * bcz <= limit2)
            return (_z[c] - _z[a]) * (_x[b] - _x[a]) - (_z[b] - _z[a]) * (_x[c] - _x[a]) > 0;
        return true;
    }
}
