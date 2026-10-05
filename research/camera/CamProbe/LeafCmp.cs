using System.Text.Json;
using Atlas3K.Core.Campaign.Camera;
using Atlas3K.Formats.Maps;
using Atlas3K.Formats.Models;
using Atlas3K.Formats.Packs;

static class LeafCmp
{
    static readonly Dictionary<string, int> Miss = new();
    public static void Run()
    {
        float T = 595.1f / 1784f, ZS = 1.15476f;
        var packs = PackSet.OpenVanilla(@"C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\data");
        var prefix = PackFile.Normalize(TileDatabase.Folder);
        var db = TileDatabase.Load(packs.Packs.SelectMany(p => p.Entries.Keys).Where(k => k.StartsWith(prefix, StringComparison.Ordinal)).Distinct().Select(k => packs.TryRead(k)).OfType<byte[]>());
        var gm = TileList.Read("Z:/Claude/TerryClone/Vanilla/Map/terrain/campaigns/3k_dlc07_main_map/global_map/tile_list.bin");
        (int, int)? Size(int r) => db.TryGetValue(TileDatabase.NormalisePath(gm.Paths[(int)gm.Records[r].Path]), out var t) ? (t.Width, t.Height) : null;
        var mode = Environment.GetEnvironmentVariable("CMODE") ?? "all";
        float[]? Custom(int r)
        {
            if (mode == "none") return null;
            var o = gm.Records[r].Orientation & 0xF0;
            if (mode == "o10" && o != 0x10) return null;
            var folder = TileDatabase.NormalisePath(gm.Paths[(int)gm.Records[r].Path]).Replace((char)92, '/');
            if (packs.TryRead(folder + "custom_mesh.wsmodel") is not { } ws || RigidModelGeometry.WsModelGeometryPath(ws) is not { } geo || packs.TryRead(geo) is not { } rm) return null;
            float[] b = [float.MaxValue, float.MaxValue, float.MaxValue, float.MinValue, float.MinValue, float.MinValue];
            foreach (var m in RigidModel.Read(rm).Lods[0].Meshes) for (var i = 0; i < 3; i++) { b[i] = MathF.Min(b[i], m.BoundsMin[i]); b[3 + i] = MathF.Max(b[3 + i], m.BoundsMax[i]); }
            return b;
        }
        var sceneW = 1784 * 128f * (T / 128f); var sceneD = 1405 * 128f * (T / 128f) * ZS;
        var tree = new TileQuadtree(gm, Size, r => (gm.Records[r].Flag & 1) != 0, Custom, T, sceneW, sceneD);
        var nodes = JsonDocument.Parse(File.ReadAllText("Z:/Claude/TerryClone/research/bob_re/frida_out/cam_s4h_qnodes.json")).RootElement.GetProperty("nodes").EnumerateArray().ToList();
        int leaves = 0, ok = 0, same = 0, placed = 0, tiles = 0; var shown = 0;
        foreach (var n in nodes)
        {
            var ts = n.GetProperty("tiles").EnumerateArray().Select(e => e.GetInt32()).ToList();
            if (ts.Count == 0) continue;
            leaves++;
            var b = n.GetProperty("b").EnumerateArray().Select(e => e.GetSingle()).ToArray();
            var mine = tree.LeafBounds(ts[0]);
            tiles += ts.Count;
            placed += ts.Count(t => ReferenceEquals(tree.LeafBounds(t), mine));
            if (mine is not null && mine[0] == b[0] && mine[1] == b[2] && mine[2] == b[3] && mine[3] == b[5]) ok++;
            else { var hasC = ts.Any(t => Custom(t) is not null); var key = hasC ? "with cliff" : "no cliff"; Miss[key] = Miss.GetValueOrDefault(key) + 1;
                   var cl = ts.Where(t => Custom(t) is not null).ToList();
                   if (cl.Count == 1 && mine is not null)
                   {
                       var o = gm.Records[cl[0]].Orientation & 0xF0; var sides = "";
                       if (mine[0] != b[0]) sides += $" x0 {mine[0] - b[0]:+0.0000;-0.0000}"; if (mine[1] != b[2]) sides += $" z0 {mine[1] - b[2]:+0.0000;-0.0000}";
                       if (mine[2] != b[3]) sides += $" x1 {mine[2] - b[3]:+0.0000;-0.0000}"; if (mine[3] != b[5]) sides += $" z1 {mine[3] - b[5]:+0.0000;-0.0000}";
                       var k2 = $"o{o:X2}"; Miss[k2] = Miss.GetValueOrDefault(k2) + 1;
                       if (Miss[k2] <= 6)
                       {
                           var rr = gm.Records[cl[0]]; var cbx = Custom(cl[0])!; var (uw2, uh2) = Size(cl[0])!.Value; float ss = T / 128f;
                           float Ta(float wx) => wx / ss - rr.X * 128f; float Tb(float wz) => wz / ZS / ss - rr.Y * 128f;
                           Console.WriteLine($"  O{o:X2} {gm.Paths[(int)rr.Path].Split((char)92)[^2]} W {uw2 * 128} H {uh2 * 128} mesh x {cbx[0]:F2}..{cbx[3]:F2} z {cbx[2]:F2}..{cbx[5]:F2} | bob a {Ta(b[0]):F2}..{Ta(b[3]):F2} b {Tb(b[2]):F2}..{Tb(b[5]):F2} | mine a {Ta(mine[0]):F2}..{Ta(mine[2]):F2} b {Tb(mine[1]):F2}..{Tb(mine[3]):F2}");
                       }
                       if (Miss[k2] <= 4) Console.WriteLine($"  ONE o{o:X2} {gm.Paths[(int)gm.Records[cl[0]].Path].Split((char)92)[^2]}:{sides}");
                   }
                   if (!hasC && Miss[key] <= 3) Console.WriteLine($"  NOCLIFF bob {b[0]:R},{b[2]:R},{b[3]:R},{b[5]:R} mine {(mine is null ? "-" : string.Join(",", mine.Select(v => v.ToString("R"))))} tiles {string.Join(" ", ts.Select(t => gm.Paths[(int)gm.Records[t].Path].Split((char)92)[^2] + ":" + gm.Records[t].X + "," + gm.Records[t].Y + ",o" + gm.Records[t].Orientation.ToString("X2")))}"); }
        }
        // misplaced tiles: BOB's leaf (dumped bounds) vs the tile's rect
        var leafOfTile = new Dictionary<int, float[]>();
        foreach (var n in nodes) { var bb = n.GetProperty("b").EnumerateArray().Select(e => e.GetSingle()).ToArray(); foreach (var t in n.GetProperty("tiles").EnumerateArray()) leafOfTile[t.GetInt32()] = bb; }
        var s = T / 128f; var k = 0;
        foreach (var (t, bb) in leafOfTile)
        {
            var mine = tree.LeafBounds(t);
            var others = leafOfTile.Where(kv => ReferenceEquals(kv.Value, bb)).Select(kv => kv.Key).ToList();
            if (mine is null || others.All(o => ReferenceEquals(tree.LeafBounds(o), mine))) continue;
            if (k++ > 5) break;
            var r = gm.Records[t]; var (uw, uh) = Size(t)!.Value; var (w, h) = (r.Orientation & 0xF0) is 0x20 or 0x80 ? (uh, uw) : (uw, uh);
            float ax0 = r.X * 128f * s, ax1 = r.X * 128f * s + w * 128f * s, az0 = r.Y * 128f * s * ZS, az1 = (r.Y * 128f * s + h * 128f * s) * ZS;
            Console.WriteLine($"  tile {t} {gm.Paths[(int)r.Path]} o{r.Orientation:X2} {w}x{h} rect {ax0},{az0}..{ax1},{az1} centre {(ax0 + ax1) * 0.5f},{(az0 + az1) * 0.5f} bob leaf {string.Join(",", bb.Select(v => v.ToString("G7")))} mine {string.Join(",", mine.Select(v => v.ToString("G7")))}");
        }
        foreach (var kv in Miss) Console.WriteLine($"  mismatched leaves {kv.Key}: {kv.Value}");
        Console.WriteLine($"[{mode}] tile leaves {leaves}: bounds exact {ok}; tiles placed together as BOB {placed}/{tiles}");
    }
}
