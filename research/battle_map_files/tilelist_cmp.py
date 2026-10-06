"""Field diff of two tile_list.bin files (native vs BOB): header, path order, records (by name), first divergence.
usage: tilelist_cmp.py <native> <bob>"""
import struct, sys
from collections import Counter


def load(p):
    d = open(p, 'rb').read(); o = 12

    def strs():
        nonlocal o
        n, = struct.unpack_from('<I', d, o); o += 4; r = []
        for _ in range(n):
            l, = struct.unpack_from('<H', d, o); r.append(d[o + 2:o + 2 + l].decode()); o += 2 + l
        return r
    P = strs(); C = strs()
    f = struct.unpack_from('<6f', d, o); o += 24
    I = struct.unpack_from('<11i', d, o); o += 44
    m = d[o]; o += 1
    n, = struct.unpack_from('<I', d, o); o += 4
    recs = []
    for i in range(n):
        v, pi, ci, x, y, ori, fl, lo, hi = struct.unpack_from('<HIBHHBBff', d, o + 21 * i)
        recs.append((P[pi].replace('terrain\\tiles\\battle\\', ''), C[ci], x, y, ori, fl, lo, hi))
    return dict(P=P, C=C, f=f, I=I, m=m, recs=recs)


a, b = load(sys.argv[1]), load(sys.argv[2])
for k in ('C', 'f', 'I', 'm'):
    print(k, 'same' if a[k] == b[k] else f'native {a[k]} bob {b[k]}')
print('records', len(a['recs']), len(b['recs']), 'paths', len(a['P']), len(b['P']))
ka = Counter(r[:5] for r in a['recs']); kb = Counter(r[:5] for r in b['recs'])
print('only native:', sorted((ka - kb).elements())[:20])
print('only bob   :', sorted((kb - ka).elements())[:20])
hs = sum(1 for r in a['recs'] if r[:5] in kb)
same_h = Counter(r for r in a['recs']) & Counter(r for r in b['recs'])
print('records equal incl. heights:', sum(same_h.values()))
for i, (x, y) in enumerate(zip(a['recs'], b['recs'])):
    if x != y:
        print('first divergence at record', i, '\n  native', x, '\n  bob   ', y); break
print('path order equal:', a['P'] == b['P'])
