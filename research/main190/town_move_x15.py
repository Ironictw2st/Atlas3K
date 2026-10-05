#!/usr/bin/env python3
"""Move towns whose city bar does not show (user, 2026-10-01: Guandu, Wan, Meiji, Guyang, Nan'an, Dianjiang, Zhouling)
clear of river / coast / impassable: the footprint (slots + sprawl) is translated in cube coordinates (shape kept) to
the nearest spot in its own region with no river edge, sea, beach / cliff, impassable or bridge within CLEAR-1 hexes.
Roads that ended at the old footprint are re-routed (BFS over passable land, no river-edge crossings) to the new one.
In place on hex/map.hex (backup hex/map_pre_move_<ts>.hex). Usage: town_move_x15.py <region key> ..."""
import json, shutil, struct, sys, time, zlib
from collections import deque
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
import town_fix as T
from hexgrid import to_cube, direction_between
CLEAR, MAXMOVE = 3, 12
HEX = HERE / "hex" / "map.hex"
shutil.copy2(HEX, HERE / "hex" / f"map_pre_move_{time.strftime('%Y%m%d_%H%M%S')}.hex")
b, P, w, h, g, f, names = T.load(HEX)
G = g.copy(); imp = f["imp"].copy(); slot = f["slot"].copy(); sprawl = f["sprawl"].copy(); road = f["road"].copy()
redge = f["river"] > 0
for r, c in zip(*np.nonzero(f["river"] > 0)):
    for d, nc, nr in T.nbrs(int(c), int(r), w, h):
        if (f["river"][r, c] >> d) & 1: redge[nr, nc] = True
haz0 = redge | (f["terr"] != 0) | (f["bridge"] > 0)
log = {}
for name in sys.argv[1:]:
    k = names.index(name); F = T.footprint(f, k)
    town = (slot >= 0) | (sprawl > 0)
    haz = haz0 | (imp > 0)
    cs = [p[0] for p in F]; rs = [p[1] for p in F]
    c0, c1, r0, r1 = max(0, min(cs) - 30), min(w, max(cs) + 31), max(0, min(rs) - 30), min(h, max(rs) + 31)
    dist = np.full((h, w), 99, int); q = deque()
    for r in range(r0, r1):
        for c in range(c0, c1):
            if haz[r, c]: dist[r, c] = 0; q.append((c, r))
    while q:
        c, r = q.popleft()
        for _, nc, nr in T.nbrs(c, r, w, h):
            if c0 <= nc < c1 and r0 <= nr < r1 and dist[nr, nc] > dist[r, c] + 1: dist[nr, nc] = dist[r, c] + 1; q.append((nc, nr))
    best = None
    for dq in range(-MAXMOVE, MAXMOVE + 1):
        for dr in range(-MAXMOVE, MAXMOVE + 1):
            n = max(abs(dq), abs(dr), abs(dq + dr))
            if n == 0 or n > MAXMOVE: continue
            F2 = {T.cube_shift(p, (dq, dr)) for p in F}
            if not all(0 <= c < w and 0 <= r < h and f["region"][r, c] == k and not haz[r, c] and ((c, r) in F or not town[r, c])
                       for c, r in F2): continue
            # keep other towns' footprints out of the new ring too
            if any(town[nr, nc] and (nc, nr) not in F for c, r in F2 for _, nc, nr in T.nbrs(c, r, w, h)): continue
            clear = min(dist[r, c] for c, r in F2)
            score = (clear < CLEAR, n, -clear)
            if best is None or score < best[0]: best = (score, (dq, dr), F2, clear)
    if best is None or best[3] < CLEAR:
        log[name] = {"skipped": True, "best_clear": None if best is None else int(best[3])}; print(name, "NO SITE", log[name]); continue
    _, Tc, F2, clear = best
    ends = set()
    for c, r in F:
        for d, nc, nr in T.nbrs(c, r, w, h):
            if (nc, nr) not in F and road[nr, nc] and (road[nr, nc] >> ((d + 3) % 6)) & 1:
                ends.add((nc, nr)); road[nr, nc] &= ~(1 << ((d + 3) % 6))
    old = {p: (int(slot[p[1], p[0]]), int(sprawl[p[1], p[0]])) for p in F}
    for c, r in F: slot[r, c] = -1; sprawl[r, c] = 0; road[r, c] = 0
    for p, (s, sp) in old.items():
        c, r = T.cube_shift(p, Tc); slot[r, c] = s; sprawl[r, c] = sp; imp[r, c] = 0
    roads = []
    for e in sorted(ends):                                    # BFS from the cut road end to the new footprint
        prev = {e: None}; q = deque([e]); hit = None
        while q and hit is None:
            a = q.popleft()
            for d, nc, nr in T.nbrs(*a, w, h):
                bb = (nc, nr)
                if bb in prev or abs(nc - e[0]) > 40 or abs(nr - e[1]) > 40: continue
                if (f["river"][a[1], a[0]] >> d) & 1: continue                  # no river crossing
                if f["terr"][nr, nc] != 0 or imp[nr, nc] and bb not in F2: continue
                prev[bb] = a
                if bb in F2: hit = bb; break
                q.append(bb)
        if hit is None: roads.append([list(e), None]); continue
        path = [hit]
        while prev[path[-1]] is not None: path.append(prev[path[-1]])
        path.reverse()
        for a, bb in zip(path, path[1:]):
            d = direction_between(a, bb)
            road[a[1], a[0]] |= 1 << d; road[bb[1], bb[0]] |= 1 << ((d + 3) % 6)
        roads.append([list(e), list(hit), len(path)])
    log[name] = {"shift_cube": Tc, "clearance": int(clear), "roads": roads}
    print(f"{name}: moved {Tc} clearance {clear} roads {roads}")
G[..., 2] = ((((slot + 1) & 15) << 4) | ((imp & 1) << 3) | (g[..., 2] & 7)).astype(np.uint8)
G[..., 3] = ((g[..., 3] & 0x80) | ((road & 63) << 1) | (sprawl & 1)).astype(np.uint8)
out = bytearray(b); out[P + 8:P + 8 + 16 * w * h] = G.tobytes()
out[-4:] = struct.pack("<I", zlib.crc32(bytes(out[:-4])) & 0xFFFFFFFF)
HEX.write_bytes(bytes(out))
json.dump(log, open(HERE / "town_move_x15.json", "w"), indent=1)
