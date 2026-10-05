using System.Text.Json;
using Atlas3K.Core.Campaign.Camera;

static class PatchCompare
{
    static readonly Dictionary<string, int> Entry = new();
    public static void Run(CameraHeightField field)
    {
        var objs = JsonDocument.Parse(File.ReadAllText("Z:/Claude/TerryClone/research/bob_re/frida_out/cam_s4g_patches.json")).RootElement.GetProperty("objs")
            .EnumerateArray().Select(o => (M: o.GetProperty("m").EnumerateArray().Select(e => e.GetSingle()).ToArray(),
                                           Inv: o.GetProperty("inv").EnumerateArray().Select(e => e.GetSingle()).ToArray(),
                                           Aabb: o.GetProperty("aabb").EnumerateArray().Select(e => e.GetSingle()).ToArray(),
                                           Local: o.GetProperty("local").EnumerateArray().Select(e => e.GetSingle()).ToArray())).ToList();
        var stats = new Dictionary<string, int[]>();
        var shown = new Dictionary<string, int>();
        foreach (var p in field.Patches)
        {
            var kind = p.Source.Contains("height_patches") ? "river" : p.M[8] != 0 && Math.Abs(Math.Abs(p.M[10]) - Math.Abs(p.M[0])) > 1e-3 || p.M[1] == 0 && p.M[9] == 0 && Math.Abs(Math.Sqrt(p.M[8] * p.M[8] + p.M[10] * p.M[10]) / Math.Sqrt(p.M[0] * p.M[0] + p.M[2] * p.M[2]) - 1.15476) < 1e-3 ? "tile" : "global";
            var best = objs.Where(o => Math.Abs(o.M[3] - p.M[3]) < 1e-3 && Math.Abs(o.M[11] - p.M[11]) < 1e-3 && Math.Abs(o.M[7] - p.M[7]) < 1e-3)
                .OrderBy(o => Enumerable.Range(0, 12).Sum(i => Math.Abs(o.M[i] - p.M[i]))).FirstOrDefault();
            if (!stats.TryGetValue(kind, out var s)) stats[kind] = s = new int[6];
            s[0]++;
            if (best.M is null) continue;
            s[1]++;
            if (best.M.SequenceEqual(p.M)) s[2]++;
            else for (var e = 0; e < 12; e++) if (best.M[e] != p.M[e]) { var key = kind + " entry " + e; Entry[key] = Entry.GetValueOrDefault(key) + 1; if (e == 7 && Entry[key] < 4) Console.WriteLine($"  y: bob {best.M[7]:R} mine {p.M[7]:R} d {best.M[7] - p.M[7]:G3}"); }
            if (best.Inv.SequenceEqual(p.Inv)) s[3]++;
            if (best.Aabb.SequenceEqual(p.Aabb)) s[4]++;
            if (best.Local.SequenceEqual(p.Local)) s[5]++;
            if (!best.M.SequenceEqual(p.M) && shown.GetValueOrDefault(kind) < 3)
            {
                shown[kind] = shown.GetValueOrDefault(kind) + 1;
                Console.WriteLine($"  {kind} m bob  {string.Join(",", best.M.Take(12).Select(v => v.ToString("R")))}");
                Console.WriteLine($"  {kind} m mine {string.Join(",", p.M.Take(12).Select(v => v.ToString("R")))}");
            }
        }
        foreach (var (k, v) in Entry.OrderBy(k => k.Key)) Console.WriteLine($"  {k}: {v}");
        foreach (var (k, s) in stats) Console.WriteLine($"{k}: {s[0]} objects, matched {s[1]}, m exact {s[2]}, inv exact {s[3]}, aabb exact {s[4]}, local exact {s[5]}");
    }
}
static class RiverDump
{
    public static void Run(CameraHeightField f)
    {
        foreach (var p in f.Patches.Where(p => p.Source.Contains("height_patches")).Take(4))
            Console.WriteLine($"{p.Source} aabb {string.Join(",", p.Aabb.Select(v => v.ToString("R")))} local {string.Join(",", p.Local.Select(v => v.ToString("R")))}");
    }
}
