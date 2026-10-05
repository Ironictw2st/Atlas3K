"""Fit WARSCAPE::TERRAIN_QUAD_TREE's visiting order to BOB's height-query call dump (frida_gheight3, mesh k=170):
per grid point, the distinct tiles BOB asked in call order must be ascending in (leaf pre-order position, record).
Leaf of a record = descend from the root box by the centre of its tile rectangle. usage: tree_fit.py"""
import collections, glob, itertools, sys
import numpy as np
sys.path.insert(0, r"Z:\Claude\TerryClone\research\derived_maps")
import tiles_lib as TL
F = np.float32
paths, cl, fl, ints, rec = TL.read_tile_list(r"Z:\Claude\TerryClone\output\mesh_parity\gmesh_pack\terrain\campaigns\3k_190e_expanded_map\tile_list.bin")
db = TL.read_db()
W, H = ints[1], ints[2]
T = F(595.1) / F(1784); Tp = F(F(F(1) / F(W)) * F(F(W) * T))
maxX, maxZ = F(F(W) * Tp), F(F(H) * Tp)
size_of = []
for p in paths:
    t = db.get(p.lower().rstrip('\\') + '\\') or db.get(p.lower())
    size_of.append((t['w'], t['h']) if t else (1, 1))
byxy = collections.defaultdict(list)
for i, r in enumerate(rec): byxy[(int(r['x']), int(r['y']))].append(i)
BIN = 'Z:/Claude/TerryClone/research/bob_re/frida_out/frida_gheight3_main190_bin/'
dt = np.dtype([('x', '<f4'), ('z', '<f4'), ('tx', '<i2'), ('ty', '<i2'), ('o', '<u2'), ('valid', 'u1'), ('flag', 'u1'),
               ('lf', '<f4'), ('res', '<f4'), ('hfo', '<f4'), ('n', '<u4')])
c = np.concatenate([np.fromfile(f, dt) for f in sorted(glob.glob(BIN + '*_calls.bin'))])
c = c[np.argsort(c['n'], kind='stable')]
cell = F(F(F(W) * Tp) / F(2 * W))
grid = {float(F(F(I) * cell)) for I in range(2 * W + 1)}
seqs = collections.OrderedDict()
cur = None
for r in c:
    if float(r['x']) in grid and float(r['z']) in grid:
        key = (float(r['x']), float(r['z'])); cur = key
        recs = [i for i in byxy[(int(r['tx']), int(r['ty']))] if (rec[i]['orient'] & 0xF0) == (r['o'] & 0xF0)]
        rid = recs[0] if recs else -1
        s = seqs.setdefault(key, [])
        if rid not in s: s.append(rid)
multi = [s for s in seqs.values() if len(s) > 1 and -1 not in s]
print(len(seqs), 'points', len(multi), 'with >1 tile')
need = sorted({i for s in multi for i in s})


def keys(depth, visit, root):
    rank = {c: k for k, c in enumerate(visit)}
    rx0, rz0, rx1, rz1 = root
    out = {}
    for i in need:
        r = rec[i]; w, h = size_of[r['path']]
        if (r['orient'] & 0xF0) in (0x20, 0x80): w, h = h, w
        x0 = F(F(int(r['x'])) * Tp); z0 = F(F(int(r['y'])) * Tp)
        x1 = F(x0 + F(F(w) * Tp)); z1 = F(z0 + F(F(h) * Tp))
        cx = F(F(x0 + x1) * F(0.5)); cz = F(F(z0 + z1) * F(0.5))
        bx0, bz0, bx1, bz1 = rx0, rz0, rx1, rz1; path = 0
        for d in range(depth):
            mx = F(F(bx1 + bx0) * F(0.5)); mz = F(F(bz1 + bz0) * F(0.5))
            if bx0 <= cx <= mx and mz <= cz <= bz1: ch = 0
            elif mx <= cx <= bx1 and mz <= cz <= bz1: ch = 1
            elif bx0 <= cx <= mx and bz0 <= cz <= mz: ch = 2
            else: ch = 3
            path = path * 4 + rank[ch]
            if ch == 0: bx1, bz0 = mx, mz
            elif ch == 1: bx0, bz0 = mx, mz
            elif ch == 2: bx1, bz1 = mx, mz
            else: bx0, bz1 = mx, mz
        out[i] = (path, i)
    return out


roots = {"(-1,-1)..(maxX,maxZ)": (F(-1), F(-1), maxX, maxZ), "(0,0)..(maxX,maxZ)": (F(0), F(0), maxX, maxZ),
         "(-1,-1)..(maxX+1,maxZ+1)": (F(-1), F(-1), F(maxX + 1), F(maxZ + 1))}
res = []
for depth in range(4, 13):
    for visit in itertools.permutations(range(4)):
        for rn, root in roots.items():
            k = keys(depth, visit, root)
            ok = sum(all(k[s[j]] < k[s[j + 1]] for j in range(len(s) - 1)) for s in multi)
            res.append((ok / len(multi), depth, ''.join(map(str, visit)), rn))
for r in sorted(res, reverse=True)[:10]: print(f"{r[0]:.4%} depth {r[1]} visit {r[2]} root {r[3]}")


if __name__ == "__main__" and len(sys.argv) > 1:
    k = keys(8, (0, 1, 2, 3), roots["(-1,-1)..(maxX,maxZ)"])
    bad = [s for s in multi if not all(k[s[j]] < k[s[j + 1]] for j in range(len(s) - 1))]
    print(len(bad), 'bad')
    import collections as C
    pat = C.Counter()
    for s in bad[:4000]:
        for j in range(len(s) - 1):
            if not k[s[j]] < k[s[j + 1]]:
                a, b = s[j], s[j + 1]
                pat[('same leaf' if k[a][0] == k[b][0] else 'diff leaf', 'rec desc' if a > b else 'rec asc')] += 1
    print(pat)
    for s in bad[:6]:
        print([(i, int(rec[i]['x']), int(rec[i]['y']), int(rec[i]['orient']), size_of[rec[i]['path']], k[i][0]) for i in s])
