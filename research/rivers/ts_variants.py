"""Try evaluator summation orders in optimise_spline until the sample lists equal BOB's (Frida dump)."""
import sys, math, itertools
import numpy as np
sys.path.insert(0, '.')
import bob_spline as S, dump_cmp as D, exact_cmp as E
S.WORLD_F32 = True; S.CTRL_MODE = 'world'
F = np.float32
B = [[-1, 3, -3, 1], [3, -6, 3, 0], [-3, 3, 0, 0], [1, 0, 0, 0]]
sp = D.load('../bob_re/frida_out/frida_rivers_main190.jsonl')


def s4(a, b, c, d, mode):
    if mode == 'left': return F(F(F(a + b) + c) + d)
    if mode == 'pair': return F(F(a + b) + F(c + d))
    if mode == 'right': return F(a + F(b + F(c + d)))
    if mode == 'pair2': return F(F(a + c) + F(b + d))


def make_eval(wmode, pmode, porder):
    def ev(P, u):
        u = F(u); u2 = F(u * u); u3 = F(u2 * u); U = [u3, u2, u, F(1)]
        w = [s4(*(F(U[c] * F(B[r][c])) for c in range(4)), wmode) for r in range(4)]
        out = []
        for k in range(3):
            terms = [F(w[i] * P[i][k]) for i in porder]
            out.append(s4(*terms, pmode))
        return out
    return ev


rivers = []
for s in sp:
    p0 = s['segs'][0]['inp'][0]
    k = min(range(len(E.rs)), key=lambda k: sum(abs(float(E.rs[k][3](E.rs[k][2][0][0])[j]) - p0[j]) for j in range(3)))
    eid, name, pts, W, step = E.rs[k]; o = S.Spline()
    for a, b in zip(pts, pts[1:]): o.add(W(a[0]), E.ctrl(W, a[0], a[2]), E.ctrl(W, b[0], b[1]), W(b[0]))
    rivers.append((name, o, [F(x) for x in s['ts']]))

orig = S.eval_seg
for wmode, pmode, porder in itertools.product(('left', 'pair', 'right', 'pair2'), ('left', 'pair', 'right', 'pair2'), ((3, 2, 1, 0), (0, 1, 2, 3))):
    S.eval_seg = make_eval(wmode, pmode, porder)
    eq = 0
    for name, o, bt in rivers:
        ts = o.optimise(extra=E.extra)
        eq += len(ts) == len(bt) and all(x == y for x, y in zip(ts, bt))
    print(f"weights {wmode:5s} positions {pmode:5s} order {porder}: sample lists equal {eq}/24", flush=True)
S.eval_seg = orig
