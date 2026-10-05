"""Repair the trade-route layer of a map.hex in place: drop one-way links (a bit whose neighbour does not point
back, or points off the map). CAIME's trade-route processor never finishes on a layer with one-way links.
Usage: python trade_fix.py <map.hex> [out.hex]"""
import sys, struct, zlib
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
import crop_scale_map_hex as C
from rebuild_hex import unpack
from hexgrid import neighbour


def fix(src):
    P, w, h = C.locate_dims(src)
    g = np.frombuffer(src, np.uint8, 16 * w * h, P + 8).reshape(h, w, 16).copy()
    t = unpack(g)["trade"].copy(); dropped = 0
    for _ in range(10):
        changed = 0
        for r, c in zip(*np.nonzero(t)):
            for d in range(6):
                if (t[r, c] >> d) & 1:
                    nc, nr = neighbour(c, r, d)
                    if not (0 <= nc < w and 0 <= nr < h) or not ((t[nr, nc] >> ((d + 3) % 6)) & 1):
                        t[r, c] &= ~(1 << d); changed += 1
        dropped += changed
        if not changed: break
    g[..., 4] = (g[..., 4] & 0x3F) | ((t & 3) << 6).astype(np.uint8)          # trade = ((b5 & 15) << 2) | (b4 >> 6)
    g[..., 5] = (g[..., 5] & 0xF0) | ((t >> 2) & 15).astype(np.uint8)
    out = bytearray(src); out[P + 8:P + 8 + 16 * w * h] = g.tobytes()
    out[-4:] = struct.pack("<I", zlib.crc32(bytes(out[:-4])) & 0xFFFFFFFF)
    return bytes(out), dropped


if __name__ == "__main__":
    src = Path(sys.argv[1]).read_bytes(); out, n = fix(src)
    Path(sys.argv[2] if len(sys.argv) > 2 else sys.argv[1]).write_bytes(out); print(f"trade: {n} one-way bits dropped")
