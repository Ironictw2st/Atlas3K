"""Fit BOB's lf scaling lf = (l·A)·f − f·B on the get_height_worker dump: l from the two samplers, f and (A, B) searched."""
import sys, struct, numpy as np
sys.path.insert(0, '.')
import gheight_cmp as G
import lf_probe as P
F = np.float32
sub = G.sub[:400]


def l_c(x, z):
    u = F(x / P.maxX); v = F(F(1) - F(z / P.maxZ)); W, H = P.W, P.H
    fx = F(u * F(W)); fy = F(v * F(H)); x0 = F(np.floor(fx)); y0 = F(np.floor(fy))
    fyu = F(F(v - F(F(1) / F(H))) * F(H)); fxr = F(F(u + F(F(1) / F(W))) * F(W))
    def val(c, r):
        c = int(min(max(c, F(0)), F(W - 1))); r = int(min(max(r, F(0)), F(H - 1)))
        return F(F(P.L[r, c]) * P.K)
    a = val(fx, fyu); b = val(fxr, fyu); top = F(F(F(b - a) * F(fx - x0)) + a)
    c = val(fx, fy); d = val(fxr, fy); bot = F(F(F(d - c) * F(fx - x0)) + c)
    return F(F(F(bot - top) * F(fy - y0)) + top)


def l_a(x, z):
    u = F(x / P.maxX); v = F(F(1) - F(z / P.maxZ)); return P.sample(u, v)


def ulps(c, n):
    b = struct.unpack('<I', struct.pack('<f', c))[0]
    return [F(struct.unpack('<f', struct.pack('<I', b + i))[0]) for i in range(-n, n + 1)]


T = P.T
for lname, lfun in (('a', l_a), ('c', l_c)):
    ls = [lfun(F(r['x']), F(r['z'])) for r in sub]; tg = [F(r['lf']) for r in sub]
    for A, B in ((1100, 240), (5500, 1200), (2200, 480), (550, 120)):
        base = F(F(A / 1100 * 0.0390625 / (A / 1100)) * T)
        for f in ulps(F(F(0.0390625) * T), 40) + ulps(F(F(F(1) / F(128)) * T), 40):
            ok = sum(F(F(F(l * F(A)) * f) - F(f * F(B))) == t for l, t in zip(ls, tg))
            if ok > len(sub) * 0.5: print(lname, A, B, float(f), ok, len(sub))
print('l example', l_a(F(sub[0]['x']), F(sub[0]['z'])), l_c(F(sub[0]['x']), F(sub[0]['z'])))
