"""Is the lf miss explained by the input point? Perturb the tile-space z' (and x) by a few ulps and see how many trees
can be made bit-exact (upper bound for any z'/x mapping formula). Uses the BOB sampler port. usage: lf_ulp_probe.py"""
import numpy as np
from lf_exact import load_trees, load_lf, F, TILE

xs, ys, zs = load_trees(); raster = load_lf()
h, w = raster.shape
K = F(1 / 65535)
maxX = F(F(1784) * TILE); maxZ = F(F(1405) * TILE)


def height_from(x, zt):
    u = (x / maxX).astype(F); v = (F(1) - (zt / maxZ).astype(F)).astype(F)
    fx = (F(w) * u).astype(F); fy = (F(h) * v).astype(F)
    x0 = fx.astype(np.int64).astype(F); y0 = fy.astype(np.int64).astype(F)
    x1 = (x0 + F(1)).astype(F); ym = (y0 - F(1)).astype(F)
    cl = lambda a, m: np.clip(a, F(0), F(m)).astype(np.int64)
    val = lambda c, r: (raster[r, c].astype(F) * K).astype(F)
    a = val(cl(x0, w - 1), cl(ym, h - 1)); b = val(cl(x1, w - 1), cl(ym, h - 1))
    c = val(cl(x0, w - 1), cl(y0, h - 1)); d = val(cl(x1, w - 1), cl(y0, h - 1))
    tx = (fx - x0).astype(F); ty = (fy - y0).astype(F)
    top = ((b - a).astype(F) * tx + a).astype(F); bot = ((d - c).astype(F) * tx + c).astype(F)
    l = ((bot - top).astype(F) * ty + top).astype(F)
    f = F(F(F(1) / F(128)) * TILE)
    return ((l * F(5500)).astype(F) * f - (f * F(1200)).astype(F)).astype(F)


zt0 = (zs / F(1.15476)).astype(F)
base = height_from(xs, zt0).view(np.int32) == ys.view(np.int32)
print(f"base exact {base.mean():.4%}")
anyz = base.copy(); anyx = base.copy(); both = base.copy()
for dz in range(-4, 5):
    zt = (zt0.view(np.int32) + dz).view(F)
    ez = height_from(xs, zt).view(np.int32) == ys.view(np.int32); anyz |= ez
    for dx in range(-3, 4):
        xx = (xs.view(np.int32) + dx).view(F)
        e = height_from(xx, zt).view(np.int32) == ys.view(np.int32); both |= e
        if dz == 0: anyx |= e
print(f"exact if z' may move +-4 ulp: {anyz.mean():.4%};  x +-3 ulp: {anyx.mean():.4%};  both: {both.mean():.4%}")
