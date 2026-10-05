using System.Text.Json;
using Atlas3K.Formats.Maps;
using Atlas3K.Formats.Packs;

static class SideFit
{
    public static void Run()
    {
        float T = 595.1f / 1784f, ZS = 1.15476f, s = T / 128f, sz = s * ZS;
        var packs = PackSet.OpenVanilla(@"C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\data");
        var prefix = PackFile.Normalize(TileDatabase.Folder);
        var db = TileDatabase.Load(packs.Packs.SelectMany(p => p.Entries.Keys).Where(k => k.StartsWith(prefix, StringComparison.Ordinal)).Distinct().Select(k => packs.TryRead(k)).OfType<byte[]>());
        var gm = TileList.Read("Z:/Claude/TerryClone/Vanilla/Map/terrain/campaigns/3k_dlc07_main_map/global_map/tile_list.bin");
        var nodes = JsonDocument.Parse(File.ReadAllText("Z:/Claude/TerryClone/research/bob_re/frida_out/cam_s4h_qnodes.json")).RootElement.GetProperty("nodes").EnumerateArray().ToList();
        var hits = new Dictionary<string, int>();
        int sides = 0;
        foreach (var n in nodes)
        {
            var tiles = n.GetProperty("tiles").EnumerateArray().Select(e => e.GetInt32()).ToList();
            if (tiles.Count == 0) continue;
            var b = n.GetProperty("b").EnumerateArray().Select(e => e.GetSingle()).ToArray();
            foreach (var (side, v) in new[] { ("x0", b[0]), ("z0", b[2]), ("x1", b[3]), ("z1", b[5]) })
            {
                var cands = new Dictionary<string, bool>();
                foreach (var t in tiles)
                {
                    var r = gm.Records[t];
                    var tile = db[TileDatabase.NormalisePath(gm.Paths[(int)r.Path])];
                    var (w, h) = (r.Orientation & 0xF0) is 0x20 or 0x80 ? (tile.Height, tile.Width) : (tile.Width, tile.Height);
                    float X = r.X, Y = r.Y;
                    var f = new Dictionary<string, float>();
                    if (side == "x0") { f["X*128*s"] = X * 128f * s; f["X*T"] = X * T; f["(X*128)*s"] = (X * 128f) * s; }
                    if (side == "x1") { f["(X+w)*128*s"] = (X + w) * 128f * s; f["X*128*s+w*128*s"] = X * 128f * s + w * 128f * s; f["s*(w*128)+(X*128)*s"] = s * (w * 128f) + (X * 128f) * s; f["(X+w)*T"] = (X + w) * T; f["X*T+w*T"] = X * T + w * T; f["(w*128+X*128)*s"] = (w * 128f + X * 128f) * s; }
                    if (side == "z0") { f["Y*128*s*ZS"] = Y * 128f * s * ZS; f["Y*128*sz"] = Y * 128f * sz; f["Y*T*ZS"] = Y * T * ZS; }
                    if (side == "z1") { f["(Y+h)*128*s*ZS"] = (Y + h) * 128f * s * ZS; f["Y*128*s*ZS+h*128*sz"] = Y * 128f * s * ZS + h * 128f * sz; f["sz*(h*128)+(Y*128*s)*ZS"] = sz * (h * 128f) + (Y * 128f * s) * ZS; f["(Y+h)*128*sz"] = (Y + h) * 128f * sz; f["(Y+h)*T*ZS"] = (Y + h) * T * ZS; f["((Y+h)*128*s)*ZS"] = ((Y + h) * 128f * s) * ZS; f["z0+(h*128*s)*ZS"] = Y * 128f * s * ZS + (h * 128f * s) * ZS; f["(Y*128*s+h*128*s)*ZS"] = (Y * 128f * s + h * 128f * s) * ZS; f["z0+h*128*sz"] = Y * 128f * s * ZS + h * 128f * sz; f["(Y*128*s)*ZS+(h*128)*sz"] = (Y * 128f * s) * ZS + (h * 128f) * sz; }
                    foreach (var (k, val) in f) if (val == v) cands[k] = true;
                }
                if (cands.Count == 0) continue;
                sides++; hits["TOTAL " + side] = hits.GetValueOrDefault("TOTAL " + side) + 1;
                foreach (var k in cands.Keys) hits[side + " " + k] = hits.GetValueOrDefault(side + " " + k) + 1;
            }
        }
        Console.WriteLine($"leaf sides explained by some formula: {sides}");
        foreach (var (k, v) in hits.OrderBy(k => k.Key)) Console.WriteLine($"  {k}: {v}");
    }
}
