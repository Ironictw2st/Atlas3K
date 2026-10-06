using System.Xml.Linq;

namespace Atlas3K.Core.Battle.Build.Bmd;

/// <summary>
/// The AIH_AMBUSH_FOREST hint polylines BOB's TerryTile export adds to a battle tile's bmd_data
/// (bob_tile ACTION_TERRY_TILE::run_bmd → qttoolutility QTU::procedural_forest_ai_hints → empireutility
/// ai_hint_outlines_from_forest_blendmap; decompiles under Z:/Claude/BattleMaps/research/bob_re/forest_hints):
///  1. the forest channels: blend texture channels whose name starts with "forest" (the ground type 0 name)
///  2. BOOL_FIELD over the whole composited blend map (border included): the forest channels' weights summed in float
///     (weight = byte / 255) &gt; 0.8
///  3. TileMetrics: cell = unit_scale · 128 = 256; aabb = [−cell, (tiles + 1) · cell]; the field's cell =
///     aabb width / field width, its offset = aabb min + 0.5
///  4. the no-go outline machinery on the field (<see cref="NogoOutlines.FromField"/>: OUTLINE_CALCULATOR, min box 6,
///     the three simplification passes)
///  5. each outline: made clockwise (reversed when the signed sum Σ p.y·prev.x − p.x·prev.y is not &lt; 0), clipped
///     Sutherland–Hodgman against aabb_inner [0, tiles · cell] (top, right, bottom, left edges), dropped when its area
///     |Σ cross| / 2 is below 200
/// </summary>
public static class ForestHints
{
    public const float WeightThreshold = 0.8f;
    public const float MinArea = 200f;
    public const string ForestPrefix = "forest";

    public static List<List<(float X, float Y)>> Compute(BattleBuildContext ctx, float unitScale = 2f)
    {
        var doc = XDocument.Load(ctx.TerryFile);
        var inner = doc.Descendants("pc").First(e => (string?)e.Attribute("type") == "QTU::ProjectTileWithVista").Element("data")!.Element("data")!;
        var forest = Enumerable.Range(0, 8)
            .Where(i => ((string?)inner.Attribute($"texture_channel_{i}") ?? "").StartsWith(ForestPrefix, StringComparison.Ordinal)).ToList();
        if (forest.Count == 0 || TileBlend.Read(ctx.SourceTileDir) is not { } blend) return [];
        var project = Meshes.TerryTileProject.Load(ctx.TerryFile);
        return Compute(blend.W, blend.H, blend.Data, forest, project.TilesWide, project.TilesHigh, unitScale);
    }

    /// <param name="data">8 channel bytes per pixel, row-major.</param>
    public static List<List<(float X, float Y)>> Compute(int w, int h, byte[] data, IReadOnlyList<int> forestChannels, int tilesWide,
                                                       int tilesHigh, float unitScale)
    {
        var field = new bool[w * h];
        for (var i = 0; i < field.Length; i++)
        {
            var sum = 0f;
            foreach (var c in forestChannels) sum += data[i * 8 + c] * (1f / 255f);
            field[i] = WeightThreshold < sum;
        }
        var tileCell = unitScale * 128f;
        float minX = -tileCell, minY = -tileCell, maxX = (tilesWide + 1) * tileCell;
        var cell = (maxX - minX) / w;
        var outlines = NogoOutlines.FromField(field, w, h, cell, minX + 0.5f, minY + 0.5f);
        var inner = (X0: 0f, Y0: 0f, X1: tilesWide * tileCell, Y1: tilesHigh * tileCell);
        var result = new List<List<(float X, float Y)>>();
        foreach (var o in outlines)
        {
            var poly = o.ToList();
            if (!Clockwise(poly)) poly.Reverse();
            poly = Clip(poly, inner);
            if (Area(poly) >= MinArea) result.Add(poly);
        }
        return result;
    }

    /// <summary>QTU::polyline_is_clockwise.</summary>
    public static bool Clockwise(List<(float X, float Y)> p)
    {
        if (p.Count == 0) return false;
        var s = 0f;
        var (px, py) = p[^1];
        foreach (var (x, y) in p)
        {
            s += y * px - x * py;
            (px, py) = (x, y);
        }
        return s < 0f;
    }

    /// <summary>QTU::polyline_area_and_centroid's area: |Σ (x_i·y_(i+1) − x_(i+1)·y_i) · 0.5|.</summary>
    public static float Area(List<(float X, float Y)> p)
    {
        var s = 0f;
        for (var i = 0; i < p.Count; i++)
        {
            var (x, y) = p[i];
            var (nx, ny) = p[(i + 1) % p.Count];
            s += ny * x - nx * y;
        }
        return MathF.Abs(s * 0.5f);
    }

    /// <summary>QTU::clip_polyline_against_boundary: Sutherland–Hodgman against the box's edges (minx,maxy)→(maxx,maxy),
    /// (maxx,maxy)→(maxx,miny), (maxx,miny)→(minx,miny), (minx,miny)→(minx,maxy); a point on an edge is outside.</summary>
    public static List<(float X, float Y)> Clip(List<(float X, float Y)> poly, (float X0, float Y0, float X1, float Y1) box)
    {
        (float, float, float, float)[] edges =
        [
            (box.X0, box.Y1, box.X1, box.Y1), (box.X1, box.Y1, box.X1, box.Y0),
            (box.X1, box.Y0, box.X0, box.Y0), (box.X0, box.Y0, box.X0, box.Y1),
        ];
        foreach (var e in edges)
        {
            if (poly.Count == 0) break;
            var outp = new List<(float X, float Y)>();
            var prev = poly[^1];
            foreach (var cur in poly)
            {
                if (!Inside(e, cur))
                {
                    if (Inside(e, prev)) outp.Add(Intersect(e, prev, cur));
                }
                else
                {
                    if (!Inside(e, prev)) outp.Add(Intersect(e, prev, cur));
                    outp.Add(cur);
                }
                prev = cur;
            }
            poly = outp;
        }
        return poly;
    }

    // FUN_18005b6b0
    private static bool Inside((float X0, float Y0, float X1, float Y1) e, (float X, float Y) p) =>
        (p.Y - e.Y0) * (e.X1 - e.X0) - (e.Y1 - e.Y0) * (p.X - e.X0) < 0f;

    // FUN_18005a630: the edge line (e) against the segment a→b
    private static (float X, float Y) Intersect((float X0, float Y0, float X1, float Y1) e, (float X, float Y) a, (float X, float Y) b)
    {
        var t = ((e.Y0 - a.Y) * (b.X - a.X) - (e.X0 - a.X) * (b.Y - a.Y)) /
                ((e.X1 - e.X0) * (b.Y - a.Y) - (e.Y1 - e.Y0) * (b.X - a.X));
        return ((e.X1 - e.X0) * t + e.X0, (e.Y1 - e.Y0) * t + e.Y0);
    }
}
