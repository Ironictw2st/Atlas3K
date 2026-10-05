"""Float32 port of BOB's river spline (tooldatabuilder FUN_18016e440 segment add + length, utilitydll FUN_1800a4990
eval, SEGMENTED_SPLINE_3::optimise_spline) to test against BOB's river meshes.
Segments: Bezier (p_i, p_i + tangent_out_i, p_i+1 + tangent_in_i+1, p_i+1) in world space (entity transform applied).
usage: bob_spline.py <river layer> [bob models dir]"""
import math, re, sys
import xml.etree.ElementTree as ET
import numpy as np
F = np.float32
WORLD_F32 = False
CTRL_MODE = 'local'   # 'local': W(p + t) ; 'world': W(p) + t
B = [[-1, 3, -3, 1], [3, -6, 3, 0], [-3, 3, 0, 0], [1, 0, 0, 0]]


def weights(u3, u2, u1, u0):
    return [F(F(F(F(u3) * F(B[r][0])) + F(F(u2) * F(B[r][1]))) + F(F(u1) * F(B[r][2]))) + F(F(u0) * F(B[r][3])) for r in range(4)]
    # (Ghidra shows a*b + c*d + e*f + g*h; evaluated left to right in float32)


def eval_seg(P, u):
    u = F(u); u2 = F(u * u); u3 = F(u2 * u)
    w = weights(u3, u2, u, F(1))
    return [F(F(F(F(w[3] * P[3][k]) + F(w[2] * P[2][k])) + F(P[1][k] * w[1])) + F(P[0][k] * w[0])) for k in range(3)]


def eval_seg_fwd(P, u):
    """FUN_1801884d0 with (u^3, u^2, u, 1): sum w0*P0 + w1*P1 + w2*P2 + w3*P3, left to right (river sections)."""
    u = F(u); u2 = F(u * u); u3 = F(u * u2)
    w = weights(u3, u2, u, F(1))
    return [F(F(F(F(w[0] * P[0][k]) + F(w[1] * P[1][k])) + F(w[2] * P[2][k])) + F(w[3] * P[3][k])) for k in range(3)]


def deriv_seg(P, u):
    u = F(u)
    w = weights(F(F(u * F(3)) * u), F(u + u), F(1), F(0))   # (3u^2, 2u, 1, 0) (FUN_18016e440 local_b8/local_b0)
    return [F(F(F(F(w[0] * P[0][k]) + F(w[1] * P[1][k])) + F(w[2] * P[2][k])) + F(w[3] * P[3][k])) for k in range(3)]


class Spline:
    def __init__(self, steps=1000):
        self.segs, self.lens, self.starts, self.total, self.steps = [], [], [], F(0), steps

    def add(self, p0, p1, p2, p3):
        P = [list(map(F, p)) for p in (p0, p1, p2, p3)]
        h = F(0.5)
        e01, e23 = P[0] == P[1], P[2] == P[3]
        straight = e01 or e23                              # FUN_18016e440: any degenerate end -> straight length
        if e01 and not e23: P[1] = [F(F(P[2][k] + P[0][k]) * h) for k in range(3)]
        elif e23 and not e01: P[2] = [F(F(P[1][k] + P[3][k]) * h) for k in range(3)]
        elif e01 and e23:
            P[1] = [F(F(P[3][k] + P[0][k]) * h) for k in range(3)]; P[2] = list(P[1])
        self.segs.append(P)
        if straight:
            L = F(math.sqrt(F(sum(F(F(P[0][k] - P[3][k]) * F(P[0][k] - P[3][k])) for k in (1, 0, 2)))))
        else:
            du = F(F(1) / F(self.steps)); u = F(0); acc = F(0)
            while u < F(1):
                d = deriv_seg(P, u)
                acc = F(acc + F(math.sqrt(F(F(F(d[1] * d[1]) + F(d[0] * d[0])) + F(d[2] * d[2])))))
                u = F(u + du)
            L = F(acc * du)
        self.lens.append(L); self.starts.append(self.total); self.total = F(self.total + L)

    def eval(self, t):
        t = F(t); acc = F(0); i = len(self.segs) - 1
        for k, L in enumerate(self.lens):
            ok = acc <= t; acc = F(F(L / self.total) + acc)
            if ok and t <= acc: i = k; break
        u = F(F(F(self.total * t) - self.starts[i]) / self.lens[i])
        return eval_seg(self.segs[i], u)

    def optimise(self, density=20.0, extra=(), tol=0.02):
        n = F(F(density) * self.total); n = F(n + F(0.5)) if n > 0 else F(n - F(0.5))
        N = int(n); out = [F(0)]
        if N > 3:
            step = F(F(1) / F(N - 1)); last = 1; lim = F(F(1) - F(tol))
            for k in range(2, N):
                a = self.eval(out[-1]); b = self.eval(F(F(last) * step))
                c = self.eval(F(F(k - 1) * step)); d = self.eval(F(F(k) * step))
                v1 = [F(b[i] - a[i]) for i in range(3)]; v2 = [F(d[i] - c[i]) for i in range(3)]
                l1 = F(math.sqrt(F(F(F(v1[1] * v1[1]) + F(v1[0] * v1[0])) + F(v1[2] * v1[2]))))
                l2 = F(math.sqrt(F(F(F(v2[1] * v2[1]) + F(v2[0] * v2[0])) + F(v2[2] * v2[2]))))
                i1 = F(F(1) / l1); i2 = F(F(1) / l2)
                dot = F(F(F(F(F(i2 * v2[0]) * v1[0]) * i1) + F(F(F(i2 * v2[1]) * v1[1]) * i1)) + F(F(F(i2 * v2[2]) * v1[2]) * i1))
                if dot < lim:
                    out.append(F(F(k - 1) * step)); last = k
        out.append(F(1))
        if not extra: return out
        ts = sorted(out + [F(e) for e in extra])            # insert at end + std::sort
        # BOB's unique pass (decompiled tail of optimise_spline): compacts in place but never shrinks the count,
        # so the old tail values stay in the list
        i = next((k for k in range(1, len(ts)) if ts[k] == ts[k - 1]), None)
        if i is not None:
            w = i - 1
            for r in range(i + 1, len(ts)):
                if ts[r] != ts[w]:
                    w += 1; ts[w] = ts[r]
        return ts


def rivers(layer):
    out = []
    for ent in ET.parse(layer).getroot().iter("entity"):
        sp = ent.find("ECRiverSpline")
        if sp is None: continue
        tr = ent.find("ECTransform"); pos = list(map(float, tr.get("position").split())); yaw = math.radians(float(tr.get("rotation").split()[1]))
        def W(p, pos=pos, yaw=yaw):
            if yaw == 0 and WORLD_F32:
                return tuple(F(F(p[k]) + F(pos[k])) for k in range(3))
            return (pos[0] + p[0] * math.cos(yaw) + p[2] * math.sin(yaw), pos[1] + p[1], pos[2] - p[0] * math.sin(yaw) + p[2] * math.cos(yaw))
        pts = [(tuple(map(float, p.get("position").split(","))), tuple(map(float, p.get("tangent_in").split(","))),
                tuple(map(float, p.get("tangent_out").split(",")))) for p in sp.iter("point")]
        out.append((ent.get("id"), ent.get("name"), pts, W, float(sp.get("spline_step_size", "1.5"))))
    return out


if __name__ == "__main__":
    extra = [F(F(k) * F(F(1) / F(8))) for k in range(7)]
    res = []
    for eid, name, pts, W, step in rivers(sys.argv[1]):
        s = Spline()
        for a, b in zip(pts, pts[1:]):
            p0 = a[0]; p3 = b[0]
            p1 = tuple(p0[k] + a[2][k] for k in range(3)); p2 = tuple(p3[k] + b[1][k] for k in range(3))
            s.add(W(p0), W(p1), W(p2), W(p3))
        ts = s.optimise(extra=extra)
        res.append((int(eid, 16), name, len(pts), float(s.total), len(ts)))
    for r in sorted(res, reverse=True): print(f"id {r[0]:x} {r[1]:10s} pts {r[2]:3d} length {r[3]:8.3f} sections {r[4]:4d} -> verts {r[4]*5}")


def half_bob(x):
    """FUN_1803811a0 (tooldatabuilder): BOB's float -> half (its own rounding), returned as the half's float value."""
    u = int(np.array([x], dtype=np.float32).view(np.uint32)[0])
    sign = (u >> 16) & 0x8000; e = (u >> 23) & 0xff
    if e > 0x8e: h = sign | 0x7c00
    elif e > 0x70:
        v = u & 0x7fffffff
        v = (v + (((v - 1) & v) & 0x1fff)) & 0xffffffff
        h = ((v >> 13) & 0x3ff) | ((((v >> 23) + 0x10) * 0x400) & 0xffff) | sign
        h &= 0xffff
    elif e > 0x66:
        m = u & 0x7fffff; sh = (e + 0x99) & 0x1f
        if ((m << sh) & 0x3fffff) > 0x200:
            r = (0x7fffff >> sh) & m; m = m + ((r - 1) & r)
        m = (m + 0x800000) >> ((0x7e - e) & 0x1f)
        h = (m & 0xffff) | sign
    else:
        h = sign | (1 if (u & 0x7fffffff) > 0x33000400 else 0)
    return float(np.array([h], dtype=np.uint16).view(np.float16)[0])


def sections_bob(s, ts, widths):
    """Cross-sections as in FUN_18015e9e0: position = Eval(t), direction = derivative at t (xz), width = lerp of the
    segment's start/end widths by the local u; 5 vertices at off = j*0.25*w - 0.5*w along (dz, -dx)."""
    out = []
    for t in ts:
        t = F(t); acc = F(0); i = len(s.segs) - 1
        for k, L in enumerate(s.lens):
            ok = acc <= t; acc = F(F(F(1) / s.total) * L + acc)
            if ok and t <= acc: i = k; break
        u = F(F(F(s.total * t) - s.starts[i]) / s.lens[i])
        uc = min(max(u, F(0)), F(1))
        w = F(F(F(widths[i][1] - widths[i][0]) * uc) + widths[i][0])
        p = eval_seg_fwd(s.segs[i], u)
        d = deriv_seg(s.segs[i], u)
        l2 = F(F(d[2] * d[2]) + F(d[0] * d[0]))
        dx, dz = d[0], d[2]
        if l2 > 0: inv = F(F(1) / F(math.sqrt(l2))); dx = F(d[0] * inv); dz = F(inv * d[2])
        o0 = F(w * F(-0.5)); span = F(F(w * F(0.5)) - o0)
        for j in range(5):
            off = F(F(F(F(j) * F(0.25)) * span) + o0)
            x = F(F(dz * off) + p[0]); z = F(F(-F(dx * off)) + p[2])
            out.append((half_bob(x), half_bob(p[1]), half_bob(z)))
    return out
