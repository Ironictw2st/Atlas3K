"""Bit-exactness of the lf tree height (LfSampler, float32) against CA's shipped vanilla tree list.
Every operation is done in numpy float32 (IEEE single, correctly rounded per op), so a formula variant here behaves
exactly like the same C#/C++ float code. usage: lf_exact.py"""
import struct, sys
from pathlib import Path
import numpy as np
F = np.float32
ROOT = Path(r"Z:/Claude/TerryClone/Vanilla/Map")
TL = ROOT / "campaign_maps/3k_dlc07_main_map/display/trees/trees.campaign_tree_list"
DDS = ROOT / "terrain/campaigns/3k_dlc07_main_map/lf_height_map.dds"


def load_trees():
    d = open(TL, "rb").read(); ver, a, b, W, H, n = struct.unpack_from("<IIIffI", d, 0); o = 24
    xs, ys, zs = [], [], []
    for _ in range(n):
        L, = struct.unpack_from("<H", d, o); o += 2 + L
        c, = struct.unpack_from("<I", d, o); o += 4
        for _ in range(c):
            x, y, z, f, v, sc = struct.unpack_from("<fffBBI", d, o); o += 18 + 4 * sc
            xs.append(x); ys.append(y); zs.append(z)
    return np.array(xs, F), np.array(ys, F), np.array(zs, F)


def load_lf():
    b = open(DDS, "rb").read(); h, w = struct.unpack_from("<II", b, 12)
    return np.frombuffer(b, np.uint16, w * h, 128).reshape(h, w)


TILE = F(F(595.1) / F(1784))
ZS = F(1.15476)


def lf_height(x, z, raster, variant="current"):
    h, w = raster.shape
    maxX = F(F(1784) * TILE); maxZ = F(F(1405) * TILE)
    zt = (z / ZS).astype(F)
    u = (x / maxX).astype(F); v = (F(1) - (zt / maxZ).astype(F)).astype(F)
    fx = (u * F(w)).astype(F); fy = (v * F(h)).astype(F)
    x0 = np.floor(fx).astype(F); y0 = np.floor(fy).astype(F)
    rx = F(F(1) / F(w)); ry = F(F(1) / F(h))
    fyu = ((v - ry).astype(F) * F(h)).astype(F); fxr = ((u + rx).astype(F) * F(w)).astype(F)
    def val(c, r):
        ci = np.clip(c, 0, w - 1).astype(np.int64); ri = np.clip(r, 0, h - 1).astype(np.int64)
        return (raster[ri, ci].astype(F) * F(1 / 65535)).astype(F) if variant != "div65535" else (raster[ri, ci].astype(F) / F(65535)).astype(F)
    a = val(fx, fyu); b = val(fxr, fyu); c = val(fx, fy); d = val(fxr, fy)
    tx = (fx - x0).astype(F); ty = (fy - y0).astype(F)
    if variant == "lerp_1mt":
        top = (a * (F(1) - tx) + b * tx).astype(F); bot = (c * (F(1) - tx) + d * tx).astype(F); l = (top * (F(1) - ty) + bot * ty).astype(F)
    else:
        top = ((b - a).astype(F) * tx + a).astype(F); bot = ((d - c).astype(F) * tx + c).astype(F)
        l = ((bot - top).astype(F) * ty + top).astype(F)
    f = F(F(F(1) / F(128)) * TILE)
    if variant == "scale_fused":
        return ((l * F(5500) - F(1200)).astype(F) * f).astype(F)
    return ((l * F(5500)).astype(F) * f - (f * F(1200)).astype(F)).astype(F)


if __name__ == "__main__":
    xs, ys, zs = load_trees(); raster = load_lf()
    print(f"{len(xs):,} trees, lf {raster.shape}")
    for var in (sys.argv[1:] or ["current"]):
        hgt = lf_height(xs, zs, raster, var)
        exact = (hgt.view(np.int32) == ys.view(np.int32))
        ulp = np.abs(hgt.view(np.int32).astype(np.int64) - ys.view(np.int32).astype(np.int64))
        print(f"{var:14s} bit-exact {exact.mean():.4%}  within 1e-5 {(np.abs(hgt - ys) <= 1e-5).mean():.4%}  "
              f"ulp<=2 {(ulp <= 2).mean():.4%}  median ulp {int(np.median(ulp))}  diff>1e-3 {(np.abs(hgt - ys) > 1e-3).mean():.4%}")


def lf_height_bob(x, z, raster):
    """FUN_18039eea0 + get_height_worker (0x371030), float32: corners at int(fx), int(fx)+1 and int(fy)-1, int(fy)."""
    h, w = raster.shape
    maxX = F(F(1784) * TILE); maxZ = F(F(1405) * TILE)
    zt = (z / ZS).astype(F)
    u = (x / maxX).astype(F); v = (F(1) - (zt / maxZ).astype(F)).astype(F)
    fx = (F(w) * u).astype(F); fy = (F(h) * v).astype(F)
    xi = fx.astype(np.int64); yi = fy.astype(np.int64)                       # trunc (values >= 0)
    x0 = xi.astype(F); y0 = yi.astype(F)
    x1 = (x0 + F(1)).astype(F); ym = (y0 - F(1)).astype(F)
    cl = lambda a, m: np.clip(a, F(0), F(m)).astype(np.int64)
    K = F(1 / 65535)
    val = lambda c, r: (raster[r, c].astype(F) * K).astype(F)
    a = val(cl(x0, w - 1), cl(ym, h - 1)); b = val(cl(x1, w - 1), cl(ym, h - 1))
    c = val(cl(x0, w - 1), cl(y0, h - 1)); d = val(cl(x1, w - 1), cl(y0, h - 1))
    tx = (fx - x0).astype(F); ty = (fy - y0).astype(F)
    top = ((b - a).astype(F) * tx + a).astype(F)
    bot = ((d - c).astype(F) * tx + c).astype(F)
    l = ((bot - top).astype(F) * ty + top).astype(F)
    f = F(F(F(1) / F(128)) * TILE)
    return ((l * F(5500)).astype(F) * f - (f * F(1200)).astype(F)).astype(F)


def report(name, hgt, ys):
    exact = (hgt.view(np.int32) == ys.view(np.int32))
    print(f"{name:14s} bit-exact {exact.mean():.4%}  within 1e-5 {(np.abs(hgt - ys) <= 1e-5).mean():.4%}  diff>1e-3 {(np.abs(hgt - ys) > 1e-3).mean():.4%}")
    return exact
