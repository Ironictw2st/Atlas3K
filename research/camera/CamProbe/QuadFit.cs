using System.Text.Json;
using Atlas3K.Formats.Maps;
using Atlas3K.Formats.Packs;

static class QuadFit
{
    static readonly Dictionary<string, int> Cat = new();
    static List<float[]> Aabbs = [];
    // get_tile_transform applied to a tile-space point (a, b): x = t0·a + t2·b + t3, z = t8·a + t10·b + t11
    static (float, float) Xf(TileList.Record r, int tw, int th, float T, float ZS, float a, float b)
    {
        var s = T / 128f; var sz = s * ZS; float px = r.X * 128f, pz = r.Y * 128f, w = tw * 128f, h = th * 128f;
        float t0 = 0, t2 = 0, t3, t8 = 0, t10 = 0, t11;
        switch (r.Orientation & 0xF0)
        {
            case 0x20: t2 = s; t3 = px * s; t8 = -sz; t11 = (w + pz) * s * ZS; break;
            case 0x40: t0 = -s; t3 = (w + px) * s; t10 = -sz; t11 = (h + pz) * s * ZS; break;
            case 0x80: t2 = -s; t3 = (h + px) * s; t8 = sz; t11 = pz * s * ZS; break;
            default: t0 = s; t3 = px * s; t10 = sz; t11 = pz * s * ZS; break;
        }
        return (t0 * a + 0f * 0f + t2 * b + t3, t8 * a + 0f * 0f + t10 * b + t11);
    }
    static readonly Dictionary<string, float[]?> CustomCache = new();
    static float[]? Custom(PackSet packs, string folder)
    {
        if (CustomCache.TryGetValue(folder, out var c)) return c;
        c = null;
        var f = folder.Replace((char)92, '/');
        if (packs.TryRead(f + "custom_mesh.wsmodel") is { } ws && Atlas3K.Formats.Models.RigidModelGeometry.WsModelGeometryPath(ws) is { } geo && packs.TryRead(geo) is { } rm)
        {
            var model = Atlas3K.Formats.Models.RigidModel.Read(rm);
            float[] b = [float.MaxValue, float.MaxValue, float.MaxValue, float.MinValue, float.MinValue, float.MinValue];
            var mode = Environment.GetEnvironmentVariable("CB") ?? "all";
            var meshes = mode == "first" ? model.Lods[0].Meshes.Take(1) : mode == "alllods" ? model.Lods.SelectMany(l => l.Meshes) : model.Lods[0].Meshes;
            foreach (var m in meshes)
            {
                if (mode == "verts")
                    for (var v = 0; v < m.Positions.Length; v += 3) for (var i = 0; i < 3; i++) { b[i] = MathF.Min(b[i], m.Positions[v + i]); b[3 + i] = MathF.Max(b[3 + i], m.Positions[v + i]); }
                else
                    for (var i = 0; i < 3; i++) { b[i] = MathF.Min(b[i], m.BoundsMin[i]); b[3 + i] = MathF.Max(b[3 + i], m.BoundsMax[i]); }
            }
            c = b;
        }
        return CustomCache[folder] = c;
    }
    sealed class Node { public float[] Box = new float[4]; public Node[]? Kids; public int Depth; public float[] Dump = []; public List<int> Tiles = []; public List<int> Ids = []; }

    static Node Build(float x0, float z0, float x1, float z1, int depth)
    {
        var n = new Node { Box = [x0, z0, x1, z1], Depth = depth };
        if (depth < 7)
        {
            var mx = (x1 + x0) * 0.5f; var mz = (z1 + z0) * 0.5f;
            n.Kids = [Build(x0, mz, mx, z1, depth + 1), Build(mx, mz, x1, z1, depth + 1), Build(x0, z0, mx, mz, depth + 1), Build(mx, z0, x1, mz, depth + 1)];
        }
        return n;
    }

    public static void Run()
    {
        float T = 595.1f / 1784f, ZS = 1.15476f;
        var sceneW = 1784 * 128f * (T / 128f); var sceneD = 1405 * 128f * (T / 128f) * ZS;
        var root = Build(-1f, -1f, sceneW, sceneD, 0);
        var nodes = JsonDocument.Parse(File.ReadAllText("Z:/Claude/TerryClone/research/bob_re/frida_out/cam_s4h_qnodes.json")).RootElement.GetProperty("nodes").EnumerateArray().ToList();
        // the dump's DFS: pop last, push children 0..3
        var order = new List<Node>(); var stack = new Stack<Node>(); stack.Push(root);
        while (stack.Count > 0) { var n = stack.Pop(); order.Add(n); if (n.Kids != null) foreach (var k in n.Kids) stack.Push(k); }
        Console.WriteLine($"regular nodes {order.Count}, dumped {nodes.Count}");
        int depthOk = 0;
        for (var i = 0; i < order.Count; i++)
        {
            var d = nodes[i]; order[i].Dump = d.GetProperty("b").EnumerateArray().Select(e => e.GetSingle()).ToArray();
            if (d.GetProperty("d").GetInt32() == order[i].Depth) depthOk++;
            foreach (var t in d.GetProperty("tiles").EnumerateArray()) order[i].Tiles.Add(t.GetInt32());
            foreach (var t in d.GetProperty("ids").EnumerateArray()) order[i].Ids.Add(t.GetInt32());
        }
        Console.WriteLine($"depth sequence matches {depthOk}/{order.Count}");
        int regEmpty = 0, empty = 0;
        foreach (var n in order.Where(n => n.Depth == 7 && n.Tiles.Count == 0 && n.Dump.Length == 6))
        {
            empty++;
            if (n.Dump[0] == n.Box[0] && n.Dump[2] == n.Box[1] && n.Dump[3] == n.Box[2] && n.Dump[5] == n.Box[3]) regEmpty++;
        }
        Console.WriteLine($"leaves without tiles whose dumped x/z bounds equal the regular box: {regEmpty}/{empty}");

        // tiles: sizes from the tile database
        var packs = PackSet.OpenVanilla(@"C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\data");
        var prefix = PackFile.Normalize(TileDatabase.Folder);
        var db = TileDatabase.Load(packs.Packs.SelectMany(p => p.Entries.Keys).Where(k => k.StartsWith(prefix, StringComparison.Ordinal)).Distinct().Select(k => packs.TryRead(k)).OfType<byte[]>());
        var gm = TileList.Read("Z:/Claude/TerryClone/Vanilla/Map/terrain/campaigns/3k_dlc07_main_map/global_map/tile_list.bin");
        var pointHits = new Dictionary<string, int>();
        Aabbs = JsonDocument.Parse(File.ReadAllText("Z:/Claude/TerryClone/research/bob_re/frida_out/cam_s4h_patches.json")).RootElement.GetProperty("objs")
            .EnumerateArray().Select(o => o.GetProperty("aabb").EnumerateArray().Select(e => e.GetSingle()).ToArray()).ToList();
        var growOk = 0; var growN = 0; var shown = 0;
        foreach (var leaf in order.Where(n => n.Tiles.Count > 0))
        {
            float ux0 = leaf.Box[0], uz0 = leaf.Box[1], ux1 = leaf.Box[2], uz1 = leaf.Box[3];
            foreach (var t in leaf.Tiles)
            {
                var r = gm.Records[t];
                var tile = db[TileDatabase.NormalisePath(gm.Paths[(int)r.Path])];
                var (w, h) = (r.Orientation & 0xF0) is 0x20 or 0x80 ? (tile.Height, tile.Width) : (tile.Width, tile.Height);
                float ax0 = r.X * 128f * (T / 128f), ax1 = (r.X + w) * 128f * (T / 128f), az0 = r.Y * 128f * (T / 128f) * ZS, az1 = (r.Y + h) * 128f * (T / 128f) * ZS;
                if (Environment.GetEnvironmentVariable("XF") == "1")
                {
                    var corners = new List<(float, float)> { (0, 0), (tile.Width * 128f, 0), (0, tile.Height * 128f), (tile.Width * 128f, tile.Height * 128f) };
                    (ax0, az0, ax1, az1) = (float.MaxValue, float.MaxValue, float.MinValue, float.MinValue);
                    foreach (var (ca, cbz) in corners) { var (wx, wz) = Xf(r, tile.Width, tile.Height, T, ZS, ca, cbz); ax0 = MathF.Min(ax0, wx); ax1 = MathF.Max(ax1, wx); az0 = MathF.Min(az0, wz); az1 = MathF.Max(az1, wz); }
                }
                var pts = new Dictionary<string, (float, float)>
                {
                    ["centre"] = ((ax0 + ax1) * 0.5f, (az0 + az1) * 0.5f),
                    ["min corner"] = (ax0, az0),
                    ["max corner"] = (ax1, az1),
                };
                foreach (var (pn, (px, pz)) in pts)
                    if (leaf.Box[0] <= px && px <= leaf.Box[2] && leaf.Box[1] <= pz && pz <= leaf.Box[3]) pointHits[pn] = pointHits.GetValueOrDefault(pn) + 1;
                ux0 = MathF.Min(ux0, ax0); ux1 = MathF.Max(ux1, ax1); uz0 = MathF.Min(uz0, az0); uz1 = MathF.Max(uz1, az1);
                var co = Environment.GetEnvironmentVariable("CO") ?? "all";
                if ((co == "all" || (co == "o10" && (r.Orientation & 0xF0) == 0x10) || (co == "swap" )) && Custom(packs, gm.Paths[(int)r.Path]) is { } cb)
                {
                    // custom mesh: tile space a = x, b = z + H (unturned size W x H, 128 per cell), then get_tile_transform
                    float W = tile.Width * 128f, H = tile.Height * 128f, s = T / 128f, sz = s * ZS, px = r.X * 128f, pz = r.Y * 128f;
                    foreach (var (ca, cb2) in new[] { (cb[0], cb[2] + H), (cb[3], cb[2] + H), (cb[0], cb[5] + H), (cb[3], cb[5] + H) })
                    {
                        var (ta, tb) = co == "swap"
                            ? (r.Orientation & 0xF0) switch { 0x20 => (H - cb2, ca), 0x40 => (W - ca, H - cb2), 0x80 => (cb2, W - ca), _ => (ca, cb2) }
                            : (r.Orientation & 0xF0) switch { 0x20 => (cb2, W - ca), 0x40 => (W - ca, H - cb2), 0x80 => (H - cb2, ca), _ => (ca, cb2) };
                        var (wx, wz) = Environment.GetEnvironmentVariable("XF") == "1" ? Xf(r, tile.Width, tile.Height, T, ZS, ca, cb2) : ((ta + px) * s, (tb + pz) * s * ZS);
                        ux0 = MathF.Min(ux0, wx); ux1 = MathF.Max(ux1, wx); uz0 = MathF.Min(uz0, wz); uz1 = MathF.Max(uz1, wz);
                    }
                }
            }
            foreach (var id in leaf.Ids)
            {
                var a = Aabbs[id];
                ux0 = MathF.Min(ux0, a[0]); uz0 = MathF.Min(uz0, a[1]); ux1 = MathF.Max(ux1, a[2]); uz1 = MathF.Max(uz1, a[3]);
            }
            growN++;
            var ok = leaf.Dump[0] == ux0 && leaf.Dump[2] == uz0 && leaf.Dump[3] == ux1 && leaf.Dump[5] == uz1;
            if (ok) growOk++;
            else
            {
                foreach (var t in leaf.Tiles)
                {
                    var r = gm.Records[t]; var tp = gm.Paths[(int)r.Path];
                    var tile = db[TileDatabase.NormalisePath(tp)];
                    var (w, h) = (r.Orientation & 0xF0) is 0x20 or 0x80 ? (tile.Height, tile.Width) : (tile.Width, tile.Height);
                    float ax0 = r.X * 128f * (T / 128f), ax1 = (r.X + w) * 128f * (T / 128f), az0 = r.Y * 128f * (T / 128f) * ZS, az1 = (r.Y + h) * 128f * (T / 128f) * ZS;
                    var touches = leaf.Dump[0] == ax0 || leaf.Dump[3] == ax1 || leaf.Dump[2] == az0 || leaf.Dump[5] == az1;
                    var key = System.Text.RegularExpressions.Regex.Replace(tp, @"\[^\]*\$", "");
                    Cat[key] = Cat.GetValueOrDefault(key) + 1;
                }
            }
            var noCustom = leaf.Tiles.All(t => Custom(packs, gm.Paths[(int)gm.Records[t].Path]) is null);
            if (!ok && noCustom && shown < 3) foreach (var t in leaf.Tiles)
            {
                var r = gm.Records[t]; var tile = db[TileDatabase.NormalisePath(gm.Paths[(int)r.Path])];
                var (w, h) = (r.Orientation & 0xF0) is 0x20 or 0x80 ? (tile.Height, tile.Width) : (tile.Width, tile.Height);
                Console.WriteLine($"     tile {t} {gm.Paths[(int)r.Path]} at {r.X},{r.Y} o{r.Orientation:X2} {w}x{h} rect x {r.X * T:R}..{(r.X + w) * T:R} z {r.Y * T * ZS:R}..{(r.Y + h) * T * ZS:R}");
            }
            if (!ok && noCustom && shown++ < 3) Console.WriteLine($"  leaf dump {leaf.Dump[0]:R},{leaf.Dump[2]:R},{leaf.Dump[3]:R},{leaf.Dump[5]:R} union {ux0:R},{uz0:R},{ux1:R},{uz1:R} box {string.Join(",", leaf.Box)}");
        }
        foreach (var (k, v) in Cat.OrderByDescending(x => x.Value).Take(12)) Console.WriteLine($"   tiles in mismatched leaves: {k} {v}");
        Console.WriteLine($"tile leaves {growN}: dumped bounds == union(regular box, tile AABBs) {growOk}");
        foreach (var (k, v) in pointHits) Console.WriteLine($"  tile point '{k}' inside its regular leaf: {v}/{order.Sum(n => n.Tiles.Count)}");
        // ancestors: dumped bounds vs union of children
        int anc = 0, ancOk = 0;
        foreach (var n in order.Where(n => n.Kids != null))
        {
            anc++;
            float x0 = n.Box[0], z0 = n.Box[1], x1 = n.Box[2], z1 = n.Box[3];
            foreach (var k in n.Kids!) { x0 = MathF.Min(x0, k.Dump[0]); z0 = MathF.Min(z0, k.Dump[2]); x1 = MathF.Max(x1, k.Dump[3]); z1 = MathF.Max(z1, k.Dump[5]); }
            if (n.Dump[0] == x0 && n.Dump[2] == z0 && n.Dump[3] == x1 && n.Dump[5] == z1) ancOk++;
        }
        Console.WriteLine($"inner nodes {anc}: dumped == union(regular box, children's dumped) {ancOk}");
    }
}
