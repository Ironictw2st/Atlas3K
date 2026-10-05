#!/usr/bin/env python3
"""After jeju_scale.py: city-bar check of the two Tamna towns (town_pinch_fix) and the road between them."""
import heapq, struct, subprocess, sys, zlib
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
TOWNS = ["ironic_region_tamna_capital", "ironic_region_baek_resource_1"]


def road():
    import town_fix as T
    from hexgrid import neighbour_arrays, direction_between
    b, P, w, h, g, f, names = T.load(str(HERE / "hex" / "map.hex")); NA = neighbour_arrays(h, w)
    town = (f["slot"] >= 0) | (f["sprawl"] > 0)
    A = town & (f["region"] == names.index(TOWNS[0])); B = town & (f["region"] == names.index(TOWNS[1]))
    src = [(int(r), int(c)) for r, c in zip(*np.nonzero(A))]
    dist = {p: 0.0 for p in src}; prev = {p: None for p in src}; q = [(0.0, p) for p in src]; heapq.heapify(q); hit = None
    while q:
        d, a = heapq.heappop(q)
        if d > dist.get(a, 1e18): continue
        if B[a]: hit = a; break
        for k, (nr, nc, v) in enumerate(NA):
            if not v[a]: continue
            bq = (int(nr[a]), int(nc[a]))
            if f["terr"][bq] != 0 or f["imp"][bq]: continue
            nd = d + 1
            if nd < dist.get(bq, 1e18): dist[bq] = nd; prev[bq] = a; heapq.heappush(q, (nd, bq))
    if hit is None: print("jeju road: no route"); return
    path = [hit]
    while prev[path[-1]] is not None: path.append(prev[path[-1]])
    rd = f["road"].copy()
    for a, bq in zip(path, path[1:]):
        d = direction_between((a[1], a[0]), (bq[1], bq[0]))
        if d >= 0: rd[a] |= 1 << d; rd[bq] |= 1 << ((d + 3) % 6)
    G = g.copy(); G[..., 3] = ((g[..., 3] & 0x81) | ((rd & 63) << 1)).astype(np.uint8)
    out = bytearray(b); out[P + 8:P + 8 + 16 * w * h] = G.tobytes()
    out[-4:] = struct.pack("<I", zlib.crc32(bytes(out[:-4])) & 0xFFFFFFFF); (HERE / "hex" / "map.hex").write_bytes(bytes(out))
    print("jeju road:", len(path), "hexes")


if __name__ == "__main__":
    subprocess.run([sys.executable, str(HERE / "town_pinch_fix.py")] + TOWNS, check=True)
    road()
