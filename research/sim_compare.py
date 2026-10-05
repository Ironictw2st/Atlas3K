"""Compare TileMatchSimulator output (CSV: location,x,y,rotation,climate,layer) with a BOB tile_list.bin.
usage: sim_compare.py <sim.csv> <tile_list.bin>"""
import struct, sys, collections
def read_tl(p):
    b = open(p, 'rb').read(); o = 12
    def strs():
        nonlocal o
        n = struct.unpack_from('<I', b, o)[0]; o += 4; out = []
        for _ in range(n):
            l = struct.unpack_from('<H', b, o)[0]; out.append(b[o+2:o+2+l].decode('latin1')); o += 2 + l
        return out
    paths = strs(); clim = strs(); o += 24 + 44 + 1
    cnt = struct.unpack_from('<I', b, o)[0]; o += 4
    recs = []
    for i in range(cnt):
        v, pi, c, x, y, ori, fl = struct.unpack_from('<HIBHHBB', b, o + i * 21)
        recs.append((paths[pi].lower().rstrip(chr(92)), x, y, ori & 0xf0, c, fl))
    return recs
sim = []
for line in open(sys.argv[1]):
    loc, x, y, r, c, layer = line.strip().rsplit(',', 5)
    sim.append((loc.lower().rstrip(chr(92)), int(x), int(y), int(r), int(c), int(layer)))
ref = read_tl(sys.argv[2])
print('records: sim', len(sim), 'ref', len(ref))
print('ref flags', collections.Counter(r[5] for r in ref).most_common(5))
print('sim layers', collections.Counter(s[5] for s in sim))
key = lambda t: (t[0], t[1], t[2], t[3])
S = collections.Counter(key(s) for s in sim); R = collections.Counter(key(r) for r in ref)
only_s = S - R; only_r = R - S
print('matching', sum((S & R).values()), 'only sim', sum(only_s.values()), 'only ref', sum(only_r.values()))
pos = lambda c: sorted(c.elements(), key=lambda t: (t[2], t[1]))
print('first only-sim:', pos(only_s)[:15]); print('first only-ref:', pos(only_r)[:15])
# position-only match ignoring path
P = collections.Counter((s[1], s[2]) for s in sim); Q = collections.Counter((r[1], r[2]) for r in ref)
print('positions only sim', sum((P - Q).values()), 'only ref', sum((Q - P).values()))
# breakdown ignoring rotation, and rotation agreement where position+path agree
K2 = lambda t: (t[0], t[1], t[2])
S2 = collections.Counter(K2(s) for s in sim if s[5] == 1); R2 = collections.Counter(K2(r) for r in ref)
print('ignoring rotation: matching', sum((S2 & R2).values()), 'only sim', sum((S2 - R2).values()), 'only ref', sum((R2 - S2).values()))
refrot = {}
for r in ref: refrot.setdefault(K2(r), []).append(r[3])
agree = collections.Counter()
for s in sim:
    if s[5] != 1: continue
    rr = refrot.get(K2(s))
    if rr: agree[(s[3], rr[0])] += 1
print('rotation pairs (sim, ref):', agree.most_common(12))
big = [s for s in sim if 'mountains' in s[0] or '8x8' in s[0] or '16x16' in s[0]]
print('first sim large:', big[:5])
bigr = [r for r in ref if K2(r) in set(K2(b) for b in big[:200])][:5]
print('ref same:', bigr)
