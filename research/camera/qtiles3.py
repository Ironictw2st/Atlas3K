import json, sys, collections
import numpy as np
sys.path.insert(0, '../trees'); from tiles import read_tile_list
F = np.float32
nodes = json.load(open('../bob_re/frida_out/cam_s4h_qnodes.json'))['nodes']
paths, clim, fl, ints, gm = read_tile_list('../../Vanilla/Map/terrain/campaigns/3k_dlc07_main_map/global_map/tile_list.bin')
where = {}
for n in nodes:
    for t in n['tiles']: where[t] = n
print('stored', len(where), 'all flagged in gm list:', all(gm[t]['flag'] & 1 for t in where), 'flagged count', sum(1 for r in gm if r['flag'] & 1))
# tile sizes from the tile database names in paths? use the CLI-free approach: size from path folder name WxH if present
import re
def size(p):
    m = re.search(r'(\d+)x(\d+)', p); return (int(m[1]), int(m[2])) if m else None
T = F(F(595.1) / F(1784)); ZS = F(1.15476)
ok = bad = unk = 0; ex = []
for t, n in where.items():
    r = gm[t]; sz = size(paths[r['path']])
    if sz is None: unk += 1; continue
    w, h = sz
    if (r['ori'] & 0xF0) in (0x20, 0x80): w, h = h, w
    x0 = F(F(r['x']) * T); x1 = F(F(r['x'] + w) * T); z0 = F(F(F(r['y']) * T) * ZS); z1 = F(F(F(r['y'] + h) * T) * ZS)
    b = n['b']
    inside = b[0] <= x0 and x1 <= b[3] and b[2] <= z0 and z1 <= b[5]
    # deepest: no child contains it -> check the node's children bounds via splitting at midpoints
    mx = F((F(b[0]) + F(b[3])) * F(0.5)); mz = F((F(b[2]) + F(b[5])) * F(0.5))
    childfits = (x1 <= mx or x0 >= mx) and (z1 <= mz or z0 >= mz)
    if inside and (n['d'] == 7 or not childfits): ok += 1
    else:
        bad += 1
        if len(ex) < 6: ex.append((t, r['x'], r['y'], r['ori'], w, h, (x0, z0, x1, z1), b, n['d']))
print('ok', ok, 'bad', bad, 'unknown size', unk)
for e in ex: print(e)
cnt = collections.Counter(); ex = []
for t, n in where.items():
    r = gm[t]; b = n['b']
    for name, (px, pz) in {'min corner': (F(F(r['x']) * T), F(F(F(r['y']) * T) * ZS)), 'cell centre': (F(F(r['x'] + 0.5) * T), F(F(F(r['y'] + 0.5) * T) * ZS))}.items():
        if b[0] <= px <= b[3] and b[2] <= pz <= b[5]: cnt[name] += 1
        elif name == 'min corner' and len(ex) < 5: ex.append((r['x'], r['y'], r['ori'], px, pz, b))
print(cnt, len(where)); [print(e) for e in ex]
root = nodes[0]['b']; lw = (root[3] - root[0]) / 128; lh = (root[5] - root[2]) / 128
diff = 0; szs = collections.Counter()
for t, n in where.items():
    r = gm[t]; b = n['b']
    szs[(round((b[3]-b[0])/lw), round((b[5]-b[2])/lh))] += 1
    c = (int((r['x'] * float(T) - root[0]) // lw), int((r['y'] * float(T) * float(ZS) - root[2]) // lh))
    e = (int(((r['x'] + 0.5) * float(T) - root[0]) // lw), int(((r['y'] + 0.5) * float(T) * float(ZS) - root[2]) // lh))
    diff += c != e
print('leaf sizes', szs, 'tiles whose corner and cell centre are in different leaves:', diff)
k = 0
for t, n in where.items():
    r = gm[t]; b = n['b']
    c = (int((r['x'] * float(T) - root[0]) // lw), int((r['y'] * float(T) * float(ZS) - root[2]) // lh))
    e = (int(((r['x'] + 0.5) * float(T) - root[0]) // lw), int(((r['y'] + 0.5) * float(T) * float(ZS) - root[2]) // lh))
    if c != e and k < 4:
        k += 1; print(r['x'], r['y'], 'corner', r['x'] * float(T), r['y'] * float(T) * float(ZS), 'centre', (r['x'] + .5) * float(T), (r['y'] + .5) * float(T) * float(ZS), 'leaf', b, c, e)
