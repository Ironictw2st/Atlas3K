"""Dump a battle tile_list.bin (same FASTBIN0 1/1 layout as the campaign one). usage: tilelist_dump.py <tile_list.bin> [n]"""
import collections, struct, sys

d = open(sys.argv[1], 'rb').read()
N = int(sys.argv[2]) if len(sys.argv) > 2 else 12
print(len(d), d[:12])
o = 12


def strs():
    global o
    n, = struct.unpack_from('<I', d, o); o += 4; r = []
    for _ in range(n):
        l, = struct.unpack_from('<H', d, o); r.append(d[o + 2:o + 2 + l].decode()); o += 2 + l
    return r


P = strs(); C = strs()
print(len(P), 'paths'); [print('  ', i, p) for i, p in enumerate(P)]
print('climates', C)
f = struct.unpack_from('<6f', d, o); o += 24
I = struct.unpack_from('<11i', d, o); o += 44
print('floats', f); print('ints', I)
m = d[o]; o += 1
n, = struct.unpack_from('<I', d, o); o += 4
print('marker', m, 'records', n, 'bytes left', len(d) - o, 'per record', (len(d) - o) / max(n, 1))
recs = [struct.unpack_from('<HIBHHBBff', d, o + 21 * i) for i in range(n)]
for r in recs[:N]: print(' ', r)
print('orient', collections.Counter(r[5] for r in recs), 'flag', collections.Counter(r[6] for r in recs),
      'path', collections.Counter(r[1] for r in recs).most_common(8))
