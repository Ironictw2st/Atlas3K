"""BOB's TRIANGLE_MERGER inputs (frida_gmesh_combo.js: vertices x, y, z, normal; flags; triangles) for the first 24
merges vs the native builder's (ATLAS3K_GMESH_DUMP with ATLAS3K_GMESH_BOB_GRIDS). usage: merger_inputs_cmp.py"""
import json, os, sys, numpy as np
F = np.float32
JL = 'Z:/Claude/TerryClone/research/bob_re/frida_out/frida_gcombo_main190.jsonl'
BIN = 'Z:/Claude/TerryClone/research/bob_re/frida_out/frida_gcombo_main190_bin/'
NAT = 'Z:/Claude/TerryClone/output/mesh_parity/gmesh_native_dump/'
MAP = json.load(open('Z:/Claude/TerryClone/output/mesh_parity/gmesh_bob_grids/mapping.json'))
msgs = [json.loads(l) for l in open(JL, encoding='utf-8')]
by = {}
for m in msgs:
    if m['kind'] in ('verts', 'flags', 'tris', 'merged') and 'call' in m: by[(m['kind'], m['call'])] = m
T = F(595.1) / F(1784); Tp = F(F(F(1) / F(2956)) * F(F(2956) * T)); ext = F(F(2956) * Tp)
for c in range(24):
    kind, k, name, key = MAP[c]
    if key is None or ('verts', c) not in by: continue
    v = np.fromfile(BIN + by[('verts', c)]['file'], np.float32).reshape(-1, 6)
    fl = np.fromfile(BIN + by[('flags', c)]['file'], np.uint8)
    tr = np.fromfile(BIN + by[('tris', c)]['file'], np.uint32)
    n = int(round(len(v) ** 0.5)); row, col = map(int, key.split('_')[1:])
    I = np.arange(n) + col * (n - 1); J = np.arange(n) + row * (n - 1)
    px = np.array([F(i * float(ext) / 5912) for i in I], F); pz = np.array([F(j * float(ext) / 5912) for j in J], F)
    xs = np.tile(px, n); zs = np.repeat(pz, n)
    ny = np.fromfile(NAT + key + '.y.bin', np.float32)
    nf = np.fromfile(NAT + key + '.flags.bin', np.uint8)
    nn = np.fromfile(NAT + key + '.normals.bin', np.float32).reshape(-1, 3)
    valid = v[:, 1] != -20
    print(f'{key:10s} verts {len(v)} x {np.mean(v[:,0]==xs):.4f} z {np.mean(v[:,2]==zs):.4f} y {np.mean(v[:,1]==ny):.4f} '
          f'flags {np.mean(fl==nf):.4f} (valid {np.mean((fl==nf)[valid]):.4f}) normals {np.mean((v[:,3:6]==nn).all(1)):.4f} '
          f'tris {len(tr)//3}')
    bad = np.where((fl != nf) & valid)[0][:5]
    for b in bad: print('   flag diff at', b % n, b // n, 'bob', fl[b], 'ours', nf[b])
    badn = np.where(~(v[:, 3:6] == nn).all(1) & valid)[0][:3]
    for b in badn: print('   normal diff at', b % n, b // n, v[b, 3:6], nn[b])

# triangle lists: BOB's input vs the native quad split
for c in range(24):
    kind, k, name, key = MAP[c]
    if key is None or ('tris', c) not in by: continue
    tr = np.fromfile(BIN + by[('tris', c)]['file'], np.uint32)
    y = np.fromfile(NAT + key + '.y.bin', np.float32); n = int(round(len(y) ** 0.5))
    nat = []
    for j in range(n - 1):
        for i in range(n - 1):
            a = j * n + i; b = a + 1; cc = a + n; d = cc + 1
            if y[a] == -20 or y[b] == -20 or y[cc] == -20 or y[d] == -20: continue
            nat += [a, cc, b, cc, d, b]
    print(key, 'tris equal', len(nat) == len(tr) and np.array_equal(np.array(nat, np.uint32), tr), len(nat)//3, len(tr)//3)
