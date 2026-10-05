"""Search the tile size / scale-factor representation and the u/v mapping for a bit-exact lf tree height.
Sampler = BOB's FUN_18039eea0 port (lf_exact.lf_height_bob internals). usage: lf_scale_search.py"""
import itertools
import numpy as np
from lf_exact import load_trees, load_lf, F

xs, ys, zs = load_trees(); raster = load_lf()
h, w = raster.shape
K = F(1 / 65535)


def sample(u, v):
    fx = (F(w) * u).astype(F); fy = (F(h) * v).astype(F)
    x0 = fx.astype(np.int64).astype(F); y0 = fy.astype(np.int64).astype(F)
    x1 = (x0 + F(1)).astype(F); ym = (y0 - F(1)).astype(F)
    cl = lambda a, m: np.clip(a, F(0), F(m)).astype(np.int64)
    val = lambda c, r: (raster[r, c].astype(F) * K).astype(F)
    a = val(cl(x0, w - 1), cl(ym, h - 1)); b = val(cl(x1, w - 1), cl(ym, h - 1))
    c = val(cl(x0, w - 1), cl(y0, h - 1)); d = val(cl(x1, w - 1), cl(y0, h - 1))
    tx = (fx - x0).astype(F); ty = (fy - y0).astype(F)
    top = ((b - a).astype(F) * tx + a).astype(F); bot = ((d - c).astype(F) * tx + c).astype(F)
    return ((bot - top).astype(F) * ty + top).astype(F)


tiles = {"f32(595.1)/f32(1784)": F(F(595.1) / F(1784)), "f32(595.1/1784 dbl)": F(595.1 / 1784),
         "f32(595.1)*f32(1/1784)": F(F(595.1) * F(F(1) / F(1784)))}
results = []
for (kt, T), zmode, umode, fmode in itertools.product(tiles.items(), ("div", "mulinv"), ("div", "mulinv"),
                                                      ("1/128*T", "T/128", "dbl", "T*(1/128)")):
    maxX = F(F(1784) * T); maxZ = F(F(1405) * T)
    zt = (zs / F(1.15476)).astype(F) if zmode == "div" else (zs * F(F(1) / F(1.15476))).astype(F)
    if umode == "div":
        u = (xs / maxX).astype(F); v = (F(1) - (zt / maxZ).astype(F)).astype(F)
    else:
        u = (xs * F(F(1) / maxX)).astype(F); v = (F(1) - (zt * F(F(1) / maxZ)).astype(F)).astype(F)
    l = sample(u, v)
    f = {"1/128*T": F(F(F(1) / F(128)) * T), "T/128": F(T / F(128)), "dbl": F(595.1 / 1784 / 128),
         "T*(1/128)": F(T * F(F(1) / F(128)))}[fmode]
    for order in ("(l*5500)*f-f*1200", "l*(5500*f)-f*1200"):
        if order.startswith("(l"): hgt = ((l * F(5500)).astype(F) * f - (f * F(1200)).astype(F)).astype(F)
        else: hgt = (l * F(F(5500) * f) - (f * F(1200)).astype(F)).astype(F)
        ex = (hgt.view(np.int32) == ys.view(np.int32)).mean()
        results.append((ex, kt, zmode, umode, fmode, order))
for r in sorted(results, reverse=True)[:10]: print(f"{r[0]:.4%}", *r[1:])
