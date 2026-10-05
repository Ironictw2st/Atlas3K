import sys, collections, numpy as np
sys.path.insert(0, '.')
from bob_spline import *
import river_cmp, xml.etree.ElementTree as ET
L = "C:/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/assembly_kit_190E/raw_data/terrain/campaigns/3k_190e_expanded_map/3k_190e_expanded_map.1972bd217a4938e.layer"
B = river_cmp.summary(r"Z:/Claude/TerryClone/output/bob_runs/20261004_230523_frida_trees_main190/bob_terrain_out/models")
rs = sorted(rivers(L), key=lambda r: -int(r[0], 16))
wmap = {}
for ent in ET.parse(L).getroot().iter('entity'):
    sp = ent.find('ECRiverSpline')
    if sp is not None: wmap[ent.get('id')] = [float(p.get('width', '1')) for p in sp.iter('point')]
extra = [F(F(k) * F(F(1) / F(8))) for k in range(7)]
k = int(sys.argv[1]) if len(sys.argv) > 1 else 0
eid, name, pts, W, step = rs[k]; s = Spline()
for a, b in zip(pts, pts[1:]):
    p0 = a[0]; p3 = b[0]; s.add(W(p0), W(tuple(p0[i] + a[2][i] for i in range(3))), W(tuple(p3[i] + b[1][i] for i in range(3))), W(p3))
ws = wmap[eid]; widths = [(F(ws[i]), F(ws[i + 1])) for i in range(len(ws) - 1)]
v = np.array(sections_bob(s, s.optimise(extra=extra), widths), float); b = B[k]['pos'][:, :3].astype(float)
f = B[k]['f']; m = f.lods[0].models[0]
print('model bbox', getattr(m, 'bbox_min', None), getattr(m, 'bbox_max', None))
cand = collections.Counter()
for bi in b:
    for vj in v: cand[tuple(np.round((bi - vj)[[0, 2]], 4))] += 1
oxz = np.array(cand.most_common(1)[0][0]); print('xz offset', oxz)
# pair by xz
pairs = []
for bi in b:
    d = np.abs(v[:, [0, 2]] + oxz - bi[[0, 2]]).sum(1); j = int(np.argmin(d))
    if d[j] < 1e-4: pairs.append((bi[1], v[j, 1]))
pairs = np.array(pairs)
dy = pairs[:, 0] - pairs[:, 1]
print('xz-paired', len(pairs), 'of', len(b), ' dy values (bob y - our half y):', collections.Counter(np.round(dy, 5)).most_common(8))
print('bob y sample', np.round(pairs[:8, 0], 5).tolist()); print('our y sample', np.round(pairs[:8, 1], 5).tolist())
