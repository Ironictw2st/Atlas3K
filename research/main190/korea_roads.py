"""Korea road diagnostics (read-only): road components, settlements off-road, dead ends, roads on impassable."""
import sys, numpy as np
from pathlib import Path
sys.path.insert(0, "guandu"); sys.path.insert(0, ".")
import crop_scale_map_hex as C, hexmap
from rebuild_hex import unpack, components
from hexgrid import neighbour
p = sys.argv[1] if len(sys.argv) > 1 else "main190/hex/map.hex"; src = Path(p).read_bytes()
L = hexmap.load(p)["lists"]; names = L["land_regions"] + L["sea_regions"]
P, w, h = C.locate_dims(src); g = np.frombuffer(src, np.uint8, 16 * w * h, P + 8).reshape(h, w, 16); f = unpack(g)
box = [int(v) for v in sys.argv[2].split(",")] if len(sys.argv) > 2 else [440, 760, 960, 1132]
K = np.zeros((h, w), bool); K[box[0]:box[1], box[2]:box[3]] = True
K &= np.isin(f["region"], [i for i, n in enumerate(names) if n.startswith("ironic_region_")])
road = (f["road"] > 0) & K
comps = sorted(components(road), key=len, reverse=True)
print("Korea road hexes", road.sum(), "components", [len(c) for c in comps][:15])
# settlements: region -> slot 0 centre (mean of slot-0 hexes); on/next to road?
for k in sorted(set(f["region"][K])):
    m = K & (f["region"] == k) & (f["slot"] == 0)
    if not m.any(): print(f"  {names[k]:40s} NO SLOT 0"); continue
    rr, cc = np.nonzero(m); on = (f["road"][m] > 0).any()
    ci = [i for i, c in enumerate(comps) if any(m[r, q] for q, r in c)]
    print(f"  {names[k]:40s} slot0 {len(rr):2d} hexes at ~({int(cc.mean())},{int(rr.mean())}) road-on-slot {on} comp {ci[:3]}")
# dead ends: road hex with exactly one road-bit neighbour pointing and not in a slot
de = []
for r, c in zip(*np.nonzero(road)):
    nb = sum(1 for d in range(6) if (f["road"][r, c] >> d) & 1)
    if nb <= 1 and f["slot"][r, c] < 0: de.append((c, r, nb))
print("dead ends (not in a slot):", len(de), de[:30])
print("roads on impassable:", int((road & (f["imp"] == 1)).sum()), " on beach/cliff:", int((road & np.isin(f["terr"], (2, 3))).sum()))
# asymmetric road bits
bad = 0
for r, c in zip(*np.nonzero(road)):
    for d in range(6):
        if (f["road"][r, c] >> d) & 1:
            nc, nr = neighbour(c, r, d)
            if not (0 <= nc < w and 0 <= nr < h) or not ((f["road"][nr, nc] >> ((d + 3) % 6)) & 1): bad += 1
print("one-way road bits:", bad)

# network: roads + settlement slot/sprawl hexes as connectors (Korea + a margin for the Liaodong link)
net = ((f["road"] > 0) | (f["slot"] >= 0) | (f["sprawl"] == 1)) & (f["terr"] != 1)
KK = np.zeros((h, w), bool); KK[box[0]:box[1], box[2] - 60:box[3]] = True
nc = sorted(components(net & KK), key=len, reverse=True)
setl = {}
for k in sorted(set(f["region"][K])):
    m = K & (f["region"] == k) & (f["slot"] == 0)
    if m.any():
        r, c = np.argwhere(m)[0]
        setl[names[k]] = next((i for i, comp in enumerate(nc) if (c, r) in set(comp)), None)
groups = {}
for n, i in setl.items(): groups.setdefault(i, []).append(n.replace("ironic_region_", ""))
print("networks (roads+towns) holding Korean settlements:")
for i, ns in groups.items(): print(f"  net {i} size {len(nc[i]) if i is not None else 0}: {ns}")
