"""Walk the native placement trace (ATLAS3K_BATTLE_TILE_TRACE) in placement order and report the first placements
whose (tile, x, y, rotation) is not in BOB's tile_list.bin. usage: placement_first_bad.py <trace.tsv> <bob tile_list.bin> [n]"""
import struct, sys


def bob(p):
    d = open(p, 'rb').read(); o = 12

    def strs():
        nonlocal o
        n, = struct.unpack_from('<I', d, o); o += 4; r = []
        for _ in range(n):
            l, = struct.unpack_from('<H', d, o); r.append(d[o + 2:o + 2 + l].decode()); o += 2 + l
        return r
    P = strs(); strs(); o += 24 + 44 + 1
    n, = struct.unpack_from('<I', d, o); o += 4
    s = set()
    for i in range(n):
        v, pi, ci, x, y, ori, fl, lo, hi = struct.unpack_from('<HIBHHBBff', d, o + 21 * i)
        s.add((P[pi].lower(), x, y, ori & 0xF0))
    return s


B = bob(sys.argv[2])
N = int(sys.argv[3]) if len(sys.argv) > 3 else 15
bad = 0
for i, line in enumerate(open(sys.argv[1])):
    loc, x, y, rot, layer = line.rstrip('\n').split('\t')
    key = (loc.lower(), int(x), int(y), int(rot))
    if key not in B:
        print(i, loc.split('battle\\')[-1], x, y, hex(int(rot)), 'layer', layer,
              'same pos in bob:', [k for k in B if k[1] == int(x) and k[2] == int(y)])
        bad += 1
        if bad >= N: break
