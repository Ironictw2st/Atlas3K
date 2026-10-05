#!/usr/bin/env python3
"""After CAIME's ResizeMapHex padding (edge-clamped copies): pad hexes become plain non-playable, impassable land -
region 3k_main_reg_non_playable, no slot / sprawl / road / bridge / river / trade / AoI / restriction (ground and
climate keep the clamped edge values). North-pad hexes that were clamped from sea stay sea (their sea region), so the
coast does not turn into a land wall. Road / river bits of the old edge hexes that point into the pad are dropped.
Usage: python pad_clean.py <padded map.hex> <west cols> <north rows> <out map.hex>   (row 0 = south: north rows on top)"""
import struct, sys, zlib
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
import crop_scale_map_hex as C, hexmap
from hexgrid import neighbour

src, west, north, dst = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
b = bytearray(Path(src).read_bytes()); P, w, h = C.locate_dims(bytes(b))
g = np.frombuffer(b, np.uint8, 16 * w * h, P + 8).reshape(h, w, 16).copy()
lists = hexmap.load(src)["lists"]; names = lists["land_regions"] + lists["sea_regions"]
NP = names.index("3k_main_reg_non_playable") + 1                  # stored +1
pad = np.zeros((h, w), bool); pad[:, :west] = True
if north: pad[h - north:, :] = True
sea = (g[..., 0] & 3) == 1
land_pad = pad & ~(sea & (np.arange(h)[:, None] >= h - north) & (north > 0))
g[land_pad, 0] = (NP & 0x1F) << 3                                  # region low bits, terr = 0 (land)
g[land_pad, 1] = (NP >> 5) & 0xFF
g[land_pad, 2] = (1 << 3) | (g[land_pad, 2] & 7)                   # impassable, slot -1
g[pad, 2] = np.where(land_pad[pad], g[pad, 2], g[pad, 2] & 0x0F)    # sea pad: no slot (keep imp/low bits)
g[pad, 3] = 0; g[pad, 4] = 0; g[pad, 8] = 0; g[pad, 15] = 0
g[pad, 5] = g[pad, 5] & 0xF0                                       # keep ground low nibble, trade high = 0
# road (byte 3 bits 1-6) / river (byte 4 bits 0-5) bits of non-pad hexes pointing into the pad
rr, cc = np.nonzero(~pad)
edge = [(r, c) for r, c in zip(rr, cc) if c == west or r == h - north - 1]
for r, c in edge:
    for d in range(6):
        nc, nr = neighbour(c, r, d)
        if 0 <= nc < w and 0 <= nr < h and pad[nr, nc]:
            g[r, c, 3] &= ~np.uint8(1 << (1 + d)); g[r, c, 4] &= ~np.uint8(1 << d)
b[P + 8:P + 8 + 16 * w * h] = g.tobytes()
b[-4:] = struct.pack("<I", zlib.crc32(bytes(b[:-4])) & 0xFFFFFFFF)
Path(dst).write_bytes(bytes(b))
print(f"{w}x{h}: west {west} cols + north {north} rows cleaned ({int(pad.sum())} hexes, {int((pad & ~land_pad).sum())} kept as sea) -> {dst}")
