"""Why does the prototype stop merging? Count rejection reasons in the first pass over land_mesh_0."""
from collections import Counter

import numpy as np

import merger_proto as M

v_ref, idx_ref, bb = M.read_mesh(0)
valid = M.global_validity()
L = M.lf_heights()
xs, ys, zs, flags, nrm, tris = M.build(0, 0, L, valid)
f32 = np.float32
factor = f32(0.9999)
L2 = f32(6.4) * f32(6.4)
tri = [t[:] for t in tris]
adj = [[] for _ in range(len(xs))]
for ti, t in enumerate(tri):
    for c in t:
        adj[c].append(ti)
degen = lambda t: t[0] == t[1] or t[0] == t[2] or t[1] == t[2]
reasons = Counter()
cand_reasons = Counter()
for v in range(len(xs)):
    if flags[v] < 2:
        reasons['flag<2'] += 1
        continue
    okv = True
    for ti in adj[v]:
        t = tri[ti]
        if degen(t):
            continue
        o = [q for q in t if q != v]
        for w in o:
            if abs(f32(nrm[v] @ nrm[w])) < factor:
                okv = False
    if not okv:
        reasons['normal'] += 1
        continue
    got = False
    for ti in adj[v]:
        t = tri[ti]
        if degen(t):
            continue
        for w in t:
            if w == v:
                continue
            why = None
            for u in (v, w):
                for tj in adj[u]:
                    tt = tri[tj]
                    if degen(tt):
                        continue
                    a, b, c = [w if q == v else q for q in tt]
                    if flags[w] > 1 and (a == b or a == c or b == c) and min(flags[a], flags[b], flags[c]) < 2:
                        why = why or 'degenerate-near-fixed'
                    elif not (a == b or a == c or b == c):
                        cx = xs[c] - xs[a]; cz = zs[c] - zs[a]; bx = xs[b] - xs[a]; bz = zs[b] - zs[a]
                        cross = cz * bx - bz * cx
                        if cross > 0:
                            why = why or 'orientation'
            cand_reasons[why or 'ok'] += 1
            got = got or why is None
    reasons['collapsible' if got else 'no-candidate'] += 1
print(reasons)
print(cand_reasons)
# winding of the initial triangles in x/z
t = tris[0]
cx = xs[t[2]] - xs[t[0]]; cz = zs[t[2]] - zs[t[0]]; bx = xs[t[1]] - xs[t[0]]; bz = zs[t[1]] - zs[t[0]]
print('initial tri', t, 'orientation cross (c.z-a.z)*(b.x-a.x)-(b.z-a.z)*(c.x-a.x) =', cz * bx - bz * cx)
