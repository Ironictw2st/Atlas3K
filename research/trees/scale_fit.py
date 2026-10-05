"""Fit the final lf scaling lf = (l*A)*f - f*B (float32) to BOB's per-tree lf, given our exact sampler l on BOB's
exact (u, v) (uv_dump.npy from uv_analyze.py). Searches f within +-N ulps of tile/128 and A, B near 5500 / 1200.
usage: scale_fit.py"""
import numpy as np
from lf_exact import load_lf, F, TILE

D = np.load("uv_dump.npy").astype(F)
x, z, hf, lf, U, V = D.T
ok = np.isfinite(U)
U, V, lf = U[ok], V[ok], lf[ok]
raster = load_lf(); h, w = raster.shape
K = F(1 / 65535)
fx = (F(w) * U).astype(F); fy = (F(h) * V).astype(F)
x0 = fx.astype(np.int64).astype(F); y0 = fy.astype(np.int64).astype(F)
x1 = (x0 + F(1)).astype(F); ym = (y0 - F(1)).astype(F)
cl = lambda a, m: np.clip(a, F(0), F(m)).astype(np.int64)
val = lambda c, r: (raster[r, c].astype(F) * K).astype(F)
a = val(cl(x0, w - 1), cl(ym, h - 1)); b = val(cl(x1, w - 1), cl(ym, h - 1))
c = val(cl(x0, w - 1), cl(y0, h - 1)); d = val(cl(x1, w - 1), cl(y0, h - 1))
tx = (fx - x0).astype(F); ty = (fy - y0).astype(F)
top = ((b - a).astype(F) * tx + a).astype(F); bot = ((d - c).astype(F) * tx + c).astype(F)
L = ((bot - top).astype(F) * ty + top).astype(F)


def step(v, k): return np.array([v], F).view(np.int32)[0] + k


best = []
f0 = F(F(F(1) / F(128)) * TILE)
for df in range(-40, 41):
    f = np.array([step(f0, df)], np.int32).view(F)[0]
    for A in (F(5500),):
        for B in (F(1200),):
            for form in ("(l*A)*f-f*B", "l*(A*f)-f*B", "(l*A-B)*f", "l*A*f-(B*f)"):
                if form == "(l*A)*f-f*B": hgt = ((L * A).astype(F) * f - (f * B).astype(F)).astype(F)
                elif form == "l*(A*f)-f*B": hgt = (L * F(A * f) - F(f * B)).astype(F)
                elif form == "(l*A-B)*f": hgt = (((L * A).astype(F) - B).astype(F) * f).astype(F)
                else: hgt = ((L * A).astype(F) * f - F(B * f)).astype(F)
                ex = (hgt.view(np.int32) == lf.view(np.int32)).mean()
                best.append((ex, df, form, float(f)))
best.sort(reverse=True)
for r in best[:8]: print(f"{r[0]:.4%}  f = f0 {r[1]:+d} ulp ({r[3]!r})  {r[2]}")
# what does BOB's lf look like as a function of l: implied f per tree for the best form
