"""BOB's river mesh tail on top of the prototype sections: triangles per section pair
(n_j, c_j, n_j+1), (c_j, c_j+1, n_j+1); drop degenerate triangles (rule selectable); renumber vertices by first use;
pivot = bbox centre. Compares vertex list (ordered) and index list with BOB. usage: mesh_tail.py [bob river idx|all] [rule]"""
import sys, collections, numpy as np
sys.path.insert(0, '.')
import exact_cmp as E
import bob_spline as S
S.WORLD_F32 = True; S.CTRL_MODE = 'world'
F = np.float32


def tail(v, rule):
    n = len(v) // 5; tris = []
    for s in range(n - 1):
        c, nx = 5 * s, 5 * (s + 1)
        for j in range(4):
            tris += [(nx + j, c + j, nx + j + 1), (c + j, c + j + 1, nx + j + 1)]
    def degen(t):
        a, b, c = (v[i] for i in t)
        if rule == 'none': return False
        if rule == 'samepos': return tuple(a) == tuple(b) or tuple(b) == tuple(c) or tuple(a) == tuple(c)
        if rule == 'area':
            ab = b - a; ac = c - a; cr = np.cross(ab.astype(np.float32), ac.astype(np.float32)); return float(np.dot(cr, cr)) == 0.0
        if rule == 'area_xz':
            return float((b[0] - a[0]) * (c[2] - a[2]) - (b[2] - a[2]) * (c[0] - a[0])) == 0.0
    tris = [t for t in tris if not degen(t)]
    remap = {}; order = []
    for t in tris:
        for i in t:
            if i not in remap: remap[i] = len(order); order.append(i)
    vv = v[order]
    c = ((vv.min(0) + vv.max(0)) * F(0.5)).astype(F)
    return (vv - c).astype(F), np.array([remap[i] for t in tris for i in (t[0], t[2], t[1])])   # written with flipped winding


def run(bk, rule, verbose=False):
    k = E.pairing()[bk]
    name, ts, v = E.build_world(k)
    pos, idx = tail(v, rule)
    bp = E.B[bk]['partsraw'][0][0][:, :3].astype(F); bi = E.B[bk]['partsraw'][0][1]
    same_v = len(pos) == len(bp) and np.array_equal(pos, bp)
    same_i = len(idx) == len(bi) and np.array_equal(idx, bi)
    pos_eq = (len(pos) == len(bp)) and float((pos == bp).all(1).mean())
    if verbose: print(f"{name}: verts ours {len(pos)} bob {len(bp)}; idx ours {len(idx)} bob {len(bi)}; ordered vertex equality {pos_eq}; idx equal {same_i}")
    return name, len(pos), len(bp), len(idx), len(bi), same_v, same_i, pos_eq


if __name__ == "__main__":
    a = sys.argv[1] if len(sys.argv) > 1 else 'all'; rule = sys.argv[2] if len(sys.argv) > 2 else 'area'
    if a != 'all': run(int(a), rule, True); sys.exit()
    cv = ci = cnt = 0; eq = []
    for bk in range(24):
        name, nv, nb, ni, nbi, sv, si, pe = run(bk, rule)
        cv += sv; ci += si; cnt += (nv == nb and ni == nbi); eq.append(pe if pe else 0)
        print(f"bob river_{bk:2d} {name:9s} v {nv:4d}/{nb:4d} i {ni:5d}/{nbi:5d} ordered-vertex-eq {pe if pe is not False else '-'} {'VERTS' if sv else ''} {'IDX' if si else ''}")
    print(f"rule={rule}: counts equal {cnt}/24, vertex lists identical {cv}/24, index lists identical {ci}/24")
