"""Search the lf sampling constants (world bounds, z scaling) for a bit-exact match with the vanilla tree heights.
u = (x - minX) / (maxX - minX), v = 1 - (z' - minZ) / (maxZ - minZ) as in get_height_worker (0x371030); the
bilinear sampler and final scaling as in LfSampler. usage: lf_bounds_search.py"""
import itertools
import numpy as np
from lf_exact import load_trees, load_lf, F

xs, ys, zs = load_trees(); raster = load_lf()
h, w = raster.shape
TILE = F(F(595.1) / F(1784))


def height(u, v):
    fx = (u * F(w)).astype(F); fy = (v * F(h)).astype(F)
    x0 = np.floor(fx).astype(F); y0 = np.floor(fy).astype(F)
    rx = F(F(1) / F(w)); ry = F(F(1) / F(h))
    fyu = ((v - ry).astype(F) * F(h)).astype(F); fxr = ((u + rx).astype(F) * F(w)).astype(F)
    def val(c, r):
        ci = np.clip(c, 0, w - 1).astype(np.int64); ri = np.clip(r, 0, h - 1).astype(np.int64)
        return (raster[ri, ci].astype(F) * F(1 / 65535)).astype(F)
    a = val(fx, fyu); b = val(fxr, fyu); c = val(fx, fy); d = val(fxr, fy)
    tx = (fx - x0).astype(F); ty = (fy - y0).astype(F)
    top = ((b - a).astype(F) * tx + a).astype(F); bot = ((d - c).astype(F) * tx + c).astype(F)
    l = ((bot - top).astype(F) * ty + top).astype(F)
    f = F(F(F(1) / F(128)) * TILE)
    return ((l * F(5500)).astype(F) * f - (f * F(1200)).astype(F)).astype(F)


maxXs = {"1784*tile": F(F(1784) * TILE), "595.1": F(595.1)}
maxZs = {"1405*tile": F(F(1405) * TILE), "541.79": F(541.79), "1405/1784*595.1": F(F(F(1405) / F(1784)) * F(595.1)),
         "595.1*1405/1784": F(F(F(595.1) * F(1405)) / F(1784)), "468.67": F(F(1405) * F(595.1) / F(1784))}
zfs = {"z/1.15476": lambda z: (z / F(1.15476)).astype(F), "z*(1/1.15476)": lambda z: (z * F(F(1) / F(1.15476))).astype(F),
       "z*0.866": lambda z: (z * F(0.8659808)).astype(F)}
res = []
for (kx, mx), (kz, mz), (kf, zf) in itertools.product(maxXs.items(), maxZs.items(), zfs.items()):
    zt = zf(zs)
    u = ((xs - F(0)).astype(F) / (mx - F(0))).astype(F)
    v = (F(1) - ((zt - F(0)).astype(F) / (mz - F(0))).astype(F)).astype(F)
    hgt = height(u, v)
    ex = (hgt.view(np.int32) == ys.view(np.int32)).mean()
    res.append((ex, kx, kz, kf))
for r in sorted(res, reverse=True)[:8]: print(f"{r[0]:.4%}  maxX {r[1]:10s} maxZ {r[2]:18s} {r[3]}")
