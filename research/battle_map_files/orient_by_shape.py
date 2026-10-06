"""Orientation counts per tile shape (square / non-square, from the folder name WxH) in a tile_list.bin. usage: orient_by_shape.py <tile_list.bin>"""
import re, struct, sys
from collections import Counter

d = open(sys.argv[1], 'rb').read(); o = 12


def strs():
    global o
    n, = struct.unpack_from('<I', d, o); o += 4; r = []
    for _ in range(n):
        l, = struct.unpack_from('<H', d, o); r.append(d[o + 2:o + 2 + l].decode()); o += 2 + l
    return r


P = strs(); strs(); o += 24 + 44 + 1
n, = struct.unpack_from('<I', d, o); o += 4
c = Counter()
for i in range(n):
    v, pi, ci, x, y, ori, fl, lo, hi = struct.unpack_from('<HIBHHBBff', d, o + 21 * i)
    m = re.search(r'\\(\d+)x(\d+)', P[pi])
    shape = 'unknown' if not m else ('square' if m.group(1) == m.group(2) else 'nonsquare')
    c[(shape, ori & 0xF0)] += 1
for k in sorted(c): print(k, c[k])
