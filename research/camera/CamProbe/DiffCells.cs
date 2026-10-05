using System.Text.Json;
using Atlas3K.Core.Campaign;
using Atlas3K.Core.Campaign.Camera;

static class DiffCells
{
    public static void Run(CameraHeightField field, int tw, int th)
    {
        var bob = new float[1784 * 1405];
        Buffer.BlockCopy(File.ReadAllBytes("Z:/Claude/TerryClone/research/bob_re/frida_out/cam_s4d.f32"), 0, bob, 0, bob.Length * 4);
        var cells = CameraHeightmapStep.Sample(field, 1784, 1405, CameraHeightmapStep.SceneWidth(tw), CameraHeightmapStep.SceneDepth(th), 4);
        var objs = JsonDocument.Parse(File.ReadAllText("Z:/Claude/TerryClone/research/bob_re/frida_out/cam_s4g_patches.json")).RootElement.GetProperty("objs")
            .EnumerateArray().Select(o => (M: o.GetProperty("m").EnumerateArray().Select(e => e.GetSingle()).ToArray(),
                                           Inv: o.GetProperty("inv").EnumerateArray().Select(e => e.GetSingle()).ToArray(),
                                           Aabb: o.GetProperty("aabb").EnumerateArray().Select(e => e.GetSingle()).ToArray(),
                                           Local: o.GetProperty("local").EnumerateArray().Select(e => e.GetSingle()).ToArray())).ToList();
        var byM = new Dictionary<string, int>();
        for (var i = 0; i < objs.Count; i++) byM.TryAdd(string.Join(",", objs[i].M.Take(12).Select(v => BitConverter.SingleToInt32Bits(v + 0f))), i);
        // field with BOB's own patch objects (same maps)
        var bobPatches = new List<CameraHeightField.Patch>();
        var missing = 0;
        foreach (var p in field.Patches)
            if (!p.Source.Contains("height_patches") && byM.TryGetValue(string.Join(",", p.M.Take(12).Select(v => BitConverter.SingleToInt32Bits(v + 0f))), out var i)) bobPatches.Add(new CameraHeightField.Patch(p.Source, objs[i].Aabb, objs[i].Local, objs[i].M, objs[i].Inv, p.Map));
            else { bobPatches.Add(p); missing++; }
        Console.WriteLine($"patches mapped to BOB objects: {field.Patches.Count - missing}/{field.Patches.Count}");
        var withBob = field.WithPatches(bobPatches);
        var cells2 = CameraHeightmapStep.Sample(withBob, 1784, 1405, CameraHeightmapStep.SceneWidth(tw), CameraHeightmapStep.SceneDepth(th), 4);
        int d1 = 0, d2 = 0;
        var list = new List<int>();
        for (var i = 0; i < bob.Length; i++)
        {
            if (BitConverter.SingleToInt32Bits(cells[i]) != BitConverter.SingleToInt32Bits(bob[i])) d1++;
            if (BitConverter.SingleToInt32Bits(cells2[i]) != BitConverter.SingleToInt32Bits(bob[i])) { d2++; list.Add(i); }
        }
        Console.WriteLine($"cells differing: native objects {d1}, with BOB's inverse/aabb {d2}");
        foreach (var i in list.Take(int.Parse(Environment.GetEnvironmentVariable("NLIST") ?? "15"))) Console.WriteLine($"  cell j {i / 1784} u {i % 1784}: bob {bob[i]:R} mine {cells2[i]:R}");
    }
}
