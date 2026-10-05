"""Targeted get_height_worker dump (frida_gheight3.js, BOB mesh k=170 = Land_10_10): at grid points where the native
height differs from BOB's, show BOB's calls (tile, valid, lf, result) at the centre position.
usage: g3.py [n points]"""
import glob, sys, numpy as np, collections
F = np.float32
BIN = 'Z:/Claude/TerryClone/research/bob_re/frida_out/frida_gheight3_main190_bin/'
dt = np.dtype([('x', '<f4'), ('z', '<f4'), ('tx', '<i2'), ('ty', '<i2'), ('o', '<u2'), ('valid', 'u1'), ('flag', 'u1'),
               ('lf', '<f4'), ('res', '<f4'), ('hfo', '<f4'), ('n', '<u4')])
c = np.concatenate([np.fromfile(f, dt) for f in sorted(glob.glob(BIN + '*_calls.bin'))])
print(len(c), 'calls; valid', c['valid'].mean())
v = c[c['valid'] == 1]; hf = v['res'] - v['lf']
print('valid calls with nonzero hf', np.mean(hf != 0))
T = F(595.1) / F(1784); Tp = F(F(F(1) / F(2956)) * F(F(2956) * T)); cell = F(F(F(2956) * Tp) / F(5912))
key, row, col = 'Land_10_0', 10, 0
b = np.fromfile(f'Z:/Claude/TerryClone/output/mesh_parity/gmesh_bob_grids/{key}.bob.bin', np.float32).reshape(370, 370)
a = np.fromfile(f'Z:/Claude/TerryClone/output/mesh_parity/gmesh_native_dump2/{key}.y.bin', np.float32).reshape(370, 370)
mis = np.argwhere(a != b)
idx = collections.defaultdict(list)
order = np.lexsort((c['n'],))
for k in range(len(c)):
    idx[(float(c['x'][k]), float(c['z'][k]))].append(k)
for j, i in mis[:int(sys.argv[1]) if len(sys.argv) > 1 else 5]:
    x = F(F(col * 369 + i) * cell); z = F(F(row * 369 + j) * cell)
    print(f'point ({i},{j}) bob {b[j,i]:.7f} ours {a[j,i]:.7f}')
    for k in idx.get((float(x), float(z)), [])[:8]:
        r = c[k]; print(f'   tile {r["tx"]},{r["ty"]} o {r["o"]:#x} valid {r["valid"]} lf {r["lf"]:.7f} res {r["res"]:.7f} hfo {r["hfo"]:.4g} n {r["n"]}')
x = F(F(col * 369 + 12) * cell); z = F(F(row * 369 + 0) * cell)
m = (np.abs(c['x'] - x) < 0.01) & (np.abs(c['z'] - z) < 0.01)
print('target', repr(x), repr(z))
for r in c[m][:12]: print(repr(r['x']), repr(r['z']), r['tx'], r['ty'], hex(r['o']), r['valid'], r['lf'], r['res'])
print('x range', c['x'].min(), c['x'].max(), 'z range', c['z'].min(), c['z'].max(), 'mesh size', float(369*cell))
