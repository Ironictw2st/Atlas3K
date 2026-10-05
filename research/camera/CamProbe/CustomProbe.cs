using Atlas3K.Formats.Models;
using Atlas3K.Formats.Packs;
static class CustomProbe
{
    public static void Run()
    {
        var packs = PackSet.OpenVanilla(@"C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\data");
        foreach (var f in new[] { "terrain/tiles/campaign/blockout_cliff/mid_curve1/", "terrain/tiles/campaign/blockout_cliff/mid_curve1_mirror/", "terrain/tiles/campaign/blockout_cliff/straight_2/" })
        {
            var ws = packs.TryRead(f + "custom_mesh.wsmodel")!;
            var geo = RigidModelGeometry.WsModelGeometryPath(ws)!;
            var m = RigidModel.Read(packs.TryRead(geo)!);
            Console.WriteLine($"{f} geo {geo} lods {m.Lods.Count}");
            foreach (var (lod, li) in m.Lods.Select((l, i) => (l, i)))
                foreach (var mesh in lod.Meshes)
                {
                    float[] vb = [float.MaxValue, float.MaxValue, float.MaxValue, float.MinValue, float.MinValue, float.MinValue];
                    for (var v = 0; v < mesh.Positions.Length; v += 3) for (var i = 0; i < 3; i++) { vb[i] = MathF.Min(vb[i], mesh.Positions[v + i]); vb[3 + i] = MathF.Max(vb[3 + i], mesh.Positions[v + i]); }
                    Console.WriteLine($"  lod {li} hdr {string.Join(",", mesh.BoundsMin)} .. {string.Join(",", mesh.BoundsMax)} verts {string.Join(",", vb.Select(x => x.ToString("G6")))} pivot {string.Join(",", mesh.Pivot)}");
                }
            Console.WriteLine("  wsmodel: " + System.Text.Encoding.UTF8.GetString(ws).Replace("\n", " ").Substring(0, Math.Min(400, ws.Length)));
        }
        float s = (595.1f / 1784f) / 128f;
        Console.WriteLine($"BOB x min tile units rel. corner: {431.55984f / s - 1294 * 128f}  mine {431.55618f / s - 1294 * 128f}");
    }
}
