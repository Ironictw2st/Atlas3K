#!/usr/bin/env python3
"""Settlement spacing: land walking distance (hex steps) from every settlement to its nearest neighbours.

"Regions should not be one army walk away from each other" (user, 2026-09-29). Armies have 2,450 action points
(most land_units; +10% general bonus) and open ground costs 120 per hex step (campaign_ground_types: plains,
grassland; hills 240, forest/mountain/wetland 360; roads cheaper), so one turn is about 20-22 hexes on open ground.
Vanilla's own spacing is the reference for "normal".

Settlement hex = the slot-footprint hex (slot >= 0) closest to the centroid of the region's footprint.
Walkable = land (terr != 1) or a bridge, and not impassable. Distance = BFS hex steps (unweighted: terrain and
road costs are not modelled, so compare against vanilla rather than reading it as turns).

usage: spacing.py <map.hex> [<map.hex> ...]    (prints the closest pairs; first file is the reference if several)
"""
import sys, os, heapq, collections
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
for p in (HERE, os.path.join(HERE, "..", "guandu"), os.path.join(HERE, "..")):
    sys.path.insert(0, p)
from regions_plan import load
from hexgrid import neighbour_arrays

MAXD = 60


def settlements(f, names):
    out = {}
    slot = f["slot"] >= 0
    for rid in np.unique(f["region"][slot]):
        if "sea" in names[rid] or "lake" in names[rid]: continue           # port slots of sea regions
        rr, cc = np.nonzero(slot & (f["region"] == rid))
        k = np.argmin((rr - rr.mean()) ** 2 + (cc - cc.mean()) ** 2)
        out[names[rid]] = (rr[k], cc[k])
    return out


def pairs(path):
    f, names, w, h = load(path)
    walk = ((f["terr"] != 1) | (f["bridge"] > 0)) & (f["imp"] == 0)
    S = settlements(f, names)
    at = {v: k for k, v in S.items()}
    nb = neighbour_arrays(h, w)
    res = {}
    for name, (r0, c0) in S.items():
        dist = {(r0, c0): 0}; q = collections.deque([(r0, c0)]); found = []
        while q:
            r, c = q.popleft(); d = dist[(r, c)]
            if d >= MAXD: continue
            for nr, nc, valid in nb:
                if not valid[r, c]: continue
                a, b = nr[r, c], nc[r, c]
                if (a, b) in dist or not walk[a, b]: continue
                dist[(a, b)] = d + 1; q.append((a, b))
                if (a, b) in at: found.append((d + 1, at[(a, b)]))
        res[name] = sorted(found)
    return res, S


def main():
    out = []
    for p in sys.argv[1:]:
        res, S = pairs(p)
        nn = {k: v[0][0] for k, v in res.items() if v}
        vals = np.array(sorted(nn.values()))
        print(f"== {p}\n   {len(S)} settlements; nearest-neighbour walk (hex steps): min {vals.min()}  p5 {np.percentile(vals, 5):.0f}  "
              f"p25 {np.percentile(vals, 25):.0f}  median {np.median(vals):.0f}; isolated (none within {MAXD}): {len(S) - len(nn)}")
        out.append((p, res, vals))
    ref = out[0][2]
    thr = int(np.percentile(ref, 5))
    for p, res, vals in out[1:]:
        close = sorted({tuple(sorted((a, b))): d for a, v in res.items() for d, b in v if d < thr}.items(), key=lambda t: t[1])
        print(f"\n{p}: pairs closer than the reference's 5th percentile ({thr} hex steps): {len(close)}")
        for (a, b), d in close:
            print(f"   {d:3d}  {a}  <->  {b}")


if __name__ == "__main__":
    main()
