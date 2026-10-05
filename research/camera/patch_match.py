"""Match BOB's dumped height-patch objects (frida_campatch.js) to compressed maps on disk by (w, h, lo, hi, probe values).
Writes <dump>_patchmap.json: object index -> map path. usage: patch_match.py <patches.json> <map dir> [<map dir> ...]"""
import glob, json, sys
import numpy as np
sys.path.insert(0, r"Z:/Claude/TerryClone/research/trees")
import camap_read
F = np.float32


def fingerprint(path):
    raw, hdr = camap_read.read(path)
    h, w = raw.shape; lo, hi = F(hdr[1]), F(hdr[4])
    vf = lambda x, y: float(((F(raw[y, x]) * F(1 / 65535)).astype(F) * (hi - lo) + lo).astype(F))
    pts = [[0, 0], [w >> 1, h >> 1], [w - 1, h - 1], [w >> 2, (3 * h) >> 2]]
    st = 2 if w * h > 4096 else 1; n = 0; sm = 0.0
    vals = ((raw.astype(F) * F(1 / 65535)).astype(F) * (hi - lo) + lo).astype(F)
    for y in range(0, h, st):
        for x in range(0, w, st):
            v = vals[y, x]
            if v > -49.999: n += 1; sm += float(v) * ((x * 7 + y * 13) % 17 + 1)
    return (w, h, round(float(lo), 4), round(float(hi), 4), tuple(round(vf(*p), 4) for p in pts), n, round(sm, 1))


if __name__ == "__main__":
    d = json.load(open(sys.argv[1])); objs = d["objs"]
    table = {}
    for root in sys.argv[2:]:
        for p in glob.glob(root + "/**/*.compressed_map", recursive=True):
            try: table.setdefault(fingerprint(p), []).append(p)
            except Exception as e: print("skip", p, e)
    out, miss = {}, {}
    for o in objs:
        c = o["cm"]; key = (c["w"], c["h"], round(c["lo"], 4), round(c["hi"], 4), tuple(round(v, 4) for v in c["probe"]), c["sum"][0], round(c["sum"][1], 1))
        if key in table: out[o["i"]] = table[key][0]
        else: miss[key] = miss.get(key, 0) + 1
    print(f"{len(out)} of {len(objs)} objects matched; {len(table)} maps fingerprinted; {len(miss)} unmatched shapes")
    for k, v in sorted(miss.items(), key=lambda kv: -kv[1])[:8]: print("  unmatched", v, k)
    amb = sum(1 for v in table.values() if len(v) > 1); print("ambiguous fingerprints", amb)
    json.dump(out, open(sys.argv[1].replace("_patches.json", "_patchmap.json"), "w"))
