namespace Atlas3K.Core.Battle.Build.Bmd;

/// <summary>
/// warscape WS_SCENE_NODE_TERRAIN_EDITOR_V3::build_hf_influence_map (via qttoolutility QTU::height_alpha_map, built by
/// bob_vegetation's Prepare Generation Data): a ((tiles + 2) · density + 1)² field, one tile-cell border round the tile,
/// 1 inside and fading to 0 over the cells at the tile's edge: per pixel get_hf_influence_value blends the cell's
/// neighbour flags (FUN_1803e8e20 across the cell, completed corners and sides) into v and gives
/// (1 − e^(−4.41 v²)) · 1.0123. Procedural trees' heights are the height map times this field. Ported for tiles without
/// a cell mask and link points (all corpus tiles); bit-exact against BOB's map.
/// </summary>
public static class HfInfluenceMap
{
    public static float[] Build(int density, int tilesWide, int tilesHigh, out int size)
    {
        var w = (tilesWide + 2) * density + 1;
        var h = (tilesHigh + 2) * density + 1;
        size = w;
        var field = new float[w * h];
        for (var y = 0; y < h; y++)
            for (var x = 0; x < w; x++)
                field[y * w + x] = Value(x - density, y - density, density, tilesWide, tilesHigh);
        return field;
    }

    /// <summary>FUN_1803e8e20: across a cell, from the near side's neighbour value to 1 at the middle.</summary>
    private static float Edge(float coord, float lo, float hi, int d)
    {
        var f4 = (float)d * 0.5f + 0.25f;
        float t, nb;
        if (coord < (float)(d + 1) * 0.5f)
        {
            t = coord - 2f;
            nb = lo;
        }
        else
        {
            t = ((float)d - coord) - 2f;
            nb = hi;
        }
        t = !(0f <= t) ? 0f : 5000f < t ? 5000f : t;
        return t / f4 * (1f - nb) + nb;
    }

    public static float Value(int px, int py, int d, int w, int h)
    {
        if (!(px >= 0 && px < d * w && py >= 0 && py < d * h)) return 0f;
        int ix = px / d, iy = py / d;
        float u = iy != 0 ? 1f : 0f, dn = iy != h - 1 ? 1f : 0f, l = ix != 0 ? 1f : 0f, r = ix != w - 1 ? 1f : 0f;
        float tl = ix != 0 && iy != 0 ? 1f : 0f, tr = ix != w - 1 && iy != 0 ? 1f : 0f;
        float bl = ix != 0 && iy != h - 1 ? 1f : 0f, br = ix != w - 1 && iy != h - 1 ? 1f : 0f;
        if (tl == 0f && l == 1f && u == 1f) tl = 1f;
        if (bl == 0f && l == 1f && dn == 1f) bl = 1f;
        if (tr == 0f && r == 1f && u == 1f) tr = 1f;
        if (br == 0f && r == 1f && dn == 1f) br = 1f;
        if (l == 1f && u == 1f && tr == 1f && r == 0f) r = 1f;
        else if (r == 1f && u == 1f && tl == 1f) { if (l == 0f) l = 1f; }
        else if (l == 0f && ix > 0 && (tl == 1f || bl == 1f)) l = 1f;
        if (r == 0f && ix < w - 1 && (tr == 1f || br == 1f)) r = 1f;
        if (u == 0f && iy > 0 && (tl == 1f || tr == 1f)) u = 1f;
        if (dn == 0f && iy < h - 1 && (bl == 1f || br == 1f)) dn = 1f;
        if (tl == 0f && l != u) tl = 1f;
        if (bl == 0f && l != dn) bl = 1f;
        if (tr == 0f && r != u) tr = 1f;
        if (br == 0f && r != dn) br = 1f;
        float lx = px - ix * d, ly = py - iy * d;
        var a = Edge(lx, bl, br, d);
        var b = Edge(lx, tl, tr, d);
        var c = Edge(ly, b, a, d);
        var dv = Edge(lx, l, r, d);
        var ev = Edge(ly, u, dn, d);
        var v = c * (dv * ev);
        var p = MathF.Pow(2.71828175f, v * v * -4.40999937f);
        return (1f - p) * 1.01230478f;
    }
}
