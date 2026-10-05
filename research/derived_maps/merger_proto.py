"""Prototype of BOB's global land mesh surface pipeline (see docs/bob_re_global_mesh.md), checked against vanilla.

Hole grid: rebuilt from vanilla's own quad coverage (tile-coverage semantics come later).
Run: python merger_proto.py <mesh index>
"""
import math
import struct
import sys
import time

import numpy as np

f32 = np.float32
V = r"Z:\Claude\TerryClone\Vanilla\Map\terrain\campaigns\3k_dlc07_main_map"
N = 224
EXTENT = f32(595.1)
TOTAL = 3568                     # 2 * max(tiles)
CELL = EXTENT / f32(TOTAL)
HOLE = f32(-20.0)
NZ_SCALE = 8.0
TRACE = None


def read_mesh(n):
    b = open(fr"{V}\global_meshes\land_mesh_{n}.rigid_model_v2", 'rb').read()
    vc, = struct.unpack_from('<I', b, 0xB4)
    io, ic = struct.unpack_from('<II', b, 0xB8)
    bb = struct.unpack_from('<6f', b, 0xC0)
    v = np.frombuffer(b, '<f4', count=vc * 4, offset=0x150).reshape(-1, 4)[:, :3].copy()
    idx = np.frombuffer(b, '<u2', count=ic, offset=0xA8 + io).reshape(-1, 3).copy()
    return v, idx, bb


def global_validity():
    """Vertex validity over the whole map: vanilla land_mesh_N.compressed_map value 0 = hole."""
    import glob, re
    sys.path.insert(0, r"Z:\Claude\TerryClone\research")
    import compressed_map as cmap
    valid = np.zeros((TOTAL + 1, TOTAL + 1), bool)
    for f in glob.glob(V + r"\global_meshes\land_mesh_*.compressed_map"):
        n = int(re.search(r'_(\d+)\.compressed', f).group(1))
        v, idx, bb = read_mesh(n)
        tc, tr = int(round(bb[0] / (223 * float(CELL)))), int(round(bb[2] / (223 * float(CELL))))
        r, hdr = cmap.decode(f)
        sub = valid[tr * 223:tr * 223 + 224, tc * 223:tc * 223 + 224]
        sub |= (r != 0)[:sub.shape[0], :sub.shape[1]]
    return valid


def global_validity_from_coverage():
    """Vertex validity over the whole map from vanilla quad coverage of every land mesh."""
    import glob, re
    valid = np.zeros((TOTAL + 1, TOTAL + 1), bool)
    for f in glob.glob(V + r"\global_meshes\land_mesh_*.rigid_model_v2"):
        n = int(re.search(r'_(\d+)\.rigid', f).group(1))
        v, idx, bb = read_mesh(n)
        gi = np.round(v[:, 0] / CELL).astype(int)
        gj = np.round(v[:, 2] / CELL).astype(int)
        p = v[idx].astype(np.float64)
        area = (p[:, 1, 0] - p[:, 0, 0]) * (p[:, 2, 2] - p[:, 0, 2]) - (p[:, 2, 0] - p[:, 0, 0]) * (p[:, 1, 2] - p[:, 0, 2])
        for t in idx[np.abs(area) > 1e-9]:
            xs, zs = gi[t], gj[t]
            valid[zs.min():zs.max() + 1, xs.min():xs.max() + 1] |= True   # conservative: bbox of the triangle
    return valid


def lf_heights():
    L = np.frombuffer(open(V + r"\lf_height_map.dds", 'rb').read(), '<u2', offset=128, count=7136 * 5620).reshape(5620, 7136)
    return L.astype(np.float32) * f32(0.000218712) - f32(3.12725)


def bilinear(L, x, z):
    px = 595.1 / 7136
    col = x / px
    row = 5619 - z / px
    c0 = min(max(int(math.floor(col)), 0), 7134); r0 = min(max(int(math.floor(row)), 0), 5618)
    fc = col - c0; fr = row - r0
    return f32((L[r0, c0] * (1 - fc) + L[r0, c0 + 1] * fc) * (1 - fr) + (L[r0 + 1, c0] * (1 - fc) + L[r0 + 1, c0 + 1] * fc) * fr)


def build(tc, tr, L, valid):
    xs = np.zeros(N * N, f32); ys = np.zeros(N * N, f32); zs = np.zeros(N * N, f32)
    flags = np.zeros(N * N, np.uint8)
    offx, offz = f32(223 * tc), f32(223 * tr)
    def ok(I, J):
        return bool(0 <= I <= TOTAL and 0 <= J <= TOTAL and valid[J, I])
    for j in range(N):
        for i in range(N):
            k = j * N + i
            x = f32((i + 223 * tc) * float(EXTENT) / TOTAL); z = f32((j + 223 * tr) * float(EXTENT) / TOTAL)   # BOB: double
            xs[k], zs[k] = x, z
            I, J = 223 * tc + i, 223 * tr + j
            if not ok(I, J):
                ys[k] = HOLE; flags[k] = 2; continue
            ys[k] = bilinear(L, float(x), float(z))
            f = 2 if all(ok(I + di, J + dj) for di in (-1, 0, 1) for dj in (-1, 0, 1) if di or dj) else 0
            if i in (0, N - 1) or j in (0, N - 1):
                cnt = ok(I, J - 1) + ok(I, J + 1) + ok(I - 1, J) + ok(I + 1, J)
                f = 0
                if cnt == 3:
                    onx = i in (0, N - 1)
                    if ((j != 0 and j != N - 1) or (i & 31) != 0) and (not onx or (j & 31) != 0):
                        f = 3
            flags[k] = f
    # Sobel normals, clamped indices
    H = ys.reshape(N, N)
    K = [[1, 0, -1], [2, 0, -2], [1, 0, -1]]
    nrm = np.zeros((N * N, 3), f32)
    for j in range(N):
        for i in range(N):
            gx = f32(0); gy = f32(0)
            for r in range(3):
                for c in range(3):
                    jj = min(max(j + r - 1, 0), N - 1); ii = min(max(i + c - 1, 0), N - 1)
                    gx = f32(gx + f32(f32(1.0) * H[jj, ii]) * f32(K[r][c]))
                    jj2 = min(max(j + c - 1, 0), N - 1); ii2 = min(max(i + r - 1, 0), N - 1)
                    gy = f32(gy + f32(f32(1.0) * H[jj2, ii2]) * f32(K[r][c]))
            gx = f32(gx / f32(8.0)); gy = f32(gy / f32(8.0))      # kernel sum divided by (k*k - 1)
            s = f32(f32(1.0) / f32(0.33))
            inv = f32(f32(1.0) / f32(np.sqrt(f32(f32(gx * gx + gy * gy) + s * s))))
            nrm[j * N + i] = (gx * inv, gy * inv, s * inv)
    tris = []
    for j in range(N - 1):
        for i in range(N - 1):
            a = j * N + i; b = a + 1; c = a + N; d = c + 1
            if HOLE in (ys[a], ys[b], ys[c], ys[d]):
                continue
            tris.append([a, c, b]); tris.append([c, d, b])
    return xs, ys, zs, flags, nrm, tris


def merge(xs, ys, zs, flags, nrm, tris, factor, span=64.0, tol=3.4028235e38):
    iters = min(int(span * (1.0 / 6.0)), 50)
    step = f32(span) / f32(iters)
    nv = len(xs)
    cur = [t[:] for t in tris]
    def degen(t): return t[0] == t[1] or t[0] == t[2] or t[1] == t[2]
    def collinear(a, b, c):
        if a == b or a == c or b == c: return False
        if (zs[a] == zs[b] and zs[b] == zs[c]) or (xs[a] == xs[b] and xs[b] == xs[c]): return True
        cx = xs[c] - xs[a]; cz = zs[c] - zs[a]; bx = xs[b] - xs[a]; bz = zs[b] - zs[a]
        lac = cz * cz + cx * cx; lab = bz * bz + bx * bx
        if lac == 0 or lab == 0: return True
        il_ab = f32(1) / f32(math.sqrt(lab)); il_ac = f32(1) / f32(math.sqrt(lac))
        return abs(f32(il_ac * cx * bz * il_ab - il_ac * cz * bx * il_ab)) < f32(0.1)
    def bad_shape(a, b, c, L2):
        if a == b or a == c or b == c: return False
        abx = xs[b] - xs[a]; abz = zs[b] - zs[a]
        acx = xs[c] - xs[a]; acz = zs[c] - zs[a]
        bcx = xs[c] - xs[b]; bcz = zs[c] - zs[b]
        if abz * abz + abx * abx <= L2 and acz * acz + acx * acx <= L2 and bcx * bcx + bcz * bcz <= L2:
            if (zs[c] - zs[a]) * (xs[b] - xs[a]) - (zs[b] - zs[a]) * (xs[c] - xs[a]) <= 0:
                return False
        return True
    stall = 0; k = 0; mult = 1
    while k < iters:
        L = f32(mult) * step; L2 = L * L
        tri = [t[:] for t in cur]
        adj = [[] for _ in range(nv)]
        for ti, t in enumerate(tri):
            for c in t: adj[c].append(ti)
        for v in range(nv):
            if flags[v] < 2: continue
            # removable?
            okv = True
            for ti in adj[v]:
                t = tri[ti]
                if degen(t): continue
                if t[0] == v: o = (t[1], t[2])
                elif t[1] == v: o = (t[0], t[2])
                elif t[2] == v: o = (t[0], t[1])
                else: continue
                for w in o:
                    dot = abs(f32(nrm[v, 1] * nrm[w, 1] + nrm[v, 0] * nrm[w, 0] + nrm[v, 2] * nrm[w, 2]))
                    if dot < factor: okv = False; break
                    if flags[v] != 4 and flags[w] not in (1, 4) and abs(ys[w] - ys[v]) > tol: okv = False; break
                if not okv: break
            if not okv: continue
            # candidates
            cands = []
            for ti in adj[v]:
                t = tri[ti]
                if degen(t): continue
                for w in t:
                    if w != v and can_collapse(v, w, tri, adj, flags, degen, collinear, bad_shape, L2):
                        cands.append(w)
            if not cands: continue
            vx, vz = xs[v], zs[v]
            key = lambda w: f32((zs[w] - vz) * (zs[w] - vz) + (xs[w] - vx) * (xs[w] - vx))
            if len(cands) > 32:
                print('  note: >32 candidates, introsort not modelled', len(cands))
            cands.sort(key=key)   # stable, like MSVC insertion sort for <= 32
            w = cands[0]
            if TRACE is not None: TRACE.append((k, v, w, [int(c) for c in cands]))
            adj[w].extend(adj[v]); adj[v] = []
            for ti in adj[w]:
                t = tri[ti]
                for q in range(3):
                    if t[q] == v: t[q] = w
                if degen(t): tri[ti] = [0, 0, 0]
        new = [t for t in tri if not degen(t)]
        if len(new) == len(cur):
            stall += 1
            if stall > 3:
                k += 10; stall = 0; mult += 10
        cur = new
        k += 1; mult += 1
        print(f'  iteration done, L={L:.1f}, triangles {len(cur)}')
    return cur


def can_collapse(v, w, tri, adj, flags, degen, collinear, bad_shape, L2):
    fv, fw = flags[v], flags[w]
    if fv == 0: return False
    if fv == 3 and fw not in (3, 0): return False
    if fv == 4 and fw not in (4, 1): return False
    for u in (v, w):
        for ti in adj[u]:
            t = tri[ti]
            if degen(t): continue
            a, b, c = [w if q == v else q for q in t]
            if fw > 1 and (a == b or a == c or b == c):
                if min(flags[a], flags[b], flags[c]) < 2:
                    return False
            if collinear(a, b, c) or bad_shape(a, b, c, L2):
                return False
    return True


if __name__ == '__main__':
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    v_ref, idx_ref, bb = read_mesh(n)
    tc, tr = int(round(bb[0] / (223 * float(CELL)))), int(round(bb[2] / (223 * float(CELL))))
    t0 = time.time()
    valid = global_validity_from_coverage()
    L = lf_heights()
    xs, ys, zs, flags, nrm, tris = build(tc, tr, L, valid)
    print(f'mesh {n} tile ({tc},{tr}): {len(tris)} triangles in, flags', np.bincount(flags).tolist(), f'{time.time() - t0:.0f}s')
    factor = f32(0.9999)
    out = merge(xs, ys, zs, flags, nrm, tris, factor)
    out = [[t[1], t[0], t[2]] for t in out]
    remap = {}
    idx = []
    for t in out:
        for q in t:
            if q not in remap: remap[q] = len(remap)
            idx.append(remap[q])
    order = sorted(remap, key=remap.get)
    verts = np.stack([xs[order], ys[order], zs[order]], 1)
    p = v_ref[idx_ref].astype(np.float64)
    area = (p[:, 1, 0] - p[:, 0, 0]) * (p[:, 2, 2] - p[:, 0, 2]) - (p[:, 2, 0] - p[:, 0, 0]) * (p[:, 1, 2] - p[:, 0, 2])
    nsurf = int((np.abs(area) > 1e-9).sum())
    ref_idx = idx_ref[:nsurf].ravel().tolist()
    nref_v = max(ref_idx) + 1
    print(f'ours: {len(out)} tris, {len(order)} verts | vanilla surface: {nsurf} tris, {nref_v} verts')
    same_idx = idx == ref_idx
    print('index list identical:', same_idx)
    if not same_idx:
        first = next((i for i, (a, b) in enumerate(zip(idx, ref_idx)) if a != b), min(len(idx), len(ref_idx)))
        print('first index difference at', first, 'tri', first // 3, 'ours', idx[first - first % 3:first - first % 3 + 6], 'vanilla', ref_idx[first - first % 3:first - first % 3 + 6])
    nv = min(len(order), nref_v)
    dv = np.abs(verts[:nv] - v_ref[:nv])
    print('vertex positions identical (first %d):' % nv, bool((dv == 0).all()), 'max diff', dv.max())
    bad = np.nonzero((dv != 0).any(1))[0]
    if len(bad):
        k = bad[0]
        print('first vertex difference at', k, 'ours', verts[k].tolist(), 'vanilla', v_ref[k].tolist())
        ydiff = np.nonzero(verts[:nv, 1] != v_ref[:nv, 1])[0]
        xz_same = (verts[:nv, 0] == v_ref[:nv, 0]) & (verts[:nv, 2] == v_ref[:nv, 2])
        print('vertices with same x/z but different y:', int((xz_same & (verts[:nv, 1] != v_ref[:nv, 1])).sum()), 'of', int(xz_same.sum()), 'same-x/z vertices')
