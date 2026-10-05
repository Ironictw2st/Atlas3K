"""Per river: does the native-prototype vertex multiset (bob_spline.sections_bob, half-quantised) equal BOB's (after
removing the translation)? Reports exact-match rivers and per-river vertex agreement."""
import sys, collections
import numpy as np
import xml.etree.ElementTree as ET
from bob_spline import *
import river_cmp
L = sys.argv[1]; BD = sys.argv[2]
extra = [F(F(k) * F(F(1) / F(8))) for k in range(7)]
rs = sorted(rivers(L), key=lambda r: -int(r[0], 16))
B = river_cmp.summary(BD)
wmap = {}
for ent in ET.parse(L).getroot().iter('entity'):
    sp = ent.find('ECRiverSpline')
    if sp is not None: wmap[ent.get('id')] = [float(p.get('width', '1')) for p in sp.iter('point')]
tot = exact = 0; agree = []
for k, (eid, name, pts, W, step) in enumerate(rs):
    s = Spline()
    for a, b in zip(pts, pts[1:]):
        p0 = a[0]; p3 = b[0]
        s.add(W(p0), W(tuple(p0[i] + a[2][i] for i in range(3))), W(tuple(p3[i] + b[1][i] for i in range(3))), W(p3))
    ws = wmap[eid]; widths = [(F(ws[i]), F(ws[i + 1])) for i in range(len(ws) - 1)]
    v = np.array(sections_bob(s, s.optimise(extra=extra), widths), float)
    b = B[k]['pos'][:, :3].astype(float)
    cand = collections.Counter()
    for bi in b:
        for vj in v: cand[tuple(np.round(bi - vj, 4))] += 1
    off = np.array(cand.most_common(1)[0][0])
    cv = collections.Counter(map(tuple, np.round(v + off, 4))); cb = collections.Counter(map(tuple, np.round(b, 4)))
    common = sum((cv & cb).values()); agree.append(common / max(len(b), 1))
    tot += 1; exact += (cv == cb)
    xz = sum((collections.Counter(map(tuple, np.round((v + off)[:, [0, 2]], 4))) & collections.Counter(map(tuple, np.round(b[:, [0, 2]], 4)))).values())
    print(f"bob river_{k:2d} ({name:9s}) ours {len(v):4d} bob {len(b):4d}  common {common:4d} ({common / len(b):.0%})  xz {xz / len(b):.0%}  {'EXACT' if cv == cb else ''}")
print(f"exact vertex sets: {exact}/{tot}; mean vertex agreement {np.mean(agree):.1%}")
