using Atlas3K.Core.Campaign.GlobalMesh;

namespace Atlas3K.Core.Battle.Build.Meshes;

/// <summary>
/// BOB's battle tile terrain mesh (tooldatabuilder FUN_1800d9c60, called by FUN_1800edbf0 from
/// TOOLDATABUILDER::process_tile_internal for "Process Terry tile (heightmap)"). One LOD for battle tiles. Decompiles:
/// Z:\Claude\BattleMaps\research\bob_re\tile_mesh*; notes in docs/native_battle_build.md.
///
/// <para>Grid: one vertex per height-field sample, (c·f, h[r,c], r·f) with f = 128 / density, numbered r·W + c.
/// Quads at a step of 1 (mesh) or 16 (outfield and shadow: lod shift (density == 128) + 3), each [a, b, c] [b, d, c]
/// with a = (r, c), b = (r+s, c), c = (r, c+s), d = (r+s, c+s).</para>
/// <para>Flags (merger): 0 where a vertex's ±step neighbourhood leaves the tile's cells (the outer step-band and, at
/// step 1, the last row/column before the edge), on the fixed-vertex lattice (infield_fixed_vertex_interval 16 /
/// outfield_fixed_vertex_interval 2048), at the corners and under the protection map (mesh only); else 2.</para>
/// <para>Skirts (FUN_1800dcf00, unmasked tiles): the four edges copied 10 lower, appended top, bottom, left, right,
/// each joined to its edge by two triangles per step; skirt flags 1 on the lattice and at corners, else 4.</para>
/// <para>Then <see cref="TriangleMerger"/> (span 120, height tolerance 3, factor cos(angle factor 0)), first-use
/// renumbering (VERTEX_LIST_CLEANER), MESH_SPLITTER, and "Sort fringes" (triangles touching a skirt vertex last).
/// The shadow mesh keeps only triangles steeper than shadow_mesh_angle (90°): none on a height field.</para>
/// </summary>
public static class BattleTileMeshBuilder
{
    public enum Mode { Mesh = 0, Outfield = 1, Shadow = 2 }

    /// <summary>BOB's settings defaults (bob_tile FUN_18001ac60: infield_fixed_vertex_interval / outfield_fixed_vertex_interval).</summary>
    public const int InfieldFixedVertexInterval = 16, OutfieldFixedVertexInterval = 0x800;
    /// <summary>The skirt depth (DAT_18044cea4).</summary>
    public const float SkirtDepth = 10f;
    /// <summary>TRIANGLE_MERGER::process span and height tolerance for tiles (FUN_1800d9c60: 120.0, 3.0).</summary>
    public const float MergeSpan = 120f, MergeTolerance = 3f;

    public sealed record Result(List<(float X, float Y, float Z)> Positions, List<int> Indices, int MainIndexCount);

    /// <param name="field">The tile height field, row-major (see <see cref="TerryTileProject.HeightField"/>).</param>
    /// <param name="tilesW">Tile size in cells (TILE_DATABASE_TILE width/height).</param>
    /// <param name="angleFactor">conversion_params triangle_decimation_angle_factors0 (degrees).</param>
    /// <param name="protection">The protection map (mesh only), or null.</param>
    public static Result Build(float[] field, int w, int h, int density, int tilesW, int tilesH, float normalStrength,
                               Mode mode, float angleFactor, bool optimise = true, Func<int, int, bool>? cellValid = null,
                               (float[] Values, int W, int H)? protection = null)
    {
        if (mode == Mode.Shadow) return new Result([], [], 0);
        var coarse = mode != Mode.Mesh;
        var lodShift = coarse ? (density == 0x80 ? 1 : 0) + 3 : 0;
        var spacing = coarse ? OutfieldFixedVertexInterval : InfieldFixedVertexInterval;
        var edgeLattice = coarse ? 0x800 : 8;
        var f = 128f / density;
        cellValid ??= (cx, cy) => cx >= 0 && cy >= 0 && cx < tilesW && cy < tilesH;

        var n = w * h;
        var x = new List<float>(n + 4 * w);
        var y = new List<float>(n + 4 * w);
        var z = new List<float>(n + 4 * w);
        var flags = new List<byte>(n + 4 * w);
        var fringe = new List<bool>(n + 4 * w);
        var step = Math.Min(Math.Min(1 << lodShift, w), h);
        for (var r = 0; r < h; r++)
            for (var c = 0; c < w; c++)
            {
                x.Add(c * f);
                y.Add(field[r * w + c]);
                z.Add(r * f);
                fringe.Add(false);
                flags.Add(GridFlag(r, c, w, h, density, step, spacing, edgeLattice, cellValid));
            }
        if (mode == Mode.Mesh && protection is { } p)
            for (var r = 0; r < h; r++)
                for (var c = 0; c < w; c++)
                {
                    var pr = p.H - r - 1;
                    if (pr >= 0 && c < p.W && pr < p.H && p.Values[pr * p.W + c] > 0.5f) flags[r * w + c] = 0;
                }
        var normals = Normals(field, w, h, normalStrength);

        // quads (FUN_1800d9c60): the last quad of a row/column stretches to the edge
        var tris = new List<int[]>();
        if (h != step)
            for (var r = 0; r < h - step; r += step)
            {
                var vs = r + step < h - step ? step : h - r - 1;
                for (var c = 0; c < w - step; c += step)
                {
                    var hs = c + step < w - step ? step : w - c - 1;
                    int a = r * w + c, b = (r + vs) * w + c, cc = a + hs, d = b + hs;
                    tris.Add([a, b, cc]);
                    tris.Add([b, d, cc]);
                }
            }

        // skirts (FUN_1800dcf00, unmasked branch)
        int AddCopy(int src)
        {
            x.Add(x[src]); y.Add(y[src] - SkirtDepth); z.Add(z[src]); fringe.Add(true);
            var nv = normals.Length / 3;
            Array.Resize(ref normals, (nv + 1) * 3);
            normals[nv * 3] = normals[src * 3]; normals[nv * 3 + 1] = normals[src * 3 + 1]; normals[nv * 3 + 2] = normals[src * 3 + 2];
            return x.Count - 1;
        }
        var s = Math.Min(Math.Min(1 << lodShift, w), h);
        var s0 = x.Count;
        for (var i = 0; i < w; i++) AddCopy(i);
        if (w != s)
            for (var i = 0; i < w - s; i += s)
            {
                tris.Add([i, i + s, s0 + i]);
                tris.Add([i + s, s0 + i + s, s0 + i]);
            }
        var s1 = x.Count;
        var bottom = (h - 1) * w;
        for (var i = 0; i < w; i++) AddCopy(bottom + i);
        if (w != s)
            for (var i = s; i < w; i += s)
            {
                tris.Add([bottom + i, bottom + i - s, s1 + i - s]);
                tris.Add([bottom + i, s1 + i - s, s1 + i]);
            }
        var s2 = x.Count;
        for (var j = 0; j < h; j++) AddCopy(j * w);
        if (h != s)
            for (var j = 0; j < h - s; j += s)
            {
                tris.Add([j * w, s2 + j, (j + s) * w]);
                tris.Add([(j + s) * w, s2 + j, s2 + j + s]);
            }
        var s3 = x.Count;
        for (var j = 1; j <= h; j++) AddCopy(j * w - 1);
        if (h != s)
            for (var j = 0; j < h - s; j += s)
            {
                tris.Add([j * w + w - 1, (j + s) * w + w - 1, s3 + j]);
                tris.Add([(j + s) * w + w - 1, s3 + j + s, s3 + j]);
            }
        // flags of the added vertices (FUN_1800d9c60 after FUN_1800dcf00): 1 on the lattice / at a corner, else 4
        for (var v = n; v < x.Count; v++)
        {
            var vx = (int)(uint)x[v];
            var vz = (int)(uint)z[v];
            var off = vx < 0 || vx > w - 1 || vz < 0 || vz > h - 1 || vx % spacing != 0 || vz % spacing != 0;
            var corner = (vx == 0 || vx == w - 1) && (vz == 0 || vz == h - 1);
            flags.Add(off && !corner ? (byte)4 : (byte)1);
        }

        List<int[]> merged;
        if (optimise)
        {
            var factor = MathF.Cos(angleFactor * 0.017453292f);
            merged = new TriangleMerger([.. x], [.. y], [.. z], normals, [.. flags]).Run(tris, factor, MergeSpan, MergeTolerance);
        }
        else merged = tris;

        // VERTEX_LIST_CLEANER: first-use renumbering
        var remap = new Dictionary<int, int>();
        var positions = new List<(float, float, float)>();
        var isFringe = new List<bool>();
        var indices = new List<int>(merged.Count * 3);
        foreach (var t in merged)
            foreach (var q in t)
            {
                if (!remap.TryGetValue(q, out var id))
                {
                    id = remap.Count;
                    remap.Add(q, id);
                    positions.Add((x[q], y[q], z[q]));
                    isFringe.Add(fringe[q]);
                }
                indices.Add(id);
            }
        // Sort fringes: triangles touching a skirt vertex move to the end, in order
        var main = new List<int>(indices.Count);
        var tail = new List<int>();
        for (var t = 0; t < indices.Count; t += 3)
        {
            var target = isFringe[indices[t]] || isFringe[indices[t + 1]] || isFringe[indices[t + 2]] ? tail : main;
            target.Add(indices[t]); target.Add(indices[t + 1]); target.Add(indices[t + 2]);
        }
        var mainCount = main.Count;
        main.AddRange(tail);
        return new Result(positions, main, mainCount);
    }

    private static byte GridFlag(int row, int col, int w, int h, int density, int step, int spacing, int edgeLattice,
                                 Func<int, int, bool> valid)
    {
        static int Floor(float v) => (int)MathF.Floor(v);
        var bad = !valid(Floor((col - (float)step) / density), row / density)
                  || !valid(Floor((step + col) / (float)density), row / density)
                  || !valid(col / density, Floor((step + row) / (float)density))
                  || !valid(col / density, Floor((row - (float)step) / density));
        var lattice = bad ? 1 : spacing;
        byte flag = bad ? (byte)0 : (byte)2;
        var edge = col == 0 || row == 0 || col == w - 1 || row == h - 1;
        if ((col == 0 || col == w - 1) && (row == 0 || row == h - 1)) return 0;
        if (col % lattice == 0 && row % lattice == 0) return 0;
        if (edge && col % edgeLattice == 0 && row % edgeLattice == 0) return 0;
        return edge ? (byte)3 : flag;
    }

    /// <summary>FUN_180147380: Sobel gradients over the height field (FUN_180134080 / FUN_180134370, ÷8, clamped at
    /// the border), normal = normalise(gx, gy, 1 / normal_strength). Three floats per vertex.</summary>
    public static float[] Normals(float[] hgt, int w, int h, float normalStrength)
    {
        int[] k = [1, 0, -1, 2, 0, -2, 1, 0, -1];
        var up = 1f / normalStrength;
        var normals = new float[w * h * 3];
        for (var j = 0; j < h; j++)
            for (var i = 0; i < w; i++)
            {
                float gx = 0, gy = 0;
                for (var r = 0; r < 3; r++)
                    for (var c = 0; c < 3; c++)
                    {
                        var v = hgt[Math.Clamp(j + r - 1, 0, h - 1) * w + Math.Clamp(i + c - 1, 0, w - 1)];
                        gx += v * k[r * 3 + c];
                        gy += v * k[c * 3 + r];
                    }
                gx /= 8f;
                gy /= 8f;
                var inv = 1f / MathF.Sqrt(gx * gx + gy * gy + up * up);
                var o = (j * w + i) * 3;
                normals[o] = gx * inv;
                normals[o + 1] = gy * inv;
                normals[o + 2] = up * inv;
            }
        return normals;
    }
}
