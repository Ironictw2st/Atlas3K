using System.Text.Json;
using Atlas3K.Core.Campaign.Camera;

static class InvFit
{
    static readonly int[] Used = [0, 2, 3, 8, 10, 11];
    public static void Run()
    {
        var objs = JsonDocument.Parse(File.ReadAllText("Z:/Claude/TerryClone/research/bob_re/frida_out/cam_s4g_patches.json")).RootElement.GetProperty("objs")
            .EnumerateArray().Select(o => (M: o.GetProperty("m").EnumerateArray().Select(e => e.GetSingle()).ToArray(),
                                           Inv: o.GetProperty("inv").EnumerateArray().Select(e => e.GetSingle()).ToArray())).ToList();
        var methods = new Dictionary<string, Func<float[], float[]>>
        {
            ["double cofactor"] = CameraHeightField.Inverse,
            ["float cofactor"] = FloatCofactor,
            ["affine float adj/det"] = AffineAdj,
            ["affine float adj*(1/det)"] = AffineAdjRecip,
            ["affine double"] = AffineDouble,
        };
        var counts = methods.ToDictionary(k => k.Key, _ => new int[7]);
        var n = 0;
        foreach (var (m, inv) in objs)
        {
            if (m[0] == 1 && m[5] == 1 && m[10] == 1) continue;
            n++;
            foreach (var (name, f) in methods)
            {
                var r = f(m);
                var all = true;
                for (var i = 0; i < 6; i++) { var ok = r[Used[i]] == inv[Used[i]]; if (ok) counts[name][i]++; all &= ok; }
                if (all) counts[name][6]++;
            }
        }
        Console.WriteLine($"{n} objects; exact per used entry 0,2,3,8,10,11 and all:");
        foreach (var (k, c) in counts) Console.WriteLine($"  {k}: {string.Join(" ", c)}");
    }

    static float[] FloatCofactor(float[] a)
    {
        var inv = new float[16];
        inv[0] = a[5] * a[10] * a[15] - a[5] * a[11] * a[14] - a[9] * a[6] * a[15] + a[9] * a[7] * a[14] + a[13] * a[6] * a[11] - a[13] * a[7] * a[10];
        inv[4] = -a[4] * a[10] * a[15] + a[4] * a[11] * a[14] + a[8] * a[6] * a[15] - a[8] * a[7] * a[14] - a[12] * a[6] * a[11] + a[12] * a[7] * a[10];
        inv[8] = a[4] * a[9] * a[15] - a[4] * a[11] * a[13] - a[8] * a[5] * a[15] + a[8] * a[7] * a[13] + a[12] * a[5] * a[11] - a[12] * a[7] * a[9];
        inv[12] = -a[4] * a[9] * a[14] + a[4] * a[10] * a[13] + a[8] * a[5] * a[14] - a[8] * a[6] * a[13] - a[12] * a[5] * a[10] + a[12] * a[6] * a[9];
        inv[2] = a[1] * a[6] * a[15] - a[1] * a[7] * a[14] - a[5] * a[2] * a[15] + a[5] * a[3] * a[14] + a[13] * a[2] * a[7] - a[13] * a[3] * a[6];
        inv[10] = a[0] * a[5] * a[15] - a[0] * a[7] * a[13] - a[4] * a[1] * a[15] + a[4] * a[3] * a[13] + a[12] * a[1] * a[7] - a[12] * a[3] * a[5];
        inv[3] = -a[1] * a[6] * a[11] + a[1] * a[7] * a[10] + a[5] * a[2] * a[11] - a[5] * a[3] * a[10] - a[9] * a[2] * a[7] + a[9] * a[3] * a[6];
        inv[11] = -a[0] * a[5] * a[11] + a[0] * a[7] * a[9] + a[4] * a[1] * a[11] - a[4] * a[3] * a[9] - a[8] * a[1] * a[7] + a[8] * a[3] * a[5];
        var det = a[0] * inv[0] + a[1] * inv[4] + a[2] * inv[8] + a[3] * inv[12];
        var r = new float[16];
        foreach (var i in Used) r[i] = inv[i] / det;
        return r;
    }

    // 3x3 adjugate of the rotation-scale block, translation -(inv · t)
    static float[] AffineCore(float[] a, Func<float, float, float> div)
    {
        float m00 = a[0], m01 = a[1], m02 = a[2], m10 = a[4], m11 = a[5], m12 = a[6], m20 = a[8], m21 = a[9], m22 = a[10];
        float c00 = m11 * m22 - m12 * m21, c01 = m02 * m21 - m01 * m22, c02 = m01 * m12 - m02 * m11;
        float c10 = m12 * m20 - m10 * m22, c11 = m00 * m22 - m02 * m20, c12 = m02 * m10 - m00 * m12;
        float c20 = m10 * m21 - m11 * m20, c21 = m01 * m20 - m00 * m21, c22 = m00 * m11 - m01 * m10;
        var det = m00 * c00 + m01 * c10 + m02 * c20;
        var r = new float[16];
        r[0] = div(c00, det); r[1] = div(c01, det); r[2] = div(c02, det);
        r[4] = div(c10, det); r[5] = div(c11, det); r[6] = div(c12, det);
        r[8] = div(c20, det); r[9] = div(c21, det); r[10] = div(c22, det);
        r[3] = -(r[0] * a[3] + r[1] * a[7] + r[2] * a[11]);
        r[7] = -(r[4] * a[3] + r[5] * a[7] + r[6] * a[11]);
        r[11] = -(r[8] * a[3] + r[9] * a[7] + r[10] * a[11]);
        return r;
    }
    static float[] AffineAdj(float[] a) => AffineCore(a, (c, d) => c / d);
    static float[] AffineAdjRecip(float[] a) => AffineCore(a, (c, d) => c * (1f / d));
    static float[] AffineDouble(float[] a)
    {
        var m = CameraHeightField.Inverse(a);
        return m;
    }
}
