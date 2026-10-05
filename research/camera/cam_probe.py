"""Compare BOB's height function (probe dump) with the prototype's components at the same points.
usage: cam_probe.py <global_meshes dir> <bobblocks.npy> <patches.json> <patchmap.json> <probe_points.json> <probe.json> <cells.json>"""
import json, sys, collections
import numpy as np
sys.path.insert(0, r"Z:/Claude/TerryClone/research/trees")
import camap_read
from cam_gm import height_gm, F
from cam_full import sample_patch, NEG, INV

gm, bnp, pj, pm, ptsf, prf, cellsf = sys.argv[1:8]
blocks = np.load(bnp)
maps = {int(b[0]): camap_read.read(f"{gm}/land_mesh_{int(b[0])}.compressed_map") for b in blocks}
objs = json.load(open(pj))["objs"]; pmap = {int(k): v for k, v in json.load(open(pm)).items()}
pts = np.array(json.load(open(ptsf)), np.float32); bobh = np.array(json.load(open(prf))["heights"], np.float32)
cells = json.load(open(cellsf))
px, pz = pts[:, 0].astype(F), pts[:, 1].astype(F)
g = height_gm(px, pz, blocks, maps, "bob", 0)
p = np.full(px.shape, NEG); hits = [[] for _ in range(len(px))]
cache = {}
for o in objs:
    a = o["aabb"]
    m = (px >= F(a[0])) & (px <= F(a[2])) & (pz >= F(a[1])) & (pz <= F(a[3]))
    if not m.any(): continue
    idx = np.nonzero(m)[0]; x, z = px[idx], pz[idx]
    inv = [F(t) for t in o["inv"]]; loc = [F(t) for t in o["local"]]; mm = [F(t) for t in o["m"]]
    lx = ((z * inv[2]).astype(F) + (x * inv[0]).astype(F) + inv[3]).astype(F)
    lz = ((z * inv[10]).astype(F) + (x * inv[8]).astype(F) + inv[11]).astype(F)
    ok = (loc[0] <= lx) & (lx <= loc[2]) & (loc[1] <= lz) & (lz <= loc[3])
    if not ok.any(): continue
    uu = ((lx - loc[0]).astype(F) / (loc[2] - loc[0])).astype(F); vv = ((lz - loc[1]).astype(F) / (loc[3] - loc[1])).astype(F)
    path = pmap[o["i"]]
    if path not in cache: raw, hdr = camap_read.read(path); cache[path] = (raw, F(hdr[1]), F(hdr[4]))
    raw, lo, hi = cache[path]
    hh = sample_patch(raw, lo, hi, uu, vv)
    sc = np.sqrt(F(F(F(mm[5] * mm[5]) + F(mm[1] * mm[1])) + F(mm[9] * mm[9]))).astype(F)
    val = np.where(ok & (hh != INV), ((sc * hh).astype(F) + mm[7]).astype(F), NEG)
    for j, v in zip(idx, val):
        if v > NEG: hits[j].append((o["i"], float(v)))
    p[idx] = np.maximum(p[idx], val)
gfb = np.where(g > INV, g, F(0))
mine = np.where(gfb <= p, p, gfb)
ex = mine.view(np.int32) == bobh.view(np.int32)
print(f"points {len(px)}: bit-exact {ex.mean():.4%}")
cat = collections.Counter(); exs = collections.Counter()
for i in range(len(px)):
    c = cells[i][0]; cat[c] += 1; exs[c] += int(ex[i])
print({c: f"{exs[c]}/{cat[c]}" for c in cat})
bad = np.nonzero(~ex)[0]
kinds = collections.Counter()
for i in bad:
    gi, pi_, b = float(g[i]), float(p[i]), float(bobh[i])
    if gi <= -50 and b > 0 and pi_ < b: k = "gm invalid -> bob uses fallback>0"
    elif pi_ > NEG and abs(pi_ - b) < 1e-6 * max(1, abs(b)) * 10: k = "bob = patch value (mine chose gm?)"
    elif gi > -50 and abs(gi - b) < 1e-4: k = "bob ~ gm (patch too high in mine?)"
    elif b > max(gi, pi_): k = "bob above both"
    elif b < max(gi, pi_): k = "bob below mine"
    else: k = "other"
    kinds[k] += 1
print(kinds.most_common())
np.savez("probe_cmp.npz", g=g, p=p, mine=mine, bob=bobh, px=px, pz=pz)
for i in bad[:12]:
    print(cells[i], f"x {px[i]:.4f} z {pz[i]:.4f}  bob {bobh[i]:.6f}  gm {g[i]:.6f}  patch {p[i]:.6f}  hits {hits[i][:3]}")
