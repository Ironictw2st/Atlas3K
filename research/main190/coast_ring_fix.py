#!/usr/bin/env python3
"""Coast ring rule on map.hex (2026-10-01, tile holes): vanilla's coast is exactly one ring - plain land never touches
sea (vanilla's tile map: 40 such hexes, ours 784, 417 of them in map.hex - the x15 lakes were carved as 3k_main_sea_lake
water with no shore). BOB has no tile for land meeting sea head-on, so those spots became see-through holes.
Plain land hexes touching sea become beach (terr 2, beach ground, passable); hexes within 3 of a town footprint,
roads, rivers and bridges are left alone (a beach next to a town is a city-bar hazard).
In place on hex/map.hex (backup hex/map_pre_coastring_<ts>.hex)."""
import shutil, struct, sys, time, zlib
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
import town_fix as T
from hexgrid import neighbour_arrays
HEX = HERE / "hex" / "map.hex"
BEACH_GROUND = 2                                   # the most common ground type on 190E beaches
shutil.copy2(HEX, HERE / "hex" / f"map_pre_coastring_{time.strftime('%Y%m%d_%H%M%S')}.hex")
b, P, w, h, g, f, names = T.load(HEX); G = g.copy(); NA = neighbour_arrays(h, w)
t = f["terr"]
nsea = np.zeros((h, w), bool)
for nr, nc, v in NA: nsea |= v & (t[nr, nc] == 1)
town = (f["slot"] >= 0) | (f["sprawl"] > 0)
for _ in range(3):
    g2 = town.copy()
    for nr, nc, v in NA: g2 |= v & town[nr, nc]
    town = g2
prot = town | (f["road"] > 0) | (f["river"] > 0) | (f["bridge"] > 0)
fix = (t == 0) & nsea & ~prot
print(f"plain land touching sea: {int(((t == 0) & nsea).sum())}; -> beach {int(fix.sum())}; protected {int(((t == 0) & nsea & prot).sum())}")
gt = BEACH_GROUND + 1
G[..., 0] = np.where(fix, (G[..., 0] & 0xFC) | 2, G[..., 0])
G[..., 5] = np.where(fix, (G[..., 5] & 0x0F) | ((gt & 15) << 4), G[..., 5])
G[..., 6] = np.where(fix, (G[..., 6] & 0xF8) | ((gt >> 4) & 7), G[..., 6])
G[..., 2] = np.where(fix, G[..., 2] & 0xF7, G[..., 2])          # passable beach
out = bytearray(b); out[P + 8:P + 8 + 16 * w * h] = G.tobytes()
out[-4:] = struct.pack("<I", zlib.crc32(bytes(out[:-4])) & 0xFFFFFFFF); HEX.write_bytes(bytes(out))
_, _, _, _, _, f2, _ = T.load(HEX)
ns2 = np.zeros((h, w), bool)
for nr, nc, v in NA: ns2 |= v & (f2["terr"][nr, nc] == 1)
nl = np.zeros((h, w), bool)
for nr, nc, v in NA: nl |= v & (f2["terr"][nr, nc] == 0)
print(f"after: plain land touching sea {int(((f2['terr'] == 0) & ns2).sum())}, beach not touching land {int(((f2['terr'] == 2) & ~nl).sum())}")
