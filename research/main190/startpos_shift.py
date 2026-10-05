#!/usr/bin/env python3
"""Shift the 190E start_pos_characters positions (startx/starty = 190E hex col/row) onto the warped map.

User rule: add the west padding to x (+128 hexes); y is unchanged (the padding was added only to the north).
The Central Plains band stretch moves things too, so the full warp forward mapping is used, which is exactly x+128 /
y unchanged west of and south of the band. Each result snaps to the nearest passable land hex (map.hex) if the
mapped hex is sea / impassable. Rows with startx, starty <= 1 are placeholders (off map, or placed via their
settlement) and are left alone.
Input: source_pos/db/start_pos_characters_tables/*.tsv (extracted from !!190_expanded_region_test.pack)
Output: db_out/db/start_pos_characters_tables/*.tsv (same names, so the new pack overrides the test pack's)
"""
import csv, sys
from collections import deque
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
import crop_scale_map_hex as C
from rebuild_hex import unpack
from hexgrid import centre, nearest_hex, neighbour
from warp import Warp, WarpMapping, current

SRC = HERE / "source_pos" / "db" / "start_pos_characters_tables"
MAP = WarpMapping(current())
FOLLOW = 4                               # hexes: characters this close to a moved town's old site move with it


def main():
    src = (HERE / "hex" / "map.hex").read_bytes(); P, w, h = C.locate_dims(src)
    f = unpack(np.frombuffer(src, np.uint8, 16 * w * h, P + 8).reshape(h, w, 16))
    ok = (f["terr"] == 0) & (f["imp"] == 0)
    # round 6/7: towns moved by regions_carve6 (Hexi to the real corridor, Central Plains onto their real seats) -
    # a character standing within FOLLOW hexes of a moved town's old site moves with the town
    import json, warp
    if warp.is_scale():
        # base 190E x1.5 (CAIME map-upscaler): a town is pinned up to ~3 hexes from its plainly scaled position
        # (port / cliff anchor) - characters near the scaled position follow the town to where CAIME put it
        b0 = Path(r"Z:/Claude/190Expanded/campaign_maps/map.hex").read_bytes(); P0, w0, h0 = C.locate_dims(b0)
        f0 = unpack(np.frombuffer(b0, np.uint8, 16 * w0 * h0, P0 + 8).reshape(h0, w0, 16))
        def sites(g, ww, hh, fwd):
            acc = {}
            for r_, c_ in zip(*np.nonzero(g["slot"] == 0)):
                x, z = centre(int(c_), int(r_))
                if fwd: x, z = MAP.fwd_world(x, z)
                acc.setdefault(int(g["region"][r_, c_]), []).append((x, z))
            out_ = {}
            for k, v in acc.items():
                a = np.array(v, float).mean(0); cc, rr_ = nearest_hex(a[:1], a[1:], ww, hh); out_[k] = (int(cc[0]), int(rr_[0]))
            return out_
        old_s, new_s = sites(f0, w, h, True), sites(f, w, h, False)
        follow = [(old_s[k], new_s[k]) for k in old_s if k in new_s and old_s[k] != new_s[k]]
        OUT = HERE / "db_scale" / "db" / "start_pos_characters_tables"
        print(f"scale mode: {len(follow)} towns pinned off their scaled position; output {OUT}")
    else:
        nj = json.load(open(HERE / "regions_new.json", encoding="utf-8"))
        follow = [(tuple(m["old_site"]), tuple(m["site"])) for grp in ("moved", "moved_r7") for m in nj.get(grp, {}).values()
                  if m.get("old_site") and m.get("site")]
        OUT = HERE / "db_out" / "db" / "start_pos_characters_tables"
    OUT.mkdir(parents=True, exist_ok=True)
    for path in sorted(SRC.glob("*.tsv")):
        lines = open(path, encoding="utf-8", newline="").read().split("\n")
        hdr = lines[0].split("\t"); ix, iy = hdr.index("startx"), hdr.index("starty")
        out, n, snapped, dmax, plain = lines[:2], 0, 0, 0, 0
        for line in lines[2:]:
            if not line.strip(): out.append(line); continue
            r = line.split("\t"); x, y = float(r[ix]), float(r[iy])
            if x > 1 or y > 1:
                wx, wz = centre(int(round(x)), int(round(y)))
                nx, nz = MAP.fwd_world(wx, wz)
                c, rr = nearest_hex(np.array([nx]), np.array([nz]), w, h); c, rr = int(c[0]), int(rr[0])
                for (oc, orr), (nc_, nr_) in follow:                      # followed its moved town
                    if abs(c - oc) + abs(rr - orr) <= FOLLOW: c, rr = min(w - 1, max(0, c + nc_ - oc)), min(h - 1, max(0, rr + nr_ - orr)); break
                if not ok[rr, c]:                                         # nearest passable land (BFS)
                    seen = {(c, rr)}; q = deque([(c, rr)])
                    while q:
                        a = q.popleft()
                        if ok[a[1], a[0]]: c, rr = a; break
                        for k in range(6):
                            b = neighbour(a[0], a[1], k)
                            if 0 <= b[0] < w and 0 <= b[1] < h and b not in seen: seen.add(b); q.append(b)
                    snapped += 1
                if c == int(round(x)) + 128 and rr == int(round(y)): plain += 1
                dmax = max(dmax, abs(c - x - 128) + abs(rr - y))
                r[ix], r[iy] = f"{c:.4f}", f"{rr:.4f}"; n += 1
            out.append("\t".join(r))
        open(OUT / path.name, "w", encoding="utf-8", newline="").write("\n".join(out))
        print(f"{path.name:32s} moved {n:4d}  (= x+128, y same: {plain}; changed further by the band stretch: {n - plain}; "
              f"snapped to passable land: {snapped}; max extra shift {dmax:.0f} hexes)")


if __name__ == "__main__":
    main()
