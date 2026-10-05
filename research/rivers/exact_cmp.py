"""Exact comparison per river: ours = half_bob(world) - bbox centre (float32), vs BOB's stored positions.
Lists mismatching sections. usage: exact_cmp.py [river index|all]"""
import sys, collections, numpy as np
sys.path.insert(0, '.')
from bob_spline import *
import river_cmp, xml.etree.ElementTree as ET
L = "C:/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/assembly_kit_190E/raw_data/terrain/campaigns/3k_190e_expanded_map/3k_190e_expanded_map.1972bd217a4938e.layer"
import os
B = river_cmp.summary(os.environ.get("RIVER_REF", r"Z:/Claude/TerryClone/output/bob_runs/frida_rivers_main190_bob_terrain/models"))
rs = sorted(rivers(L), key=lambda r: -int(r[0], 16))
wmap = {}
for ent in ET.parse(L).getroot().iter('entity'):
    sp = ent.find('ECRiverSpline')
    if sp is not None: wmap[ent.get('id')] = [float(p.get('width', '1')) for p in sp.iter('point')]
extra = [F(F(k) * F(F(1) / F(8))) for k in range(7)]
USE_BOB_PIVOT = '--bob-pivot' in sys.argv


def build(k):
    eid, name, pts, W, step = rs[k]; s = Spline()
    for a, b in zip(pts, pts[1:]):
        p0 = a[0]; p3 = b[0]; s.add(W(p0), ctrl(W, p0, a[2]), ctrl(W, p3, b[1]), W(p3))
    ws = wmap[eid]; widths = [(F(ws[i]), F(ws[i + 1])) for i in range(len(ws) - 1)]
    ts = s.optimise(extra=extra)
    v = np.array(sections_bob(s, ts, widths), np.float32)
    c = ((v.min(0) + v.max(0)) * np.float32(0.5)).astype(np.float32)
    if USE_BOB_PIVOT:
        m = B[[bk for bk, kk in pairing().items() if kk == k][0]]['f'].lods[0].models[0]
        c = ((np.array(m.bbox_min, np.float32) + np.array(m.bbox_max, np.float32)) * np.float32(0.5)).astype(np.float32)
    return name, ts, (v - c).astype(np.float32)


PAIR = None


def pairing():
    """BOB river index -> our river index by exact world bounding box (BOB's numbering is not plain id order)."""
    global PAIR
    if PAIR is None:
        boxes = {}
        for k in range(len(rs)):
            name, ts, v = build_world(k); boxes[k] = (v.min(0), v.max(0))
        PAIR = {}
        for bk in B:
            m = B[bk]['f'].lods[0].models[0]
            PAIR[bk] = min(boxes, key=lambda k: np.abs(boxes[k][0] - np.array(m.bbox_min)).sum() + np.abs(boxes[k][1] - np.array(m.bbox_max)).sum())
    return PAIR


def ctrl(W, p, t):
    import bob_spline as S
    if S.CTRL_MODE == 'world':
        w = W(p); return tuple(F(F(w[i]) + F(t[i])) for i in range(3))
    if S.CTRL_MODE == 'localf32':
        return W(tuple(F(F(p[i]) + F(t[i])) for i in range(3)))
    return W(tuple(p[i] + t[i] for i in range(3)))


def build_world(k):
    eid, name, pts, W, step = rs[k]; s = Spline()
    for a, b in zip(pts, pts[1:]):
        p0 = a[0]; p3 = b[0]; s.add(W(p0), ctrl(W, p0, a[2]), ctrl(W, p3, b[1]), W(p3))
    ws = wmap[eid]; widths = [(F(ws[i]), F(ws[i + 1])) for i in range(len(ws) - 1)]
    ts = s.optimise(extra=extra)
    return name, ts, np.array(sections_bob(s, ts, widths), np.float32)


def compare(bk, verbose=False):
    k = pairing()[bk]
    name, ts, v = build(k); b = B[bk]['pos'][:, :3].astype(np.float32)
    cv = collections.Counter(map(tuple, v.tolist())); cb = collections.Counter(map(tuple, b.tolist()))
    common = sum((cv & cb).values())
    if verbose:
        miss = [i for i, p in enumerate(v.tolist()) if cb[tuple(p)] == 0]
        secs = sorted(set(i // 5 for i in miss))
        print(f"{name}: sections {len(ts)}, mismatching sections {secs[:30]}")
        bset = b.tolist()
        for sidx in secs[:6]:
            ours = v[sidx * 5:(sidx + 1) * 5]
            near = [min(bset, key=lambda q: abs(q[0] - o[0]) + abs(q[2] - o[2])) for o in ours.tolist()]
            print(f"  t={float(ts[sidx]):.6f} ours {np.round(ours, 4).tolist()}\n           bob  {np.round(near, 4).tolist()}")
    return name, len(v), len(b), common, cv == cb


if __name__ == "__main__":
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    a = args[0] if args else "all"
    if a == "all":
        tot = 0; ex = 0; agree = []
        for k in range(len(rs)):
            name, nv, nb, common, same = compare(k)
            print(f"bob river_{k:2d} {name:9s} ours {nv:4d} bob {nb:4d} exact-common {common:4d} ({common / nb:.0%}) {'EXACT' if same else ''}")
            tot += 1; ex += same; agree.append(common / nb)
        print(f"exact vertex sets {ex}/{tot}; mean exact vertex agreement {np.mean(agree):.1%}")
    else:
        compare(int(a), verbose=True)
