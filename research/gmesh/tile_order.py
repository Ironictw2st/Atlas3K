"""BOB's tile visiting order in FUN_18016ae30 (frida_gheight3 dump): per centre point, the tile-list record indices of
the tiles queried, in call order, vs ascending record order."""
import glob, sys, collections, numpy as np
sys.path.insert(0, r"Z:\Claude\TerryClone\research\derived_maps")
import tiles_lib as TL
F = np.float32
paths, cl, fl, ints, rec = TL.read_tile_list(r"Z:\Claude\TerryClone\output\mesh_parity\gmesh_pack\terrain\campaigns\3k_190e_expanded_map\tile_list.bin")
byxy = collections.defaultdict(list)
for i, r in enumerate(rec): byxy[(int(r['x']), int(r['y']))].append(i)
BIN = 'Z:/Claude/TerryClone/research/bob_re/frida_out/frida_gheight3_main190_bin/'
dt = np.dtype([('x', '<f4'), ('z', '<f4'), ('tx', '<i2'), ('ty', '<i2'), ('o', '<u2'), ('valid', 'u1'), ('flag', 'u1'),
               ('lf', '<f4'), ('res', '<f4'), ('hfo', '<f4'), ('n', '<u4')])
c = np.concatenate([np.fromfile(f, dt) for f in sorted(glob.glob(BIN + '*_calls.bin'))])
c = c[np.argsort(c['n'], kind='stable')]
T = F(595.1) / F(1784); Tp = F(F(F(1) / F(2956)) * F(F(2956) * T)); cell = F(F(F(2956) * Tp) / F(5912))
grid = {float(F(F(I) * cell)) for I in range(5913)}
seqs = collections.defaultdict(list)
for r in c:
    if float(r['x']) in grid and float(r['z']) in grid:
        key = (float(r['x']), float(r['z']))
        recs = [i for i in byxy[(int(r['tx']), int(r['ty']))] if (rec[i]['orient'] & 0xF0) == (r['o'] & 0xF0)]
        rid = recs[0] if recs else -1
        if not seqs[key] or seqs[key][-1] != rid: seqs[key].append(rid)
multi = [s for s in seqs.values() if len(s) > 1]
print(len(seqs), 'points;', len(multi), 'with >1 tile')
asc = sum(1 for s in multi if s == sorted(s)); desc = sum(1 for s in multi if s == sorted(s, reverse=True))
print('ascending', asc, 'descending', desc)
for s in multi[:10]: print(s, [(int(rec[i]['x']), int(rec[i]['y'])) for i in s if i >= 0])
firsts=[]
for s in multi:
    seg=[]
    for x in s:
        if x in seg: break
        seg.append(x)
    if len(seg)>1: firsts.append(seg)
print(len(firsts), 'asc', sum(s==sorted(s) for s in firsts), 'desc', sum(s==sorted(s,reverse=True) for s in firsts))
bad=[s for s in firsts if s!=sorted(s,reverse=True)][:8]
for s in bad: print(s, [(int(rec[i]['x']), int(rec[i]['y']), int(rec[i]['orient'])) for i in s if i>=0])
