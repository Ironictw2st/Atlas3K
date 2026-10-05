#!/usr/bin/env python3
"""The 190E main-map warp: one mapping shared by the hex, raster and layer builders.

Coordinates are hex units of the 190E grid (col, row; row 0 = south). The new grid is
  x' = x + WEST + Dx(x, y)          y' = y + Dy(x, y)          (north padding just adds rows at the top)
with the Central Plains magnified by K inside a core box and a smoothstep falloff around it:
  Dx(x, y) = (K - 1) * G(x) * e_y(y)     G(x) = integral of the x-profile up to x (0 west of the box, CORE+ramp east)
  Dy(x, y) = (K - 1) * H(y) * e_x(x)
mode "band":  e = 1 everywhere     -> whole rows/columns through the box stretch (separable, simple)
mode "local": e = the other axis' profile with a wide falloff -> only the Central Plains scale up; the rest keeps
              its scale and is shifted aside (gradual shear across the falloff).
dx'/dx = 1 + (K-1) g(x) e(y) >= 1, so the map never folds; inverse() solves it by fixed-point iteration.
"""
import numpy as np

W0, H0 = 892, 702                      # 190E grid
# Central Plains core box (190E hex cols/rows): Luoyang (430,480) .. Xiapi (556,452), Taishan/Weijun (~530), Runan 394
CX0, CX1 = 420, 565
CY0, CY1 = 430, 535
RAMP = 40                              # hexes of smoothstep falloff on each side of the core (magnification axis)
ENV = 90                               # hexes of envelope falloff (local mode, other axis)
K = 1.6
WEST, NORTH = 128, 48                  # padding for the Hexi corridor / Xianbei steppe


def _smooth(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def _profile(v, a, b, ramp):
    """1 inside [a, b], smoothstep to 0 over `ramp` outside."""
    return _smooth((v - (a - ramp)) / ramp) * _smooth(((b + ramp) - v) / ramp)


def _integral(v, a, b, ramp, n=2048):
    """Integral of _profile from -inf to v (numeric, vectorised via a lookup table)."""
    lo, hi = a - ramp - 1, b + ramp + 1
    t = np.linspace(lo, hi, n)
    cum = np.concatenate([[0.0], np.cumsum((_profile(t[1:], a, b, ramp) + _profile(t[:-1], a, b, ramp)) / 2 * np.diff(t))])
    return np.interp(v, t, cum, left=0.0, right=cum[-1])


class Warp:
    def __init__(self, mode="local", k=K, west=WEST, north=NORTH):
        self.mode, self.k, self.west, self.north = mode, k, west, north
        gx_total = _integral(np.array([1e9]), CX0, CX1, RAMP)[0]
        gy_total = _integral(np.array([1e9]), CY0, CY1, RAMP)[0]
        w = W0 + west + (k - 1) * gx_total
        h = H0 + north + (k - 1) * gy_total
        self.W, self.H = int(4 * np.ceil(w / 4)), int(4 * np.ceil(h / 4))     # multiples of 4 (BOB mesh grid)

    def _env_y(self, y):
        return np.ones_like(y, dtype=float) if self.mode == "band" else _profile(y, CY0, CY1, ENV)

    def _env_x(self, x):
        return np.ones_like(x, dtype=float) if self.mode == "band" else _profile(x, CX0, CX1, ENV)

    def forward(self, x, y):
        """190E (col,row) -> new (col,row), floats."""
        x = np.asarray(x, float); y = np.asarray(y, float)
        nx = x + self.west + (self.k - 1) * _integral(x, CX0, CX1, RAMP) * self._env_y(y)
        ny = y + (self.k - 1) * _integral(y, CY0, CY1, RAMP) * self._env_x(x)
        return nx, ny

    def inverse(self, nx, ny, iters=40):
        """new (col,row) -> 190E (col,row), floats (fixed point: x = nx - west - D(x, y))."""
        nx = np.asarray(nx, float); ny = np.asarray(ny, float)
        x, y = nx - self.west, ny.copy()
        for _ in range(iters):
            x = nx - self.west - (self.k - 1) * _integral(x, CX0, CX1, RAMP) * self._env_y(y)
            y = ny - (self.k - 1) * _integral(y, CY0, CY1, RAMP) * self._env_x(x)
        return x, y

    def scale_at(self, x, y):
        """Local area magnification at 190E (x, y) (determinant of the Jacobian, approx)."""
        e = 1e-3
        a = self.forward(x + e, y)[0] - self.forward(x - e, y)[0]
        d = self.forward(x, y + e)[1] - self.forward(x, y - e)[1]
        return a * d / (4 * e * e)


if __name__ == "__main__":
    for m in ("band", "local"):
        w = Warp(m)
        print(m, "new size", w.W, "x", w.H)
        for name, (c, r) in {"Luoyang": (430, 480), "Xiapi": (556, 452), "Wuwei": (135, 563), "Chengdu-ish": (240, 400),
                             "Jianye-ish": (640, 360), "Youzhou-ish": (560, 640)}.items():
            nx, ny = w.forward(c, r); bx, by = w.inverse(nx, ny)
            print(f"  {name:12s} ({c},{r}) -> ({float(nx):.0f},{float(ny):.0f})  scale {float(w.scale_at(c, r)):.2f}  roundtrip err {abs(float(bx)-c)+abs(float(by)-r):.1e}")


class WarpMapping:
    """Adapter for rebuild_hex.rebuild(mapping=...): world units of the 190E grid <-> world units of the new grid."""
    HX, HZ = 0.668, 0.772

    def __init__(self, warp):
        self.warp, self.W, self.H = warp, warp.W, warp.H

    def fwd_world(self, x, z):
        nx, ny = self.warp.forward(np.asarray(x, float) / self.HX, np.asarray(z, float) / self.HZ)
        return nx * self.HX, ny * self.HZ

    def inv_world(self, x, z):
        ox, oy = self.warp.inverse(np.asarray(x, float) / self.HX, np.asarray(z, float) / self.HZ)
        return ox * self.HX, oy * self.HZ


# ---- the warp the pipeline uses (one switch for every script) ----
# round 1-5: "band" (Central Plains rows/columns x1.6). Round 6 (user, 2026-09-30): the south keeps 190E's size, the
# north (Qinling-Huai northwards) is scaled x1.4 in both directions - warp3.NorthWarp.
# 2026-10-01 (user: "back to base 190E, let's just scale up the map"): map.hex comes from CAIME's map-upscaler
# ("Preserve structure", x1.5) and everything else follows the same uniform scale - ScaleWarp.
MODE = "scale1.5w140n80"  # 2026-10-01: + 140 west columns (Hexi corridor, hexi_geo.py zone) + 80 north rows (steppe); map only


class ScaleWarp:
    """Uniform scale about the origin in hex units (col, row + 0.5 for odd cols), the same mapping as CAIME's
    HexGeometry.Scale; W, H as CAIME's ReplicateHexBlocks (round(W0 * f), round(H0 * f))."""

    def __init__(self, f=1.5, west=0, north=0):
        self.f, self.west, self.north = f, west, north   # padding columns on the west (Hexi) / rows on the north (steppe)
        self.W, self.H = int(round(W0 * f)) + west, int(round(H0 * f)) + north   # row 0 = south: north rows just extend H

    def forward(self, x, y):
        return np.asarray(x, float) * self.f + self.west, np.asarray(y, float) * self.f

    def inverse(self, nx, ny, iters=None):
        return (np.asarray(nx, float) - self.west) / self.f, np.asarray(ny, float) / self.f

    def scale_at(self, x, y):
        return np.full(np.shape(x), self.f * self.f)


def is_scale():
    return MODE.startswith("scale")


def is_hexi():
    """the Hexi west pad is on: dem_fill / class_fill use hexi_geo's zone instead of the Liang zone / rubber georef"""
    return is_scale() and "w" in MODE[5:]


def current():
    if is_scale():
        import re as _re
        m_ = _re.match(r"([\d.]+)(?:w(\d+))?(?:n(\d+))?$", MODE[5:])
        return ScaleWarp(float(m_.group(1)), int(m_.group(2) or 0), int(m_.group(3) or 0))
    if MODE == "band":
        return Warp("band")
    from warp3 import PinnedNorthWarp
    # round 8 (user: "go back to the round with all the regions, and just fix Shu"): the width ramp starts north of the
    # Sichuan basin in the west (row 432 for cols <= 300, blending to row 330 by col 600) - Shu / Ba keep 190E's
    # horizontal positions; the slide happens in the Hanzhong / Wudu / Qinling mountains instead
    return PinnedNorthWarp(1.4, 330, 450, west=190, xmap=dict(SXW=1.3, xw=140, SXE=1.4, xa=390, east_all=True))
    # (user, round 8: "widen the whole east") - east of col 390 x1.4 wider at EVERY latitude (no slide anywhere);
    # (user, round 8: "round-7 width, lean in the east") - Liang / Longxi / Guanzhong / Shu (cols 140-390) are never
    # widened, so nothing slides there; Hexi (west of 140) x1.3 with the slide in the Qiang highlands; the Central
    # Plains and everything east of 390 x1.4 (slide ~16 hexes at Luoyang, ~80 at Jianye, the rest at sea)
