#!/usr/bin/env python3
"""Compare the CAIME-upscaled map.hex with stock 190E: dims, settlements (slot 0 hexes per region), region hex
counts, road/river/sea totals, and how far each settlement sits from the plain f-scaled position of its original."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent.parent)); sys.path.insert(0, str(Path(__file__).parent.parent / "guandu"))
import hexmap
from rebuild_hex import unpack

SRC = r"Z:/Claude/190Expanded/campaign_maps/map.hex"
OUT = sys.argv[1] if len(sys.argv) > 1 else r"Z:/Claude/TerryClone/research/main190/hex_upscale/map.hex"


def grid(p):
    d = hexmap.load(p)
    g = np.frombuffer(d["rec"] if isinstance(d["rec"], (bytes, bytearray)) else Path(p).read_bytes(), np.uint8, 16 * d["w"] * d["h"],
                      0 if isinstance(d["rec"], (bytes, bytearray)) else d["body_off"]).reshape(d["h"], d["w"], 16)
    return d, unpack(g)


def centre(q, r): return q, r + 0.5 * (q & 1)


(da, a), (db, b) = grid(SRC), grid(OUT)
f = db["w"] / da["w"]
print(f"src {da['w']}x{da['h']}  out {db['w']}x{db['h']}  f={f:.4f}")
names = da["lists"]["land_regions"] + da["lists"]["sea_regions"]
names_b = db["lists"]["land_regions"] + db["lists"]["sea_regions"]
print("region lists identical:", names == names_b)
for k in ("terr", "road", "river", "sprawl"):
    na, nb = int((a[k] > 0).sum()), int((b[k] > 0).sum())
    print(f"{k:7s} hexes {na:8d} -> {nb:8d}  (x{nb / max(na, 1):.2f}; area x{f * f:.2f})")
ra = np.bincount(a["region"][a["region"] >= 0], minlength=len(names)); rb = np.bincount(b["region"][b["region"] >= 0], minlength=len(names))
lost = [names[i] for i in range(len(names)) if ra[i] > 0 and rb[i] == 0]
print(f"regions present {int((ra > 0).sum())} -> {int((rb > 0).sum())}; lost {lost[:10]}")
ratio = rb[ra > 50] / ra[ra > 50]
print(f"region area ratio (regions >50 hexes): min {ratio.min():.2f} p5 {np.percentile(ratio, 5):.2f} median {np.median(ratio):.2f} max {ratio.max():.2f}")
# settlements: slot 0 = the main settlement of each region
sa = {int(a["region"][r, q]): (q, r) for r, q in zip(*np.nonzero(a["slot"] == 0))}
sb = {int(b["region"][r, q]): (q, r) for r, q in zip(*np.nonzero(b["slot"] == 0))}
print(f"slot-0 settlements {len(sa)} -> {len(sb)}; missing {[names[i] for i in sa if i not in sb][:10]}")
d = []
for i, (q, r) in sa.items():
    if i not in sb: continue
    x, y = centre(q, r); qb, rb_ = sb[i]; xb, yb = centre(qb, rb_)
    d.append((np.hypot(xb - x * f, yb - y * f), names[i]))
d.sort(reverse=True)
print("settlement offset from f-scaled position (hexes): max %.2f, >1.5: %d" % (d[0][0], sum(1 for v, _ in d if v > 1.5)), d[:8])
slots_a = int((a["slot"] >= 0).sum()); slots_b = int((b["slot"] >= 0).sum())
print(f"all town-slot hexes {slots_a} -> {slots_b}")
