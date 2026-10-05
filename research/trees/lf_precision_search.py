"""lf tree height: try FMA (single rounding) and double-precision variants of the sampler steps.
usage: lf_precision_search.py"""
import itertools
import numpy as np
from lf_exact import load_trees, load_lf, F, TILE

xs, ys, zs = load_trees(); raster = load_lf()
h, w = raster.shape
D = np.float64


def fma(a, b, c):        # single-rounded a*b+c (exact in double for float32 inputs, then one rounding)
    return (a.astype(D) * b.astype(D) + c.astype(D)).astype(F)


def run(lerp, final, uv, val):
    maxX = F(F(1784) * TILE); maxZ = F(F(1405) * TILE)
    zt = (zs / F(1.15476)).astype(F)
    if uv == "f32":
        u = (xs / maxX).astype(F); v = (F(1) - (zt / maxZ).astype(F)).astype(F)
        fx = (F(w) * u).astype(F); fy = (F(h) * v).astype(F)
    else:
        u = xs.astype(D) / D(maxX); v = 1 - zt.astype(D) / D(maxZ)
        fx = (w * u).astype(F); fy = (h * v).astype(F)
    x0 = fx.astype(np.int64).astype(F); y0 = fy.astype(np.int64).astype(F)
    x1 = x0 + F(1); ym = y0 - F(1)
    cl = lambda a, m: np.clip(a, 0, m).astype(np.int64)
    if val == "mulK": V = lambda c, r: (raster[r, c].astype(F) * F(1 / 65535)).astype(F)
    else: V = lambda c, r: (raster[r, c].astype(F) / F(65535)).astype(F)
    a = V(cl(x0, w - 1), cl(ym, h - 1)); b = V(cl(x1, w - 1), cl(ym, h - 1))
    c = V(cl(x0, w - 1), cl(y0, h - 1)); d = V(cl(x1, w - 1), cl(y0, h - 1))
    tx = (fx - x0).astype(F); ty = (fy - y0).astype(F)
    if lerp == "plain":
        top = ((b - a).astype(F) * tx + a).astype(F); bot = ((d - c).astype(F) * tx + c).astype(F)
        l = ((bot - top).astype(F) * ty + top).astype(F)
    elif lerp == "fma":
        top = fma((b - a).astype(F), tx, a); bot = fma((d - c).astype(F), tx, c); l = fma((bot - top).astype(F), ty, top)
    else:  # double
        ad, bd, cd, dd, txd, tyd = (q.astype(D) for q in (a, b, c, d, tx, ty))
        top = (bd - ad) * txd + ad; bot = (dd - cd) * txd + cd; l = ((bot - top) * tyd + top).astype(F)
    f = F(F(F(1) / F(128)) * TILE)
    if final == "plain": return ((l * F(5500)).astype(F) * f - (f * F(1200)).astype(F)).astype(F)
    if final == "fma": return fma((l * F(5500)).astype(F), np.full_like(l, f), -np.full_like(l, (f * F(1200)).astype(F)))
    return ((l.astype(D) * 5500 * D(f)) - D(f) * 1200).astype(F)


res = []
for combo in itertools.product(("plain", "fma", "double"), ("plain", "fma", "double"), ("f32", "f64"), ("mulK", "divK")):
    hgt = run(*combo)
    res.append(((hgt.view(np.int32) == ys.view(np.int32)).mean(), combo))
for r in sorted(res, reverse=True)[:10]: print(f"{r[0]:.4%}", r[1])
