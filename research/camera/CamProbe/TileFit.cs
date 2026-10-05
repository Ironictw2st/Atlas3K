using System.Text.Json;
using Atlas3K.Core.Campaign.Camera;
using Atlas3K.Core.Campaign.Terrain;
using Atlas3K.Formats.Maps;
using Atlas3K.Formats.Packs;
using Atlas3K.Formats.Props;

static class TileFit
{
    static float Down(double v) { var f = (float)v; if (f > v) f = MathF.BitDecrement(f); return f; }
    public static void Run()
    {
        var game = @"C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\data";
        var packs = PackSet.OpenVanilla(game);
        var prefix = PackFile.Normalize(TileDatabase.Folder);
        var db = TileDatabase.Load(packs.Packs.SelectMany(p => p.Entries.Keys).Where(k => k.StartsWith(prefix, StringComparison.Ordinal)).Distinct().Select(k => packs.TryRead(k)).OfType<byte[]>());
        var tl = TileList.Read("Z:/Claude/TerryClone/Vanilla/Map/terrain/campaigns/3k_dlc07_main_map/tile_list.bin");
        var objs = JsonDocument.Parse(File.ReadAllText("Z:/Claude/TerryClone/research/bob_re/frida_out/cam_s4g_patches.json")).RootElement.GetProperty("objs")
            .EnumerateArray().Select(o => o.GetProperty("m").EnumerateArray().Select(e => e.GetSingle()).ToArray()).ToList();
        var byPos = objs.GroupBy(m => ((int)Math.Floor(m[3]), (int)Math.Floor(m[11]))).ToDictionary(g => g.Key, g => g.ToList());
        float T = 595.1f / 1784f, ZS = 1.15476f;
        var sCands = new Dictionary<string, float> { ["T/128"] = T / 128f, ["T*(1/128)"] = T * (1f / 128f), ["595.1/228352"] = 595.1f / 228352f };
        var cache = new Dictionary<string, List<float[]>>();
        var lfMap = CompressedMap.Read("Z:/Claude/TerryClone/Vanilla/Map/terrain/campaigns/3k_dlc07_main_map/lf_height_map.compressed_map");
        var th = new TileHfHeight(tl, db, packs.TryRead, lfMap, T);
        var gfit = new Dictionary<string, int>();
        var rot = new Dictionary<string, int>(); var tx = new Dictionary<string, int>(); var tz = new Dictionary<string, int>();
        int n = 0;
        foreach (var rec in tl.Records)
        {
            var key = TileDatabase.NormalisePath(tl.Paths[(int)rec.Path]);
            if (!db.TryGetValue(key, out var tile)) continue;
            if (!cache.TryGetValue(key, out var props))
            {
                props = [];
                if (packs.TryRead(key.Replace((char)92, '/') + "bmd_data.bin") is { } b)
                {
                    var ro = GlobalProps.ReadBody(b);
                    for (var i = 0; i < ro.Props.Count; i++) if (ro.Props[i].HasHeightPatch) props.Add(ro.PropMatrices[i]);
                }
                cache[key] = props;
            }
            foreach (var raw in props)
            {
                var guess = CameraHeightField.TileProp(rec, tile.Width, tile.Height, T, raw);
                if (!byPos.TryGetValue(((int)Math.Floor(guess[3]), (int)Math.Floor(guess[11])), out var l)) continue;
                var bob = l.FirstOrDefault(q => Math.Abs(q[3] - guess[3]) < 1e-3 && Math.Abs(q[11] - guess[11]) < 1e-3);
                if (bob is null) continue;
                n++;
                var o = rec.Orientation & 0xF0;
                {
                    var s0 = T / 128f; var szz = s0 * ZS;
                    float lzz = o switch { 0x10 => raw[11], 0x20 => -raw[9], 0x40 => -raw[11], _ => raw[9] };
                    float ozz = o switch { 0x10 or 0x80 => rec.Y * 128f, 0x20 => tile.Width * 128f + rec.Y * 128f, _ => tile.Height * 128f + rec.Y * 128f };
                    var yl = (s0 * 5f) * raw[10];
                    var ground = bob[7] - yl;
                    var zt1 = guess[11] / ZS; var zt2 = (s0 * 5f) * lzz + ozz * s0; var zt3 = bob[11] / ZS;
                    var cands = new Dictionary<string, float>
                    {
                        ["H(x, m11/ZS)"] = th.Height(guess[3], zt1),
                        ["H(x, tile z)"] = th.Height(guess[3], zt2),
                        ["H(x, bob m11/ZS)"] = th.Height(guess[3], zt3),
                        ["Lf(x, tile z)"] = th.Lf(guess[3], zt2),
                        ["Lf(x, m11/ZS)"] = th.Lf(guess[3], zt1),
                    };
                    foreach (var (cn, cv) in cands) if (yl + cv == bob[7]) gfit[cn] = gfit.GetValueOrDefault(cn) + 1;
                    gfit["total"] = gfit.GetValueOrDefault("total") + 1;
                }
                foreach (var (sn, s) in sCands)
                {
                    var sz = s * ZS;
                    float px = rec.X * 128f, pz = rec.Y * 128f, w = tile.Width * 128f, h = tile.Height * 128f;
                    // rotation entries: row 0 uses t0 (s, sign) on one p row; row 2 uses sz
                    // p rows: P[k][c] = raw[c*3+k]
                    int k0 = o is 0x10 or 0x40 ? 0 : 2, k2 = o is 0x10 or 0x40 ? 2 : 0;
                    float sg0 = o is 0x40 or 0x80 ? -1 : 1, sg2 = o is 0x40 or 0x20 ? -1 : 1;
                    var variants = new Dictionary<string, Func<float, float, float>>
                    {
                        ["t*(5p)"] = (t, p) => t * (5f * p),
                        ["(t*5)*p"] = (t, p) => (t * 5f) * p,
                        ["(t*p)*5"] = (t, p) => (t * p) * 5f,
                    };
                    foreach (var (vn, f) in variants)
                    {
                        var ok = true;
                        for (var c = 0; c < 3; c++)
                        {
                            ok &= f(sg0 * s, raw[c * 3 + k0]) == bob[c];
                            ok &= f(s, raw[c * 3 + 1]) == bob[4 + c];
                            ok &= f(sg2 * sz, raw[c * 3 + k2]) == bob[8 + c];
                        }
                        var key2 = sn + " " + vn;
                        if (ok) rot[key2] = rot.GetValueOrDefault(key2) + 1;
                    }
                    // translation x
                    float a = raw[9], bb = raw[11];
                    float lx = o switch { 0x10 => a, 0x20 => bb, 0x40 => -a, _ => -bb };
                    float ox = o switch { 0x10 or 0x20 => px, 0x40 => w + px, _ => h + px };
                    var txv = new Dictionary<string, float>
                    {
                        ["s*(5l)+ox*s"] = s * (5f * lx) + ox * s,
                        ["ox*s+s*(5l)"] = ox * s + s * (5f * lx),
                        ["(5l+ox)*s"] = (5f * lx + ox) * s,
                        ["fma(s5,l,ox*s)"] = MathF.FusedMultiplyAdd(s * 5f, lx, ox * s),
                        ["fma(ox,s,s5*l)"] = MathF.FusedMultiplyAdd(ox, s, (s * 5f) * lx),
                        ["(s*5)*l+ox*s"] = (s * 5f) * lx + ox * s,
                        ["(s*l)*5+ox*s"] = (s * lx) * 5f + ox * s,
                    };
                    foreach (var (vn, v) in txv) if (v == bob[3]) tx[sn + " " + vn] = tx.GetValueOrDefault(sn + " " + vn) + 1;
                    float lz = o switch { 0x10 => bb, 0x20 => -a, 0x40 => -bb, _ => a };
                    float oz = o switch { 0x10 or 0x80 => pz, 0x20 => w + pz, _ => h + pz };
                    var tzv = new Dictionary<string, float>
                    {
                        ["sz*(5l)+oz*sz"] = sz * (5f * lz) + oz * sz,
                        ["(5l+oz)*sz"] = (5f * lz + oz) * sz,
                        ["(sz*5)*l+oz*sz"] = (sz * 5f) * lz + oz * sz,
                        ["(sz*l)*5+oz*sz"] = (sz * lz) * 5f + oz * sz,
                        ["down(sz5*l+oz*sz exact)"] = Down((double)(sz * 5f) * lz + (double)oz * sz),
                        ["down(((s5)*l+oz*s)*ZS exact)"] = Down(((double)(s * 5f) * lz + (double)oz * s) * ZS),
                        ["down(sz5*l + down(oz*sz))"] = Down((double)(sz * 5f) * lz + Down((double)oz * sz)),
                        ["f(zt*1.15476d)"] = (float)((double)((s * 5f) * lz + oz * s) * 1.15476),
                        ["f(zt*(double)ZSf)"] = (float)((double)((s * 5f) * lz + oz * s) * (double)ZS),
                        ["(s5*l)*ZS+(oz*s)*ZS"] = ((s * 5f) * lz) * ZS + (oz * s) * ZS,
                        ["((s5)*ZS)*l+(oz*s)*ZS"] = ((s * 5f) * ZS) * lz + (oz * s) * ZS,
                        ["sz5*l+(oz*s)*ZS"] = (sz * 5f) * lz + (oz * s) * ZS,
                        ["rt /ZS*ZS"] = ((sz * 5f) * lz + oz * sz) / ZS * ZS,
                        ["rt *(1/ZS)*ZS"] = ((sz * 5f) * lz + oz * sz) * (1f / ZS) * ZS,
                        ["fma(sz5,l,oz*sz)"] = MathF.FusedMultiplyAdd(sz * 5f, lz, oz * sz),
                        ["fma(oz,sz,sz5*l)"] = MathF.FusedMultiplyAdd(oz, sz, (sz * 5f) * lz),
                        ["double"] = (float)((double)(sz * 5f) * lz + (double)oz * sz),
                        ["((s*5)*l+oz*s)*ZS"] = ((s * 5f) * lz + oz * s) * ZS,
                        ["((s*5)*l+oz*s)/(1/ZS)"] = ((s * 5f) * lz + oz * s) / (1f / ZS),
                        ["((5l+oz)*s)*ZS"] = ((5f * lz + oz) * s) * ZS,
                        ["(s*(5l)+oz*s)*ZS"] = (s * (5f * lz) + oz * s) * ZS,
                        ["(s*5*ZS)*l + oz*(s*ZS)"] = ((s * 5f) * ZS) * lz + oz * sz,
                    };
                    foreach (var (vn, v) in tzv) if (v == bob[11]) tz[sn + " " + vn] = tz.GetValueOrDefault(sn + " " + vn) + 1;
                    if (sn == "T/128")
                    {
                        var ok = (sz * 5f) * lz + oz * sz == bob[11];
                        var k3 = $"o{o:X} {(ok ? "ok" : "bad")}"; tz[k3] = tz.GetValueOrDefault(k3) + 1;
                        if (!ok && tz.GetValueOrDefault("shown" + o) < 2) { tz["shown" + o] = tz.GetValueOrDefault("shown" + o) + 1; Console.WriteLine($"o{o:X} bob {bob[11]:R} mine {(sz * 5f) * lz + oz * sz:R} lz {lz:R} oz {oz} rec {rec.X},{rec.Y} tile {tile.Width}x{tile.Height} alt (oz+5l*?) {((5f * lz) + oz) * sz:R} d {(double)bob[11] - ((double)sz * 5 * lz + oz * (double)sz):G4}"); }
                    }
                }
            }
        }
        Console.WriteLine($"matched {n}");
        foreach (var (k, v) in gfit.OrderByDescending(x => x.Value)) Console.WriteLine($"ground {k}: {v}");
        foreach (var (k, v) in rot.OrderByDescending(x => x.Value)) Console.WriteLine($"rot {k}: {v}");
        foreach (var (k, v) in tx.OrderByDescending(x => x.Value)) Console.WriteLine($"tx {k}: {v}");
        foreach (var (k, v) in tz.OrderByDescending(x => x.Value)) Console.WriteLine($"tz {k}: {v}");
    }
}
