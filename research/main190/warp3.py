#!/usr/bin/env python3
"""North-scaling warp (round 6 candidate): the south keeps 190E's size, everything north of a transition band is
scaled up uniformly by S (shapes kept), anchored on a central column xc. In the band (rows y0..y1 of 190E) the scale
ramps smoothly: x' = xc + (x - xc) * s(y), y' = integral of s - so the only distortion is a shear in the band that
grows with distance from xc. West/north padding added after the warp (new hexes)."""
import numpy as np
from warp import W0, H0


class NorthWarp:
    def __init__(self, S=1.4, y0=330, y1=450, xc=490, west=128, north=48, xband=None, xmap=None):
        # xmap=dict(SXW, xw, SXE, xa, k) (user, round 8 "round-7 width, lean in the east"): in the north the columns
        # west of xw are widened by SXW (Hexi; the slide falls in the empty Qiang highlands), columns xw..xa are not
        # widened at all (Liang / Longxi / Guanzhong / Shu - no slide), columns east of xa by SXE (Central Plains,
        # Hebei, the east); joins smoothed over ~k columns. x' = x + (f(x) - x) * t(y), t = the height ramp.
        self.xmap = xmap
        if xmap:
            g = np.linspace(-800, 1600, 24001); k = xmap.get("k", 12.0)
            sig = lambda u: 1 / (1 + np.exp(-u))
            mid = (xmap["xw"] + xmap["xa"]) / 2
            def cum(d):
                F = np.concatenate([[0], np.cumsum((d[1:] + d[:-1]) / 2 * np.diff(g))]); return F - np.interp(mid, g, F) + mid
            # west (Hexi) widening ramps in with the north; east widening too - or, with east_all (user, round 8:
            # "widen the whole east"), applies at every latitude so nothing slides anywhere east of xa
            self._fg = g
            self._fw_w = cum(1 + (xmap["SXW"] - 1) * sig((xmap["xw"] - g) / k))
            self._fw_e = cum(1 + (xmap["SXE"] - 1) * sig((g - xmap["xa"]) / k))
            self._ff = self._fw_w + self._fw_e - g
        # xband=(y0_west, x_lo, x_hi) (user, round 8 "fix Shu"): the WIDTH ramp starts at row y0_west for columns
        # x <= x_lo (Shu / Ba keep 190E's horizontal positions - no shear in the Sichuan basin) and at y0 for x >= x_hi,
        # smoothstep between; the height ramp Y(y) is unchanged (no vertical kinks anywhere)
        self.S, self.y0, self.y1, self.xc, self.xband = S, y0, y1, xc, xband
        if xmap: self.west = west
        t = np.linspace(0, 1, 2049); self._t = t; sm = t * t * (3 - 2 * t)
        self._cum = np.concatenate([[0], np.cumsum(((1 + (S - 1) * sm[1:]) + (1 + (S - 1) * sm[:-1])) / 2 * np.diff(t))]) * (y1 - y0)
        xs = np.array([0, W0 - 1] * 2, float); ys = np.array([0, 0, H0 - 1, H0 - 1], float)
        nx, ny = self._fw(xs, ys)
        self.ox = -nx.min(); self.west, self.north = (west if self.xmap else west * S), north * S
        self.W = int(4 * np.ceil((nx.max() - nx.min() + self.west) / 4)); self.H = int(4 * np.ceil((ny.max() + self.north) / 4))

    def s(self, y):
        t = np.clip((np.asarray(y, float) - self.y0) / (self.y1 - self.y0), 0, 1); return 1 + (self.S - 1) * t * t * (3 - 2 * t)

    def Y(self, y):
        y = np.asarray(y, float)
        return np.where(y < self.y0, y, np.where(y > self.y1, self.y0 + self._cum[-1] + (y - self.y1) * self.S,
                                                  self.y0 + np.interp((y - self.y0) / (self.y1 - self.y0), self._t, self._cum)))

    def y0x(self, x):
        if not self.xband: return np.full(np.shape(x), float(self.y0))
        yw, lo, hi = self.xband; t = np.clip((np.asarray(x, float) - lo) / (hi - lo), 0, 1); t = t * t * (3 - 2 * t)
        return yw + (self.y0 - yw) * t

    def sx(self, x, y):
        a = self.y0x(x); t = np.clip((np.asarray(y, float) - a) / (self.y1 - self.y0), 0, 1)
        return 1 + (self.S - 1) * t * t * (3 - 2 * t)

    def _fw(self, x, y):
        x = np.asarray(x, float); y = np.asarray(y, float)
        if self.xmap:
            t = (self.s(y) - 1) / (self.S - 1)
            dw = np.interp(x, self._fg, self._fw_w) - x; de = np.interp(x, self._fg, self._fw_e) - x
            return x + dw * t + de * (1.0 if self.xmap.get("east_all") else t), self.Y(y)
        if self.xband: return self.xc + (x - self.xc) * self.sx(x, y), self.Y(y)
        return self.xc + (x - self.xc) * self.s(y), self.Y(y)

    def forward(self, x, y):
        nx, ny = self._fw(x, y); return nx + self.ox + self.west, ny

    def inverse(self, nx, ny):
        ny = np.asarray(ny, float); grid = np.linspace(-50, H0 + 50, 8001); y = np.interp(ny, self.Y(grid), grid)
        if self.xband or self.xmap:                 # x' = f(x) at fixed y is monotonic: vectorised bisection
            tx = np.asarray(nx, float) - self.west - self.ox
            y = np.broadcast_to(y, np.broadcast(tx, y).shape).astype(float); tx = np.broadcast_to(tx, y.shape)
            lo = np.full(y.shape, -400.0); hi = np.full(y.shape, W0 + 400.0)
            for _ in range(48):
                mid = (lo + hi) / 2; fm = self._fw(mid, y)[0]
                below = fm < tx; lo = np.where(below, mid, lo); hi = np.where(below, hi, mid)
            return (lo + hi) / 2, y
        return self.xc + (np.asarray(nx, float) - self.west - self.ox - self.xc) / self.s(y), y


# ---- gate passes at vanilla size (user, round 6) ----
# The pass gate models in global_props are fixed-size; scaled x1.4 the valley around them would be too wide. Around
# each pass the mapping is a pure translation (scale 1.0) out to R0 hexes, blending into the north warp by R1:
#   F(p) = N(p) + sum_i w_i(p) D_i(p) / max(1, sum_i w_i),   D_i(p) = N(c_i) + (p - c_i) - N(p),
#   w_i = 1 - smoothstep((|p - c_i| - R0) / (R1 - R0))           (|.| in world-like units, hexes)
# Inverse: the plain inverse, then fixed-point steps for points near a pin.
PASSES = {"gu": (399, 525), "hangu": (385, 477), "hulao": (443, 481), "jiameng": (233, 440), "kui": (348, 396),
          "qi": (395, 489), "san": (265, 480), "tong": (344, 477), "wu": (336, 467)}   # 190E hex (col, row) of the town
R0, R1 = 5.0, 34.0
RING = 4.0                                    # blend ring outer radius = RING x the pinned radius


def _dist(dx, dy):
    return np.sqrt((dx * 0.668) ** 2 + (dy * 0.772) ** 2) / 0.72


class PinnedNorthWarp(NorthWarp):
    """Passes closer than CLUSTER hexes form one rigid group (one translation), so neighbours like Tong/Wu and
    Hangu/Qi both stay at exactly 1.0."""
    CLUSTER = 16.0

    def __init__(self, *a, pins=PASSES, **k):
        super().__init__(*a, **k)
        pts = np.array(list(pins.values()), float); grp = list(range(len(pts)))
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                if _dist(*(pts[i] - pts[j])) < self.CLUSTER:
                    gi, gj = grp[i], grp[j]; grp = [gi if g == gj else g for g in grp]
        self.groups = []
        for g in sorted(set(grp)):
            m = pts[[k for k in range(len(pts)) if grp[k] == g]]; c = m.mean(0)
            r0 = R0 + max(_dist(*(q - c)) for q in m)
            P = np.array(NorthWarp.forward(self, c[0], c[1]), float)
            self.groups.append((c, P, r0, r0 * RING))

    def forward(self, x, y):
        x = np.asarray(x, float); y = np.asarray(y, float)
        nx, ny = NorthWarp.forward(self, x, y)
        # overlapping rings: the strongest pin wins (weights^8 mix the directions, the max weight sets how much),
        # so a point in one gate's core follows only that gate
        sx = np.zeros_like(nx); sy = np.zeros_like(ny); sk = np.zeros_like(nx); wmax = np.zeros_like(nx)
        for (cx, cy), (Px, Py), r0, r1 in self.groups:
            r = _dist(x - cx, y - cy)
            t = np.clip(np.log(np.maximum(r, r0) / r0) / np.log(r1 / r0), 0, 1)   # log-radius ramp: even skew
            wgt = 1 - t
            if not np.any(wgt > 0): continue
            k8 = wgt ** 8
            sx += k8 * (Px + (x - cx) - nx); sy += k8 * (Py + (y - cy) - ny); sk += k8; wmax = np.maximum(wmax, wgt)
        f = np.where(sk > 0, wmax / np.maximum(sk, 1e-30), 0)
        return nx + sx * f, ny + sy * f

    def inverse(self, nx, ny, iters=30):
        nx = np.asarray(nx, float); ny = np.asarray(ny, float)
        x, y = NorthWarp.inverse(self, nx, ny)
        shape = np.broadcast(nx, ny).shape
        near = np.zeros(shape, bool)
        for _, (Px, Py), r0, r1 in self.groups:
            near |= _dist(nx - Px, ny - Py) < r1 * self.S + 6
        if not near.any(): return x, y
        x = np.array(np.broadcast_to(x, shape), float); y = np.array(np.broadcast_to(y, shape), float)
        qx, qy = np.broadcast_to(nx, shape)[near], np.broadcast_to(ny, shape)[near]
        px, py = x[near], y[near]; e = 0.05
        for _ in range(iters):                                   # Newton with a numeric Jacobian
            fx, fy = self.forward(px, py); rx, ry = fx - qx, fy - qy
            if np.max(np.abs(rx)) < 1e-4 and np.max(np.abs(ry)) < 1e-4: break
            ax_, ay_ = self.forward(px + e, py); bx_, by_ = self.forward(px, py + e)
            a, c = (ax_ - fx) / e, (bx_ - fx) / e; b, d = (ay_ - fy) / e, (by_ - fy) / e
            det = a * d - b * c; det = np.where(np.abs(det) < 1e-6, 1e-6, det)
            px = px - (d * rx - c * ry) / det; py = py - (-b * rx + a * ry) / det
        x[near], y[near] = px, py
        return x, y
