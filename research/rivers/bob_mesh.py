"""BOB's river mesh generator FUN_18015e9e0 (tooldatabuilder) after the cross-sections: index list, the in-place
'snap' pass (every vertex inside a triangle's xz is moved onto that triangle's nearest corner, WARSCAPE::contains),
face-normal accumulation, the normal/tangent/bitangent bytes and the removal of triangles touching a vertex whose
encoded normal y byte is < 0x82. Produces the raw 32-byte vertices + indices that frida_rivers2.js dumps."""
import math, numpy as np
import bob_spline as S
F = np.float32
FMAX = F(3.4028234663852886e+38)


def half_bits(x):
    return int(np.array([S.half_bob(x)], np.float16).view(np.uint16)[0])


def sections(s, ts, widths):
    """Per vertex: (x, y, z) float before quantisation, the float derivative (tangent, unnormalised), offset, t."""
    out = []
    for t in ts:
        t = F(t); acc = F(0); i = len(s.segs) - 1
        for k, L in enumerate(s.lens):
            ok = acc <= t; acc = F(F(F(1) / s.total) * L + acc)
            if ok and t <= acc: i = k; break
        u = F(F(F(s.total * t) - s.starts[i]) / s.lens[i])
        uc = min(max(u, F(0)), F(1))
        w = F(F(F(widths[i][1] - widths[i][0]) * uc) + widths[i][0])
        p = S.eval_seg_fwd(s.segs[i], u)
        d = S.deriv_seg(s.segs[i], u)
        l2 = F(F(d[2] * d[2]) + F(d[0] * d[0]))
        dx, dz = d[0], d[2]
        if l2 > 0: inv = F(F(1) / F(math.sqrt(l2))); dx = F(d[0] * inv); dz = F(inv * d[2])
        o0 = F(w * F(-0.5)); span = F(F(w * F(0.5)) - o0)
        for j in range(5):
            off = F(F(F(F(j) * F(0.25)) * span) + o0)
            x = F(F(dz * off) + p[0]); z = F(F(-F(dx * off)) + p[2])
            out.append(dict(x=x, y=F(p[1]), z=z, tan=tuple(F(c) for c in d), off=off, t=t))
    return out


def indices(n_sections):
    idx = []
    for s in range(n_sections - 1):
        for j in range(4):
            u = 5 * s + 6 + j
            idx += [u - 1, u - 6, u, u - 6, u - 5, u]
    return idx


def contains(px, py, a, b, c):
    """WARSCAPE::contains(P, A, B, C) on VECTOR_2 (x, z): crossing test, float32 in BOB's operation order."""
    (ax, ay), (bx, by), (cx, cy) = a, b, c
    r = False
    if (py <= ay) != (py <= cy):
        r = bool(px <= F(F(F(F(py - ay) * F(cx - ax)) / F(cy - ay)) + ax))
    if ((py <= by) != (py <= ay)) and px <= F(F(F(F(py - by) * F(ax - bx)) / F(ay - by)) + bx):
        r = not r
    if ((py <= cy) != (py <= by)) and px <= F(F(F(F(bx - cx) * F(py - cy)) / F(by - cy)) + cx):
        r = not r
    return r


def dist(px, pz, q):
    return F(math.sqrt(F(F(F(pz - q[2]) * F(pz - q[2])) + F(F(px - q[0]) * F(px - q[0])))))


def build(s, ts, widths, bounds=None):
    """bounds = (min x, min z, max x, max z) of the map (map_data.esf header) for the world uv; returns (sections,
    position halves [n,3], normal/tangent/bitangent bytes [n,12], indices, raw 32-byte vertices or None)."""
    sec = sections(s, ts, widths)
    n = len(sec)
    H = np.array([[half_bits(v['x']), half_bits(v['y']), half_bits(v['z'])] for v in sec], np.uint16)
    hf = lambda i: H[i].view(np.float16).astype(np.float32)
    idx = indices(len(ts))
    for q in range(0, len(idx), 3):                         # snap pass (in place, sequential)
        src = idx[q:q + 3]
        A, Bv, C = (hf(i) for i in src)
        a2, b2, c2 = (A[0], A[2]), (Bv[0], Bv[2]), (C[0], C[2])
        for v in range(n):
            if v in src: continue
            P = hf(v); px, pz = P[0], P[2]
            if contains(px, pz, a2, b2, c2):
                d0 = dist(px, pz, A); sel = 0
                if FMAX <= d0: sel = -1; d0 = FMAX
                d1 = dist(px, pz, Bv); m = d1; s17 = 1
                if d0 <= d1: m = d0; s17 = sel
                k = 2
                if m <= dist(px, pz, C): k = s17
                H[v] = H[src[k]]
    acc = np.zeros((n, 3), np.float32)
    for q in range(0, len(idx), 3):                         # face normals
        ia, ib, ic = idx[q:q + 3]
        (xa, ya, za), (xb, yb, zb), (xc, yc, zc) = hf(ia), hf(ib), hf(ic)
        nx = F(F(F(zb - za) * F(yc - ya)) - F(F(yb - ya) * F(zc - za)))
        nz = F(F(F(xc - xa) * F(yb - ya)) - F(F(xb - xa) * F(yc - ya)))
        ny = F(F(F(xb - xa) * F(zc - za)) - F(F(xc - xa) * F(zb - za)))
        l = F(F(F(ny * ny) + F(nx * nx)) + F(nz * nz))
        if l <= 0: nrm = (F(0), F(1), F(0))
        else:
            r = F(F(1) / F(math.sqrt(l))); nrm = (F(r * nx), F(r * ny), F(r * nz))
        if nrm[1] != 0:
            for i in (ia, ib, ic):
                acc[i] = (F(acc[i][0] + nrm[0]), F(nrm[1] + acc[i][1]), F(nrm[2] + acc[i][2]))
    nb = np.zeros((n, 12), np.uint8)
    e = lambda v: int(F(F(F(v * F(0.5)) * F(255)) + F(127.5))) & 0xff
    t1 = lambda v: int(F(F(v + F(1)) * F(127.5))) & 0xff
    for i in range(n):
        x, y, z = acc[i]
        l = F(F(F(x * x) + F(y * y)) + F(z * z))
        if l <= 0: nx, ny, nz = F(0), F(1), F(0)
        else:
            r = F(F(1) / F(math.sqrt(l))); nx, ny, nz = F(x * r), F(y * r), F(z * r)
        tx, ty, tz = sec[i]['tan']
        r = F(F(1) / F(math.sqrt(F(F(F(ty * ty) + F(tx * tx)) + F(tz * tz)))))
        ty = F(ty * r); tz = F(tz * r); tx = F(tx * r)
        nb[i, 0:4] = (e(nz), e(ny), e(nx), 0xff)
        nb[i, 4:8] = (t1(tz), t1(ty), t1(tx), 0xff)
        bx = F(F(ny * tz) - F(nz * ty)); by = F(F(nz * tx) - F(nx * tz)); bz = F(F(nx * ty) - F(ny * tx))
        nb[i, 8:12] = (t1(bz), t1(by), t1(bx), 0xff)
    out = []                                                # drop triangles touching a steep vertex
    for q in range(0, len(idx), 3):
        tri = idx[q:q + 3]
        if any(nb[i, 1] < 0x82 for i in tri): continue
        out += tri
    raw = None
    if bounds is not None:
        x0, z0, x1, z1 = (F(b) for b in bounds)
        tk = F(s.total * F(0.1))
        raw = np.zeros((n, 32), np.uint8)
        raw[:, 0:6] = H.view(np.uint8).reshape(n, 6)
        raw[:, 6:8] = (2, 0)                                # half 0x0002 from the vertex template
        for i, v in enumerate(sec):
            uv = [half_bits(F(v['off'] * F(0.1))), half_bits(F(tk * v['t'])),
                  half_bits(F(F(v['x'] - x0) / F(x1 - x0))), half_bits(F(F(v['z'] - z0) / F(z1 - z0)))]
            raw[i, 8:16] = np.array(uv, np.uint16).view(np.uint8)
        raw[:, 16:28] = nb
        raw[:, 28:32] = 0xff
    return sec, H, nb, out, raw
