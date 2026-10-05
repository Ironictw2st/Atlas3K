using System.Text.Json;
using Atlas3K.Core.Campaign;
using Atlas3K.Core.Campaign.Camera;

static class CellProbe
{
    public static void Run(CameraHeightField field, int tw, int th, int j, int u)
    {
        var objs = JsonDocument.Parse(File.ReadAllText("Z:/Claude/TerryClone/research/bob_re/frida_out/cam_s4g_patches.json")).RootElement.GetProperty("objs")
            .EnumerateArray().Select(o => (M: o.GetProperty("m").EnumerateArray().Select(e => e.GetSingle()).ToArray(),
                                           Inv: o.GetProperty("inv").EnumerateArray().Select(e => e.GetSingle()).ToArray(),
                                           Aabb: o.GetProperty("aabb").EnumerateArray().Select(e => e.GetSingle()).ToArray(),
                                           Local: o.GetProperty("local").EnumerateArray().Select(e => e.GetSingle()).ToArray())).ToList();
        float stepX = CameraHeightmapStep.SceneWidth(tw) / 1784, stepZ = CameraHeightmapStep.SceneDepth(th) / 1405, halfX = stepX * 0.5f, halfZ = stepZ * 0.5f;
        float cx = u * stepX, cz = j * stepZ, minX = cx - halfX, maxX = cx + halfX, minZ = cz - halfZ, maxZ = cz + halfZ;
        float dx = maxX - minX, dz = maxZ - minZ; int nx = (int)MathF.Ceiling(dx * 4), nz = (int)MathF.Ceiling(dz * 4);
        float sx = dx / nx, sz = dz / nz;
        var pts = new List<(float, float)>();
        var z = minZ;
        for (var a = 0; a < nz; a++) { var x = minX; for (var b = 0; b < nz; b++) { pts.Add((x, z)); x += sx; } z += sz; }
        pts.Add(((maxX - minX) * 0.5f + minX, (maxZ - minZ) * 0.5f + minZ));
        foreach (var (x, zz) in pts)
        {
            Console.WriteLine($"pt {x:R},{zz:R}: height {field.Height(x, zz):R} patch {field.PatchHeight(x, zz):R} gm {field.GlobalMeshHeight(x, zz / CameraHeightField.ZScale):R}");
            if (Environment.GetEnvironmentVariable("NOPATCH") == "1") continue;
            foreach (var p in field.Patches)
            {
                var one = new CameraHeightField([], [p], [-100, -100, 700, 700], null);
                var v = one.PatchHeight(x, zz);
                if (v == float.MinValue) continue;
                var bob = objs.Where(o => Math.Abs(o.M[3] - p.M[3]) < 1e-3 && Math.Abs(o.M[11] - p.M[11]) < 1e-3 && Math.Abs(o.M[7] - p.M[7]) < 1e-3).FirstOrDefault();
                var bv = float.NaN;
                if (bob.M is not null)
                {
                    var bp = new CameraHeightField.Patch(p.Source, bob.Aabb, bob.Local, bob.M, bob.Inv, p.Map);
                    bv = new CameraHeightField([], [bp], [-100, -100, 700, 700], null).PatchHeight(x, zz);
                }
                Console.WriteLine($"   {Path.GetFileName(p.Source)} mine {v:R} with bob's object {bv:R}");
                if (bob.M is not null && v != bv)
                {
                    Console.WriteLine($"     m mine {string.Join(",", p.M.Take(12).Select(q => q.ToString("R")))}\n     m bob  {string.Join(",", bob.M.Take(12).Select(q => q.ToString("R")))}");
                    Console.WriteLine($"     inv mine {string.Join(",", p.Inv.Take(12).Select(q => q.ToString("R")))}\n     inv bob  {string.Join(",", bob.Inv.Take(12).Select(q => q.ToString("R")))}");
                }
            }
        }
    }
}
