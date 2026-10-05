using TerryClone.Formats.Maps;
using TerryClone.Formats.Models;

namespace TerryClone.Core.Campaign.GlobalMesh;

/// <summary>
/// Native replacement for BOB's global mesh build (tooldatabuilder FUN_180124ed0), following the decompiled
/// algorithm (docs/bob_re_global_mesh.md). Game-valid rather than byte-identical.
///  - the map is cut into square meshes of <c>cells = (int)(maxTiles · 0.125)</c> cells (2 cells per tile-map pixel),
///    visited z-row by z-row from the south-west; empty meshes are skipped and the rest numbered in that order
///  - vertex heights: <see cref="LfSampler"/> where a tile of the mesh kind covers the point, holes elsewhere
///  - flags (sea meshes pin every 4th row and column), normalised Sobel normals (up = 1/0.33), quads split [a,c,b] [c,d,b], <see cref="TriangleMerger"/> at
///    factor 0.9999, winding flipped, vertices renumbered in first-use order
///  - skirts: a double-sided quad 1.0 below every boundary edge next to a hole or the map edge (not on seams
///    between meshes)
///  - land meshes also get a (cells+1)² compressed map of the final surface: header (0, -50, 0, 0, max, 0), 0 = hole
/// </summary>
public sealed class GlobalMeshBuilder
{
    public const float MergeFactor = 0.9999f;
    public const float Hole = -20f;
    public const float SkirtDepth = 1f;

    public sealed record MeshResult(int Row, int Col, RigidModelV2 Model, Raster<ushort>? HeightMap, float[]? HeightHeader, int Triangles);

    private readonly TileCoverage _coverage;
    private readonly LfSampler _land, _sea;
    private readonly int _cells, _gridTotal, _meshesPerAxis;
    private readonly double _extent;

    public int MeshesPerAxis => _meshesPerAxis;

    public GlobalMeshBuilder(TileCoverage coverage, LfSampler land, LfSampler sea, int tilesW, int tilesH, float tileSize)
    {
        _coverage = coverage;
        _land = land;
        _sea = sea;
        var maxTiles = Math.Max(tilesW, tilesH);
        _cells = (int)(maxTiles * 0.125f);
        _gridTotal = 2 * maxTiles;
        _meshesPerAxis = (_gridTotal + _cells - 1) / _cells;
        _extent = (float)(maxTiles * tileSize);
    }

    private float Coord(int index) => (float)(index * _extent / _gridTotal);

    public MeshResult? Build(int row, int col, MeshKind kind)
    {
        var n = _cells + 1;
        var i0 = col * _cells;
        var j0 = row * _cells;
        var x = new float[n * n];
        var y = new float[n * n];
        var z = new float[n * n];
        var flags = new byte[n * n];
        var sampler = kind == MeshKind.Land ? _land : _sea;

        // validity of every grid point of this mesh plus a one-cell border, queried once
        var m = n + 2;
        var validGrid = new bool[m * m];
        for (var j = -1; j <= n; j++)
            for (var i = -1; i <= n; i++)
            {
                int gi = i0 + i, gj = j0 + j;
                validGrid[(j + 1) * m + i + 1] = gi >= 0 && gj >= 0 && gi <= _gridTotal && gj <= _gridTotal
                                                 && _coverage.Covered(Coord(gi), Coord(gj), kind);
            }
        bool Valid(int gi, int gj)
        {
            int li = gi - i0 + 1, lj = gj - j0 + 1;
            return li >= 0 && lj >= 0 && li < m && lj < m && validGrid[lj * m + li];
        }

        var any = false;
        for (var j = 0; j < n; j++)
        for (var i = 0; i < n; i++)
        {
            var k = j * n + i;
            int gi = i0 + i, gj = j0 + j;
            x[k] = Coord(gi);
            z[k] = Coord(gj);
            flags[k] = 2;
            if (!Valid(gi, gj)) { y[k] = Hole; continue; }
            any = true;
            y[k] = sampler.Height(x[k], z[k]);
            byte f = 2;
            for (var dj = -1; dj <= 1 && f == 2; dj++)
                for (var di = -1; di <= 1; di++)
                    if ((di != 0 || dj != 0) && !Valid(gi + di, gj + dj)) { f = 0; break; }
            if (i == 0 || j == 0 || i == n - 1 || j == n - 1)
            {
                var count = (Valid(gi, gj - 1) ? 1 : 0) + (Valid(gi, gj + 1) ? 1 : 0) + (Valid(gi - 1, gj) ? 1 : 0) + (Valid(gi + 1, gj) ? 1 : 0);
                f = 0;
                if (count == 3)
                {
                    var onX = i == 0 || i == n - 1;
                    if (((j != 0 && j != n - 1) || (i & 31) != 0) && (!onX || (j & 31) != 0)) f = 3;
                }
            }
            // sea meshes keep a 4-cell lattice (BOB's option flag in the grid lambda)
            if (kind == MeshKind.Sea && ((i & 3) == 0 || (j & 3) == 0)) f = 0;
            flags[k] = f;
        }
        if (!any) return null;

        var normals = SobelNormals(y, n);
        var triangles = new List<int[]>();
        for (var j = 0; j < n - 1; j++)
            for (var i = 0; i < n - 1; i++)
            {
                int a = j * n + i, b = a + 1, c = a + n, d = c + 1;
                if (y[a] == Hole || y[b] == Hole || y[c] == Hole || y[d] == Hole) continue;
                triangles.Add([a, c, b]);
                triangles.Add([c, d, b]);
            }
        if (triangles.Count == 0) return null;
        var inputTriangles = triangles.Count;

        var merged = new TriangleMerger(x, y, z, normals, flags).Run(triangles, MergeFactor);
        foreach (var t in merged) (t[0], t[1]) = (t[1], t[0]);

        // first-use renumbering
        var remap = new Dictionary<int, int>();
        var positions = new List<(float X, float Y, float Z)>();
        var indices = new List<ushort>();
        foreach (var t in merged)
            foreach (var q in t)
            {
                if (!remap.TryGetValue(q, out var id))
                {
                    id = remap.Count;
                    remap.Add(q, id);
                    positions.Add((x[q], y[q], z[q]));
                }
                indices.Add(checked((ushort)id));
            }

        AddSkirts(merged, n, i0, j0, x, y, z, Valid, positions, indices);
        if (positions.Count > ushort.MaxValue)
            throw new InvalidDataException($"{kind} mesh ({row},{col}) has {positions.Count} vertices, more than 16-bit indices allow.");

        var model = RigidModelV2.NewTerrainTile(kind == MeshKind.Sea);
        model.Vertices = RigidModelV2.PackPositions(positions);
        model.Indices = [.. indices];
        model.SetTileBounds(Coord(i0), Coord(j0), Coord(i0 + _cells), Coord(j0 + _cells));

        Raster<ushort>? heights = null;
        float[]? header = null;
        if (kind == MeshKind.Land) (heights, header) = RasteriseSurface(merged, n, x, y, z);
        return new MeshResult(row, col, model, heights, header, inputTriangles);
    }

    private static float[] SobelNormals(float[] h, int n)
    {
        int[] k = [1, 0, -1, 2, 0, -2, 1, 0, -1];
        var normals = new float[n * n * 3];
        const float up = 1f / 0.33f;
        for (var j = 0; j < n; j++)
            for (var i = 0; i < n; i++)
            {
                float gx = 0, gy = 0;
                for (var r = 0; r < 3; r++)
                    for (var c = 0; c < 3; c++)
                    {
                        var w = k[r * 3 + c];
                        gx += h[Math.Clamp(j + r - 1, 0, n - 1) * n + Math.Clamp(i + c - 1, 0, n - 1)] * w;
                        gy += h[Math.Clamp(j + c - 1, 0, n - 1) * n + Math.Clamp(i + r - 1, 0, n - 1)] * w;
                    }
                gx /= 8f;
                gy /= 8f;
                var inv = 1f / MathF.Sqrt(gx * gx + gy * gy + up * up);
                var o = (j * n + i) * 3;
                normals[o] = gx * inv;
                normals[o + 1] = gy * inv;
                normals[o + 2] = up * inv;
            }
        return normals;
    }

    /// <summary>Double-sided vertical quads under boundary edges that border a hole or the map edge.</summary>
    private void AddSkirts(List<int[]> surface, int n, int i0, int j0, float[] x, float[] y, float[] z,
        Func<int, int, bool> valid, List<(float, float, float)> positions, List<ushort> indices)
    {
        var edgeUse = new Dictionary<(int, int), int>();
        foreach (var t in surface)
            for (var e = 0; e < 3; e++)
            {
                int a = t[e], b = t[(e + 1) % 3];
                var key = a < b ? (a, b) : (b, a);
                edgeUse[key] = edgeUse.GetValueOrDefault(key) + 1;
            }
        foreach (var t in surface)
            for (var e = 0; e < 3; e++)
            {
                int a = t[e], b = t[(e + 1) % 3];
                if (edgeUse[a < b ? (a, b) : (b, a)] != 1) continue;
                if (OnSeam(a, b, n, i0, j0, valid)) continue;
                var s = checked((ushort)positions.Count);
                positions.Add((x[a], y[a], z[a]));
                positions.Add((x[b], y[b], z[b]));
                positions.Add((x[a], y[a] - SkirtDepth, z[a]));
                positions.Add((x[b], y[b] - SkirtDepth, z[b]));
                foreach (var q in (ReadOnlySpan<int>)[0, 1, 2, 2, 1, 3, 1, 0, 2, 1, 2, 3]) indices.Add((ushort)(s + q));
            }
    }

    /// <summary>A boundary edge on the mesh perimeter whose outside neighbour quad is solid ground in the next mesh.</summary>
    private static bool OnSeam(int a, int b, int n, int i0, int j0, Func<int, int, bool> valid)
    {
        int ai = a % n, aj = a / n, bi = b % n, bj = b / n;
        (int di, int dj) outward;
        if (ai == bi && (ai == 0 || ai == n - 1)) outward = (ai == 0 ? -1 : 1, 0);
        else if (aj == bj && (aj == 0 || aj == n - 1)) outward = (0, aj == 0 ? -1 : 1);
        else return false;
        return valid(i0 + ai + outward.di, j0 + aj + outward.dj) && valid(i0 + bi + outward.di, j0 + bj + outward.dj);
    }

    /// <summary>Heights of the final surface at every grid point (barycentric), 0 where no triangle covers it.</summary>
    private static (Raster<ushort>, float[]) RasteriseSurface(List<int[]> surface, int n, float[] x, float[] y, float[] z)
    {
        var h = new float[n * n];
        var covered = new bool[n * n];
        var cell = x[1] - x[0];
        foreach (var t in surface)
        {
            int a = t[0], b = t[1], c = t[2];
            int ia = a % n, ja = a / n, ib = b % n, jb = b / n, ic = c % n, jc = c / n;
            var area = (double)(ib - ia) * (jc - ja) - (double)(ic - ia) * (jb - ja);
            if (area == 0) continue;
            for (var j = Math.Min(ja, Math.Min(jb, jc)); j <= Math.Max(ja, Math.Max(jb, jc)); j++)
                for (var i = Math.Min(ia, Math.Min(ib, ic)); i <= Math.Max(ia, Math.Max(ib, ic)); i++)
                {
                    var u = ((double)(ib - i) * (jc - j) - (double)(ic - i) * (jb - j)) / area;
                    var v = ((double)(ic - i) * (ja - j) - (double)(ia - i) * (jc - j)) / area;
                    var w = 1 - u - v;
                    if (u < -1e-9 || v < -1e-9 || w < -1e-9) continue;
                    var k = j * n + i;
                    h[k] = (float)(u * y[a] + v * y[b] + w * y[c]);
                    covered[k] = true;
                }
        }
        var max = float.MinValue;
        for (var k = 0; k < h.Length; k++) if (covered[k]) max = Math.Max(max, h[k]);
        const float lo = -50f;
        var raster = new Raster<ushort>(n, n);
        for (var k = 0; k < h.Length; k++)
            if (covered[k]) raster.Data[k] = (ushort)Math.Clamp(Math.Round((h[k] - lo) / (max - lo) * 65535), 1, 65535);
        return (raster, [0, lo, 0, 0, max, 0]);
    }
}
