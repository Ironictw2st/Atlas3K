#!/usr/bin/env python3
"""Road network connectivity (road edge bits; a road hex next to a town enters it; towns join their hexes).
usage: road_net.py <map.hex> -> components and the towns off the largest one."""
import sys, collections
from pathlib import Path
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
import numpy as np, town_fix as T
from hexgrid import neighbour_arrays


def components(path):
    _, _, w, h, _, f, names = T.load(path)
    NA = neighbour_arrays(h, w); road = f["road"]; town = (f["slot"] >= 0) | (f["sprawl"] > 0)
    par = np.arange(h * w)
    def find(x):
        while par[x] != x: par[x] = par[par[x]]; x = par[x]
        return x
    idx = np.arange(h * w).reshape(h, w)
    for d, (nr, nc, v) in enumerate(NA):
        for m in (v & (((road >> d) & 1) > 0), v & town & town[nr, nc], v & town & (road[nr, nc] > 0)):
            for a, b in zip(idx[m], idx[nr[m], nc[m]]):
                ra, rb = find(a), find(b)
                if ra != rb: par[ra] = rb
    roots = collections.Counter(find(x) for x in idx[(road > 0) | town])
    main = roots.most_common(1)[0][0]
    off = collections.defaultdict(set)
    for r, c in zip(*np.nonzero(town & (f["slot"] == 0))):
        if find(idx[r, c]) != main: off[find(idx[r, c])].add(names[f["region"][r, c]])
    return f, names, find, idx, roots, off


if __name__ == "__main__":
    f, names, find, idx, roots, off = components(sys.argv[1])
    print("components", len(roots), "largest", [n for _, n in roots.most_common(6)])
    for k, v in sorted(off.items(), key=lambda x: -len(x[1])): print(len(v), sorted(v)[:10])
