import sys, itertools, math
import numpy as np
sys.path.insert(0, '.')
import bob_spline as S, exact_cmp as E
F = np.float32
B = [[-1, 3, -3, 1], [3, -6, 3, 0], [-3, 3, 0, 0], [1, 0, 0, 0]]


def wts(U, mode):
    if mode == 'left': return [F(F(F(F(U[0] * F(B[r][0])) + F(U[1] * F(B[r][1]))) + F(U[2] * F(B[r][2]))) + F(U[3] * F(B[r][3]))) for r in range(4)]
    return [F(F(F(F(U[3] * F(B[r][3])) + F(U[2] * F(B[r][2]))) + F(U[1] * F(B[r][1]))) + F(U[0] * F(B[r][0]))) for r in range(4)]


def psum(w, P, k, order):
    idx = (0, 1, 2, 3) if order == 'fwd' else (3, 2, 1, 0)
    t = [F(w[i] * P[i][k]) for i in idx]
    return F(F(F(t[0] + t[1]) + t[2]) + t[3])


def mk(pos_order, der_order, wmode):
    def ev(P, u):
        u = F(u); u2 = F(u * u); u3 = F(u * u2)
        w = wts([u3, u2, u, F(1)], wmode); return [psum(w, P, k, pos_order) for k in range(3)]
    def de(P, u):
        u = F(u); w = wts([F(F(u * F(3)) * u), F(u + u), F(1), F(0)], wmode); return [psum(w, P, k, der_order) for k in range(3)]
    return ev, de


fwd0, der0 = S.eval_seg_fwd, S.deriv_seg
for po, do, wm in itertools.product(('fwd', 'rev'), ('fwd', 'rev'), ('left', 'rev')):
    ev, de = mk(po, do, wm)
    S.eval_seg_fwd = ev; S.deriv_seg = de
    # keep the length integration on the verified derivative: only sections change
    import importlib
    ag = []
    for bk in range(24):
        name, nv, nb, common, same = E.compare(bk); ag.append(common / nb)
    print(f"section pos {po} deriv {do} weights {wm}: mean exact vertices {np.mean(ag):.1%}", flush=True)
    S.eval_seg_fwd = fwd0; S.deriv_seg = der0
