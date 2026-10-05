#!/usr/bin/env python3
"""Close one-hex gaps (town_fix step D) around the given towns on hex/map.hex: a passable land ring hex (no road /
bridge) next to a river / impassable / beach hex two out becomes impassable. Wan (2026-10-01) had no site clear of its
impassable mass. Usage: town_gap_x15.py <region key> ..."""
import shutil, struct, sys, time, zlib
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
import town_fix as T
HEX = HERE / "hex" / "map.hex"
shutil.copy2(HEX, HERE / "hex" / f"map_pre_gap_{time.strftime('%Y%m%d_%H%M%S')}.hex")
b, P, w, h, g, f, names = T.load(HEX); G = g.copy()
for name in sys.argv[1:]:
    F = T.footprint(f, names.index(name)); R1 = T.ring(F, w, h); R2 = T.ring(F | R1, w, h)
    hz = lambda c, r: bool(f["imp"][r, c] or f["river"][r, c] or f["terr"][r, c] in (2, 3))
    near = {p for p in R2 if hz(*p)}
    add = [(c, r) for c, r in R1 if not hz(c, r) and f["terr"][r, c] == 0 and not f["road"][r, c] and not f["bridge"][r, c]
           and any((nc, nr) in near for _, nc, nr in T.nbrs(c, r, w, h))]
    for c, r in add: G[r, c, 2] |= 8
    print(name, "impassable added", add)
out = bytearray(b); out[P + 8:P + 8 + 16 * w * h] = G.tobytes()
out[-4:] = struct.pack("<I", zlib.crc32(bytes(out[:-4])) & 0xFFFFFFFF); HEX.write_bytes(bytes(out))
