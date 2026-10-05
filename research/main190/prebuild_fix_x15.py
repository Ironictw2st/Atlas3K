#!/usr/bin/env python3
"""Pre-build (re-run safe: slivers / roads / coast only act where still needed) map fixes from the 2026-10-02 audit (user: "go"), in place on hex/map.hex (backup map_pre_prebuild_<ts>.hex):
 a) slivers: land-region pieces under 40 hexes with no town (upscale slivers, a stray painted hex) join the neighbouring
    land region they share the longest border with;
 b) roads: town groups cut off from the road network that stock 190E had connected (Jiangling, Yong'an, Jiangdu, Dongye,
    Michuhol, Dongokjeo, San Pass, southern Korea) get the shortest road (BFS over passable land, no river-edge
    crossing except where a bridge exists) to the nearest hex of a bigger network piece;
 c) coast: plain land touching sea becomes beach where that adds no pinch / sprawl break to a town within 4 hexes."""
import collections, json, shutil, struct, sys, time, zlib
from collections import deque
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
import town_fix as T, hexmap
from hexgrid import neighbour_arrays, direction_between, neighbour
import road_net
HEX = HERE / "hex" / "map.hex"; STOCK = r"Z:/Claude/190Expanded/campaign_maps/map.hex"
shutil.copy2(HEX, HERE / "hex" / f"map_pre_prebuild_{time.strftime('%Y%m%d_%H%M%S')}.hex")
b, P, w, h, g, f, names = T.load(str(HEX)); G = g.copy(); NA = neighbour_arrays(h, w)
LAND = hexmap.load(str(HEX))["lists"]["land_regions"]; NL = len(LAND)
reg = f["region"].copy(); terr = f["terr"]; road = f["road"].copy(); imp = f["imp"]
town = (f["slot"] >= 0) | (f["sprawl"] > 0)
log = {}

# ---- a) slivers
moved = []
for i, k in enumerate(LAND):
    if "non_playable" in k: continue
    m = (reg == i) & (terr != 1)
    seen = np.zeros((h, w), bool); pieces = []
    for r0, c0 in zip(*np.nonzero(m)):
        if seen[r0, c0]: continue
        st = [(r0, c0)]; seen[r0, c0] = True; cells = []
        while st:
            r, c = st.pop(); cells.append((r, c))
            for nr, nc, v in NA:
                if v[r, c] and m[nr[r, c], nc[r, c]] and not seen[nr[r, c], nc[r, c]]:
                    seen[nr[r, c], nc[r, c]] = True; st.append((nr[r, c], nc[r, c]))
        pieces.append(cells)
    if len(pieces) < 2: continue
    pieces.sort(key=len, reverse=True)
    for cells in pieces[1:]:
        if len(cells) >= 40 or any(town[r, c] for r, c in cells): continue
        cs = set(cells); border = collections.Counter()
        for r, c in cells:
            for nr, nc, v in NA:
                if v[r, c]:
                    a, bb = nr[r, c], nc[r, c]
                    if (a, bb) not in cs and terr[a, bb] != 1 and reg[a, bb] < NL and reg[a, bb] != i: border[int(reg[a, bb])] += 1
        if not border: continue
        tgt = border.most_common(1)[0][0]
        for r, c in cells: reg[r, c] = tgt
        moved.append(f"{len(cells)} hexes of {k} -> {LAND[tgt]}")
log["slivers"] = moved

# ---- b) roads
_, _, _, _, _, f0, n0 = T.load(STOCK)
_, _, find0, idx0, roots0, off0 = road_net.components(STOCK)
stock_off = {k for v in off0.values() for k in v}
ISLANDS = {k for v in off0.values() if len(v) == 1 for k in v} - {'ironic_region_xiping_capital', 'ironic_region_xiping_resource_2'}
_, _, find, idx, roots, off = road_net.components(str(HEX))
big = {r for r, n in roots.items() if n >= 3000}                 # the big network pieces (main, north, west ...)
bighex = np.zeros((h, w), bool)
for r, c in zip(*np.nonzero((road > 0) | town)):
    if find(idx[r, c]) in big: bighex[r, c] = True
roads_added = []
# winding roads (user: no straight lines): Dijkstra on 1 + 3 * smooth noise + 4 * slope, carve_x15's cost style
import heapq
from class_fill import smooth_noise
from regions_carve import hex_blend_and_height
noise = 0.5 * smooth_noise((h, w), 20, 61) + 0.3 * smooth_noise((h, w), 6, 62) + 0.2 * smooth_noise((h, w), 2, 63)
noise = (noise - noise.min()) / (np.ptp(noise) + 1e-9)
_, hh = hex_blend_and_height(w, h); slope = np.zeros((h, w), np.float32)
for nr, nc, v in NA: slope = np.maximum(slope, np.where(v, np.abs(hh[nr, nc] - hh), 0))
slope = np.clip(slope / max(1.0, float(np.percentile(slope[terr != 1], 95))), 0, 1)
cost = 1.0 + 3.0 * noise + 4.0 * slope
todo = sorted(((c, t) for c, t in off.items() if c not in big and len(t) < 40 and not t <= ISLANDS), key=lambda x: -len(x[1]))
for comp, towns in todo:
    src = [(int(r), int(c)) for r, c in zip(*np.nonzero((road > 0) | town)) if find(idx[r, c]) == comp]
    if any(bighex[p] for p in src): roads_added.append(f"{sorted(towns)[:3]}: already joined"); continue
    dist = {p: 0.0 for p in src}; prev = {p: None for p in src}; pq = [(0.0, p) for p in src]; heapq.heapify(pq); hit = None
    while pq:
        dd, a = heapq.heappop(pq)
        if dd > dist.get(a, 1e18): continue
        if bighex[a] and prev[a] is not None: hit = a; break
        for d, (nr, nc, v) in enumerate(NA):
            if not v[a]: continue
            bq = (int(nr[a]), int(nc[a]))
            if abs(bq[0] - src[0][0]) > 200 or abs(bq[1] - src[0][1]) > 200: continue
            if terr[bq] != 0 or (imp[bq] and not bighex[bq]): continue
            if (f["river"][a] >> d) & 1 and not (f["bridge"][a] or f["bridge"][bq]): continue
            nd = dd + float(cost[bq])
            if nd < dist.get(bq, 1e18): dist[bq] = nd; prev[bq] = a; heapq.heappush(pq, (nd, bq))
    if hit is None: roads_added.append(f"{sorted(towns)}: no land route found"); continue
    path = [hit]
    while prev[path[-1]] is not None: path.append(prev[path[-1]])
    for a, bq in zip(path, path[1:]):
        dd_ = direction_between((a[1], a[0]), (bq[1], bq[0]))
        if dd_ < 0: continue
        road[a] |= 1 << dd_; road[bq] |= 1 << ((dd_ + 3) % 6)
    for p in src + path: bighex[p] = True                 # joined: later groups may link to it
    roads_added.append(f"{sorted(towns)[:4]}{'...' if len(towns) > 4 else ''}: {len(path)}-hex road")
log["roads"] = roads_added

# write a+b, then c is checked on the written map
G[..., 0] = ((((reg + 1) & 0x1F) << 3) | (G[..., 0] & 7)).astype(np.uint8)
G[..., 1] = (((reg + 1) >> 5) & 0xFF).astype(np.uint8)
G[..., 3] = ((G[..., 3] & 0x81) | ((road & 63) << 1)).astype(np.uint8)
def save(G):
    out = bytearray(b); out[P + 8:P + 8 + 16 * w * h] = G.tobytes()
    out[-4:] = struct.pack("<I", zlib.crc32(bytes(out[:-4])) & 0xFFFFFFFF); HEX.write_bytes(bytes(out))
save(G)

# ---- c) coast ring where safe
src = open(HERE / "town_pinch_fix.py").read(); src = src[:src.index("args = [a for a")].replace("if not DRY: shutil.copy2", "if False: shutil.copy2")
sys.argv = ["x", "--dry"]; tp = {"__file__": str(HERE / "town_pinch_fix.py"), "__name__": "tpf"}; exec(src, tp)
t = tp["terr"]; nsea = np.zeros((h, w), bool)
for nr, nc, v in NA: nsea |= v & (t[nr, nc] == 1)
cand = [(int(r), int(c)) for r, c in zip(*np.nonzero((t == 0) & nsea & (road == 0) & (f["river"] == 0)))]
near_towns = {int(k) for r, c in cand for k in np.unique(tp["reg"][max(0, r - 6):r + 7, max(0, c - 6):c + 7][tp["slot"][max(0, r - 6):r + 7, max(0, c - 6):c + 7] == 0])}
before = {k: (len(tp["town_pinches"](tp["footprint"](k))), tp["hazard_ok"](tp["footprint"](k))) for k in near_towns}
for r, c in cand: tp["terr"][r, c] = 2
after = {k: (len(tp["town_pinches"](tp["footprint"](k))), tp["hazard_ok"](tp["footprint"](k))) for k in near_towns}
worse = [names[k] for k in near_towns if after[k][0] > before[k][0] or (before[k][1] and not after[k][1])]
if worse:
    log["coast"] = f"skipped {len(cand)} hexes: would hurt {worse}"
else:
    gt = 3
    for r, c in cand:
        G[r, c, 0] = (G[r, c, 0] & 0xFC) | 2; G[r, c, 5] = (G[r, c, 5] & 0x0F) | (gt << 4); G[r, c, 6] = G[r, c, 6] & 0xF8; G[r, c, 2] &= 0xF7
    save(G); log["coast"] = f"{len(cand)} land hexes touching sea -> beach"
json.dump(log, open(HERE / "prebuild_fix_x15.json", "w"), indent=1)
for k, v in log.items():
    print(f"== {k}"); [print("   ", x) for x in (v if isinstance(v, list) else [v])]
