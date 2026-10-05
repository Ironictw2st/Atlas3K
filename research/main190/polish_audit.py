#!/usr/bin/env python3
"""Audit of the new-region dressing (village_dress dry run) - the 2026-10-03 polish rounds.
 ground : per settlement piece, |ground under the piece - the base it was seated on| (floating / buried pieces)
 trees  : village / camp pieces on hexes that carry a campaign tree (tree raster)
 props  : new pieces within 0.3 units of an existing kit prop (mountain, rock, tree mesh, stock settlement)
 tents  : tent pairs in one camp whose footprints overlap
 density: settlement pieces per 1000 land hexes, new regions vs stock"""
import re, sys, json, collections
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
import village_dress as V, trees_x15, prop_seat, town_fix as T
from hexgrid import nearest_hex
from PIL import Image
OUT = HERE / "ak" / "3k_dlc07_main_map"
V.add(OUT, dry=True); E = V.LAST
_, _, w, h, _, f, names = T.load(str(HERE / "hex" / "map.hex"))
P = []
for e in E:
    m = re.search(r'position="([^ ]+) ([^ ]+) ([^"]+)"', e); mp = re.search(r'model_path="([^"]*)"', e)
    P.append((float(m.group(1)), float(m.group(2)), float(m.group(3)), mp.group(1).lower() if mp else re.search(r'<(EC\w+)', e.split("\n", 1)[1]).group(1)))
xyz = np.array([p[:3] for p in P]); kind = [p[3] for p in P]
mesh = np.array(["/settlements/" in k for k in kind])
g = np.array([prop_seat.low_ground(x, z, 0) for x, y, z in xyz])
# ground: settlement pieces that should sit on the ground (dy small originally) - compare y to the ground under them
flo = (xyz[:, 1] - g)
base = mesh & (np.abs(flo) < 5)
print(f"ground: pieces {int(mesh.sum())}; y - ground under piece pct {np.percentile(flo[mesh], [1, 5, 50, 95, 99]).round(3)}; "
      f"buried < -0.08: {int((flo[mesh] < -0.08).sum())}")
tim = Image.open(HERE / "terrain" / trees_x15.TREE); tree = (trees_x15.hexvals(np.array(tim), w, h) != trees_x15.NO_TREE) & ~V.LAST_HEX   # the build clears LAST_HEX
c, r = nearest_hex(xyz[:, 0], xyz[:, 2], w, h)
print(f"trees: {int((tree[r, c] & mesh).sum())} settlement pieces on tree hexes ({len(set(zip(r[mesh & tree[r, c]], c[mesh & tree[r, c]])))} hexes)")
# existing props
ex = []
terry = open(OUT / "3k_dlc07_main_map.terry", encoding="utf-8", errors="replace").read(); used = set(re.findall(r'id="([0-9a-f]+)"', terry))
for p in OUT.glob("*.layer"):
    if p.name.split(".")[-2] not in used: continue
    t = open(p, encoding="utf-8", errors="replace").read()
    for m in re.finditer(r'<entity id="([0-9a-f]+)">.*?model_path="([^"]*)".*?position="([^ ]+) [^ ]+ ([^"]+)"', t, re.S):
        if m.group(1).startswith("0d"): continue
        ex.append((float(m.group(3)), float(m.group(4)), m.group(2).lower()))
et = cKDTree(np.array([e[:2] for e in ex]))
d, j = et.query(xyz[:, [0, 2]])
hit = mesh & (d < 0.3)
print(f"props: {int(hit.sum())} new pieces within 0.3 of an existing prop; by existing kind {collections.Counter(ex[i][2].split('/')[2] if ex[i][2].count('/') > 2 else ex[i][2] for i in j[hit]).most_common(6)}")
# tents
R = {k.lower(): v for k, v in V.R_TENT.items()}
ti = [i for i, k in enumerate(kind) if "settlements/tent_" in k]
tt = cKDTree(xyz[ti][:, [0, 2]]); ov = 0
for a, b in tt.query_pairs(1.0):
    ia, ib = ti[a], ti[b]
    if np.hypot(*(xyz[ia, [0, 2]] - xyz[ib, [0, 2]])) < 0.8 * 0.24 * (R.get(kind[ia], .5) + R.get(kind[ib], .5)): ov += 1
print(f"tents: {len(ti)} tents, {ov} overlapping pairs")
# density per region
land = f["terr"] == 0
reg = f["region"][r, c]
cnt = collections.Counter(int(k) for k, m_ in zip(reg, mesh) if m_)
ln = np.bincount(f["region"][land].ravel() + 1, minlength=len(names) + 1)[1:]
dens = sorted(((cnt.get(k, 0) / ln[k] * 1000, names[k]) for k in set(int(x) for x in reg) if ln[k] > 300))
print(f"density pieces/1000 land hexes: median {np.median([d_ for d_, _ in dens]):.0f}; lowest {[(round(a), b) for a, b in dens[:5]]}; highest {[(round(a), b) for a, b in dens[-3:]]}")
print("life:", collections.Counter(k for k in kind if k.lower().startswith("ec")))
