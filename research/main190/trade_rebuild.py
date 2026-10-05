"""Rebuild the trade-route layer of the warped map.hex from 190E's own trade graph.

rebuild_hex.py draws trade lines and then links every pair of adjacent trade hexes, which fuses parallel lines
into loops; CAIME's trade-route processor never finishes on the result (the original 190E layer processes
instantly). Here every 190E trade link (a mutual bit pair between adjacent hexes) is warped to the new grid and
drawn as a hex line; bits are set only between consecutive hexes of those lines.
Usage: python trade_rebuild.py <map.hex in> [out]   (the 190E source is fixed below)"""
import sys, struct, zlib
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
import crop_scale_map_hex as C
from rebuild_hex import unpack
from hexgrid import neighbour, centre, nearest_hex, hex_line
from warp import Warp, WarpMapping, current

SRC190 = r"Z:/Claude/190Expanded/campaign_maps/map.hex"
MAP = WarpMapping(current())


def grid(b):
    P, w, h = C.locate_dims(b); return P, w, h, np.frombuffer(b, np.uint8, 16 * w * h, P + 8).reshape(h, w, 16).copy()


def rebuild(new_bytes, log=print):
    _, w0, h0, g0 = grid(Path(SRC190).read_bytes()); t0 = unpack(g0)["trade"]
    P, w, h, g = grid(new_bytes)
    def m(c, r):
        x, z = centre(c, r); nx, nz = MAP.fwd_world(x, z)
        a, b = nearest_hex(np.array([nx]), np.array([nz]), w, h); return int(a[0]), int(b[0])
    t = np.zeros((h, w), np.int32); edges = 0
    for r, c in zip(*np.nonzero(t0)):
        for d in range(6):
            if not (t0[r, c] >> d) & 1: continue
            nc, nr = neighbour(c, r, d)
            if not (0 <= nc < w0 and 0 <= nr < h0) or (nc, nr) < (c, r): continue      # each link once
            if not (t0[nr, nc] >> ((d + 3) % 6)) & 1: continue
            line = hex_line(m(c, r), m(nc, nr)); edges += 1
            for a, b in zip(line, line[1:]):
                for k in range(6):
                    if neighbour(a[0], a[1], k) == b: t[a[1], a[0]] |= 1 << k; t[b[1], b[0]] |= 1 << ((k + 3) % 6)
    g[..., 4] = (g[..., 4] & 0x3F) | ((t & 3) << 6).astype(np.uint8)
    g[..., 5] = (g[..., 5] & 0xF0) | ((t >> 2) & 15).astype(np.uint8)
    out = bytearray(new_bytes); out[P + 8:P + 8 + 16 * w * h] = g.tobytes()
    out[-4:] = struct.pack("<I", zlib.crc32(bytes(out[:-4])) & 0xFFFFFFFF)
    deg = np.array([bin(int(v)).count("1") for v in t[t > 0]])
    log(f"trade: {edges} 190E links redrawn -> {int((t > 0).sum())} hexes, degree histogram {np.bincount(deg, minlength=7)[:7].tolist()}")
    return bytes(out)


if __name__ == "__main__":
    out = rebuild(Path(sys.argv[1]).read_bytes())
    Path(sys.argv[2] if len(sys.argv) > 2 else sys.argv[1]).write_bytes(out)
