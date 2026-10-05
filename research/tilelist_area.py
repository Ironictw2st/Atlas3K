"""Records of two tile_list.bin files inside a box: tile, anchor, rotation, flow bit, side by side.
usage: tilelist_area.py <a.bin> <b.bin> x0 y0 x1 y1 [filter]"""
import struct, sys
BS = chr(92)


def read(p):
    b = open(p, "rb").read(); o = 12
    def strs():
        nonlocal o
        n = struct.unpack_from("<I", b, o)[0]; o += 4; out = []
        for _ in range(n):
            l = struct.unpack_from("<H", b, o)[0]; out.append(b[o + 2:o + 2 + l].decode("latin1")); o += 2 + l
        return out
    paths = strs(); strs(); o += 24 + 44 + 1
    cnt = struct.unpack_from("<I", b, o)[0]; o += 4
    out = []
    for i in range(cnt):
        v, pi, c, x, y, ori, fl = struct.unpack_from("<HIBHHBB", b, o + i * 21)
        p = paths[pi].rstrip(BS).split(BS)
        out.append((i, p[-2] + "/" + p[-1], x, y, ori & 0xF0, (ori >> 2) & 1))
    return out


a, b = read(sys.argv[1]), read(sys.argv[2])
x0, y0, x1, y1 = map(int, sys.argv[3:7]); flt = sys.argv[7] if len(sys.argv) > 7 else ""
for ra, rb in zip(a, b):
    if x0 <= ra[2] <= x1 and y0 <= ra[3] <= y1 and flt in ra[1]:
        mark = "" if ra[1:] == rb[1:] else "   <-- " + str(rb[1:])
        print(f"#{ra[0]:6d} {ra[1]:40s} ({ra[2]},{ra[3]}) rot {ra[4]:3d} flow {ra[5]}{mark}")
