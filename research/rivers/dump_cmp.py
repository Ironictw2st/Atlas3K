"""Compare the Frida dump of BOB's river splines (frida_rivers.js) with the prototype: per spline, the raw input points
(P0..P3), the stored control points, the segment lengths and the optimise_spline sample list.
usage: dump_cmp.py <frida jsonl>"""
import json, sys, struct
import numpy as np
sys.path.insert(0, '.')
import bob_spline as S
import exact_cmp as E
S.WORLD_F32 = True; S.CTRL_MODE = 'world'
F = np.float32
f32 = lambda h: struct.unpack('<f', struct.pack('<I', int(h, 16)))[0]


def load(path):
    msgs = [json.loads(l) for l in open(path, encoding='utf-8')]
    splines = []; cur = None
    for m in msgs:
        if m['kind'] == 'spline':
            cur = dict(self=m['self'], segs=[], ts=None); splines.append(cur)
        elif m['kind'] == 'seg' and cur is not None:
            cur['segs'].append(dict(inp=[[f32(x) for x in p] for p in m['in']], ctrl=[[f32(x) for x in p] for p in m['ctrl']],
                                    len=f32(m['len']), total=f32(m['total'])))
        elif m['kind'] == 'opt' and cur is not None:
            cur['ts'] = [f32(x) for x in m['ts']]
    return splines


if __name__ == "__main__":
    sp = load(sys.argv[1])
    print(len(sp), 'splines;', [len(s['segs']) for s in sp])
    # match each dumped spline to our river by first input point
    ours = {}
    for k, (eid, name, pts, W, step) in enumerate(E.rs):
        ours[k] = (name, W(pts[0][0]), pts, W)
    tot_in = tot_ctrl = tot_len = tot_seg = 0; ts_eq = 0
    for i, s in enumerate(sp):
        p0 = s['segs'][0]['inp'][0]
        k = min(ours, key=lambda k: sum(abs(float(ours[k][1][j]) - p0[j]) for j in range(3)))
        name, w0, pts, W = ours[k]
        o = S.Spline(); in_eq = ctrl_eq = len_eq = 0
        for j, (a, b) in enumerate(zip(pts, pts[1:])):
            p0_, p3_ = a[0], b[0]
            raw = [W(p0_), E.ctrl(W, p0_, a[2]), E.ctrl(W, p3_, b[1]), W(p3_)]
            o.add(*raw)
            if j < len(s['segs']):
                d = s['segs'][j]
                in_eq += all(F(raw[q][r]) == F(d['inp'][q][r]) for q in range(4) for r in range(3))
                ctrl_eq += all(o.segs[j][q][r] == F(d['ctrl'][q][r]) for q in range(4) for r in range(3))
                len_eq += o.lens[j] == F(d['len'])
        ts = o.optimise(extra=E.extra)
        same_ts = s['ts'] is not None and len(ts) == len(s['ts']) and all(F(x) == F(y) for x, y in zip(ts, s['ts']))
        ts_eq += same_ts
        n = len(s['segs']); tot_seg += n; tot_in += in_eq; tot_ctrl += ctrl_eq; tot_len += len_eq
        print(f"{name:9s} segs {n:3d} raw-in eq {in_eq:3d} ctrl eq {ctrl_eq:3d} len eq {len_eq:3d}  ts ours {len(ts):3d} bob {len(s['ts'] or []):3d} {'TS-EQUAL' if same_ts else ''}")
        if in_eq < n and i < 3:
            j = next(j for j in range(n) if not all(F(([W(pts[j][0]), E.ctrl(W, pts[j][0], pts[j][2]), E.ctrl(W, pts[j + 1][0], pts[j + 1][1]), W(pts[j + 1][0])])[q][r]) == F(s['segs'][j]['inp'][q][r]) for q in range(4) for r in range(3)))
            print('   first raw mismatch seg', j, 'bob', s['segs'][j]['inp'], '\n   ours', [[float(x) for x in p] for p in [W(pts[j][0]), E.ctrl(W, pts[j][0], pts[j][2]), E.ctrl(W, pts[j + 1][0], pts[j + 1][1]), W(pts[j + 1][0])]])
    print(f"segments: raw input eq {tot_in}/{tot_seg}, stored ctrl eq {tot_ctrl}/{tot_seg}, length eq {tot_len}/{tot_seg}; sample lists equal {ts_eq}/{len(sp)}")
