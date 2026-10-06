"""Classify tile_list.bin differences by position: same, rotation only, other tile, missing. usage: tilelist_classify.py <native> <bob>"""
import struct, sys


def load(p):
    d = open(p, 'rb').read(); o = 12

    def strs():
        nonlocal o
        n, = struct.unpack_from('<I', d, o); o += 4; r = []
        for _ in range(n):
            l, = struct.unpack_from('<H', d, o); r.append(d[o + 2:o + 2 + l].decode()); o += 2 + l
        return r
    P = strs(); strs(); o += 24 + 44 + 1
    n, = struct.unpack_from('<I', d, o); o += 4
    out = []
    for i in range(n):
        v, pi, ci, x, y, ori, fl, lo, hi = struct.unpack_from('<HIBHHBBff', d, o + 21 * i)
        out.append((P[pi].split('battle\\')[-1], x, y, ori))
    return out


a, b = load(sys.argv[1]), load(sys.argv[2])
A = {}; B = {}
for n, x, y, o in a: A.setdefault((x, y), []).append((n, o))
for n, x, y, o in b: B.setdefault((x, y), []).append((n, o))
same = rot = tile = 0
for k, v in A.items():
    w = B.get(k)
    if w == v: same += 1
    elif w and [t for t, _ in w] == [t for t, _ in v]: rot += 1
    elif w: tile += 1
print('positions', len(A), len(B), 'same', same, 'rotation only', rot, 'other tile', tile,
      'only native', len(set(A) - set(B)), 'only bob', len(set(B) - set(A)))
for k in sorted(A):
    if any(s in A[k][0][0] for s in ('8x8', '12x', '16x')): print(' big', k, A[k], B.get(k))
