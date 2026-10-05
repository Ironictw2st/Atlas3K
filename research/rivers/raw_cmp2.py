"""raw_cmp with the bob_mesh passes: positions, normal/tangent/bitangent bytes and indices vs the Frida dump of
FUN_18015e9e0 (frida_rivers2.js). usage: raw_cmp2.py [jsonl] [dump index]"""
import sys, numpy as np
sys.path.insert(0, '.')
import exact_cmp as E, bob_mesh as M
from raw_cmp import load
BOUNDS = (0.0, 0.0, 986.0509643554688, 873.79541015625)   # main190 map_data.esf header


def spl(k):
    eid, name, pts, W, step = E.rs[k]; s = E.Spline()
    for a, b in zip(pts, pts[1:]):
        p0 = a[0]; p3 = b[0]; s.add(W(p0), E.ctrl(W, p0, a[2]), E.ctrl(W, p3, b[1]), W(p3))
    ws = E.wmap[eid]; widths = [(E.F(ws[i]), E.F(ws[i + 1])) for i in range(len(ws) - 1)]
    return name, s, s.optimise(extra=E.extra), widths


def match(D):
    worlds = {k: E.build_world(k) for k in range(len(E.rs))}
    out = []
    for d in D:
        p = d['h'][:, :3]
        out.append(min(worlds, key=lambda k: np.abs(worlds[k][2].min(0) - p.min(0)).sum() + np.abs(worlds[k][2].max(0) - p.max(0)).sum()))
    return out


if __name__ == "__main__":
    D = load(sys.argv[1] if len(sys.argv) > 1 else '../bob_re/frida_out/frida_rivers2_main190.jsonl')
    only = int(sys.argv[2]) if len(sys.argv) > 2 else None
    T = dict(pos=0, n=0, nb=0, v=0, idx=0)
    for i, (d, k) in enumerate(zip(D, match(D))):
        if only is not None and i != only: continue
        name, s, ts, widths = spl(k)
        sec, H, nb, idx, mine = M.build(s, ts, widths, BOUNDS)
        raw = d['raw']; rh = raw[:, :6].copy().view(np.uint16)
        pe = int((rh == H).all(1).sum()); ne = int((raw[:, 16:28] == nb).all(1).sum())
        fe = int((raw == mine).all(1).sum()); T['full'] = T.get('full', 0) + fe
        ie = len(idx) == len(d['idx']) and list(d['idx']) == idx
        T['pos'] += pe; T['v'] += len(H); T['nb'] += ne; T['idx'] += ie; T['n'] += 1
        print(f"dump {i:2d} {name:9s} verts {len(H):4d} pos-eq {pe:4d} nbt-eq {ne:4d} full32-eq {fe:4d} idx {len(idx):4d}/{len(d['idx']):4d} {'IDX-EQUAL' if ie else ''}", flush=True)
    print(f"positions {T['pos']}/{T['v']} = {T['pos']/T['v']:.2%}; normal/tangent/bitangent bytes {T['nb']}/{T['v']} = {T['nb']/T['v']:.2%}; index lists {T['idx']}/{T['n']}; full 32-byte vertices {T['full']}/{T['v']}")
