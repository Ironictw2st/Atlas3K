namespace Atlas3K.Core.Battle.Build;

/// <summary>
/// tooldatabuilder FUN_1800dc250 ("Rasterize final heightmap"): a mesh rasterised into a height field. Per triangle
/// (A, B, C = indices i, i+1, i+2): the integer bounding box of x and z (truncated), from min − 1 to max inclusive;
/// barycentric weights from the dot products of (B−A), (C−A), (P−A) in (z, x), accepted when all three lie in
/// [−0.0001, 1.0001]; the cell (trunc(s·z), trunc(s·x)), s = density / terrain tile size, is overwritten (the last
/// triangle wins) with w_C·C.y + w_B·B.y + w_A·A.y. Float32 in BOB's operation order.
/// </summary>
public static class MeshRaster
{
    private const float Lo = -9.999999747378752e-05f, Hi = 1.000100016593933f;

    public static void Rasterise(float[] field, int width, int height, IReadOnlyList<(float X, float Y, float Z)> v, IReadOnlyList<int> idx, float scale)
    {
        for (var i = 0; i + 2 < idx.Count; i += 3)
        {
            var a = v[idx[i]]; var b = v[idx[i + 1]]; var c = v[idx[i + 2]];
            int ax = (int)a.X, az = (int)a.Z, bx = (int)b.X, bz = (int)b.Z, cx = (int)c.X, cz = (int)c.Z;
            int x0 = Math.Min(ax, Math.Min(bx, cx)), x1 = Math.Max(ax, Math.Max(bx, cx));
            int z0 = Math.Min(az, Math.Min(bz, cz)), z1 = Math.Max(az, Math.Max(bz, cz));
            for (var z = z0 - 1; z < z1 + 1; z++)
                for (var x = x0 - 1; x < x1 + 1; x++)
                {
                    float d22 = b.Z - a.Z, d25 = b.X - a.X, d23 = c.Z - a.Z, d26 = c.X - a.X;
                    float p27 = z - a.Z, p24 = x - a.X;
                    var dot00 = d22 * d22 + d25 * d25;
                    var dot01 = d23 * d22 + d26 * d25;
                    var dot11 = d23 * d23 + d26 * d26;
                    var dot02 = p27 * d22 + p24 * d25;
                    var dot12 = p27 * d23 + p24 * d26;
                    var den = dot11 * dot00 - dot01 * dot01;
                    if (den == 0f) continue;
                    var inv = 1f / den;
                    var u = (dot02 * dot11 - dot12 * dot01) * inv;
                    var w = (dot12 * dot00 - dot02 * dot01) * inv;
                    var t = (1f - u) - w;
                    if (!(Lo <= t && t <= Hi && Lo <= u && u <= Hi && Lo <= w && w <= Hi)) continue;
                    var px = scale * x;
                    if (!(0f <= px && px < width)) continue;
                    var pz = scale * z;
                    if (!(0f <= pz && pz < height)) continue;
                    field[(int)(long)pz * width + (int)(long)px] = w * c.Y + u * b.Y + t * a.Y;
                }
        }
    }
}
