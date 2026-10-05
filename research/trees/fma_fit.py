"""Test fused multiply-add placements in BOB's lf sampler and final scaling against BOB's per-tree lf (uv_dump.npy).
fma32(a, b, c) = round_f32(a*b + c) evaluated in float64 (a*b exact for float32 inputs; the add is exact enough to
round correctly except in rare double-rounding cases). usage: fma_fit.py"""
import itertools
import numpy as np
from lf_exact import load_lf, F, TILE

D = np.load("uv_dump.npy").astype(F)
x, z, hf, lf, U, V = D.T
ok = np.isfinite(U); U, V, lf = U[ok], V[ok], lf[ok]
raster = load_lf(); h, w = raster.shape
K = F(1 / 65535)
fma = lambda a, b, c: (a.astype(np.float64) * b.astype(np.float64) + c.astype(np.float64)).astype(F)
fx = (F(w) * U).astype(F); fy = (F(h) * V).astype(F)
x0 = fx.astype(np.int64).astype(F); y0 = fy.astype(np.int64).astype(F)
x1 = (x0 + F(1)).astype(F); ym = (y0 - F(1)).astype(F)
cl = lambda a, m: np.clip(a, F(0), F(m)).astype(np.int64)
def val(c, r, fused):
    v = raster[r, c].astype(F)
    return fma(v * K if False else v, np.full_like(v, K), np.zeros_like(v)) if fused else (v * K).astype(F)
f = F(F(F(1) / F(128)) * TILE); A = F(5500); B = F(1200)
res = []
for lerp_fma, final_fma, val_fma in itertools.product((False, True), ("none", "lA_f_minus", "neg"), (False,)):
    a = val(cl(x0, w - 1), cl(ym, h - 1), val_fma); b = val(cl(x1, w - 1), cl(ym, h - 1), val_fma)
    c = val(cl(x0, w - 1), cl(y0, h - 1), val_fma); d = val(cl(x1, w - 1), cl(y0, h - 1), val_fma)
    tx = (fx - x0).astype(F); ty = (fy - y0).astype(F)
    if lerp_fma:
        top = fma((b - a).astype(F), tx, a); bot = fma((d - c).astype(F), tx, c); L = fma((bot - top).astype(F), ty, top)
    else:
        top = ((b - a).astype(F) * tx + a).astype(F); bot = ((d - c).astype(F) * tx + c).astype(F)
        L = ((bot - top).astype(F) * ty + top).astype(F)
    lA = (L * A).astype(F); fB = (f * B).astype(F)
    if final_fma == "none": hgt = (lA * f - fB).astype(F)
    elif final_fma == "lA_f_minus": hgt = fma(lA, np.full_like(lA, f), np.full_like(lA, -fB))
    else: hgt = fma(np.full_like(lA, -f), np.full_like(lA, B), (lA * f).astype(F))
    ex = (hgt.view(np.int32) == lf.view(np.int32)).mean()
    res.append((ex, lerp_fma, final_fma))
for r in sorted(res, reverse=True): print(f"{r[0]:.4%}  lerp_fma={r[1]}  final={r[2]}")
