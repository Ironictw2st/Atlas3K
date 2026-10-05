#!/usr/bin/env python3
"""Rubber-sheet lat/lon <-> 190E world (round 6).

research/guandu/georef.json is one affine fit (lat/lon -> vanilla/190E world). Vanilla squashed Liangzhou south, so
190E's western towns sit 15-70 hexes from where the affine puts them (Xiping 70, Wuwei 21, Zhangye 16); real
terrain (the Qilian range, the Hexi corridor) drawn with the plain affine would not line up with the towns.
Correction field c(w) = sum g_i r_i / (sum g_i + G0), g_i = exp(-|w - p_i|^2 / 2 SIGMA^2), where p_i = affine(seat_i)
and r_i = 190E town position - p_i, over the georef seats plus 190E's western towns. It fades to 0 away from the
anchors (G0), so the east / south keep the affine.
  to_world(lat, lon) = p + c(p)                 (lat/lon -> 190E world)
  to_lonlat(wx, wz) = affine^-1(w - c(.))       (190E world -> lat/lon, 3 fixed-point steps)
"""
import json, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))

M = np.array(json.load(open(HERE.parent / "guandu" / "georef.json"))["M"])
MINV = np.linalg.inv(M[:2])
SIGMA, G0 = 45.0, 0.05                                   # world units (~60 hexes); weight of "no correction"
ORIG_HEX = r"Z:/Claude/TerryClone/output/backups/main190_originals_20260929_130639/190Expanded_map.hex"
# 190E's own western towns (not in the georef seat list): region -> (seat, lat, lon)
# Only towns 190E placed near their real seat (research_r6/inventory.csv: Guzang 37 km via the georef seats,
# Jincheng 20 km, Xidu 78 km). NOT 190E's Hexi towns: its "Dunhuang" (ironic_region_hanyang) sits on the real
# Zhangye site and Lude / Jiuquan / Rile / Xihai are packed east of it - anchoring them would bend the real corridor
# onto that compressed layout (round 6 research).
WEST = {"ironic_region_xiping_capital": ("Xidu (Xining)", 36.62, 101.78),
        "3k_main_jincheng_capital": ("Jincheng (Lanzhou)", 36.06, 103.83)}


def affine(lat, lon):
    return np.stack([np.asarray(lon, float), np.asarray(lat, float), np.ones_like(np.asarray(lat, float))], -1) @ M


def _anchors():
    from regions_plan import load
    from hexgrid import centre
    from georef import SEATS
    f, names, w, h = load(ORIG_HEX)
    pts = {}
    for k, (_, lat, lon) in SEATS.items():
        for n in (f"3k_main_{k}_capital", f"3k_dlc06_{k}_capital"):
            if n in names: pts[n] = (lat, lon); break
    for n, (_, lat, lon) in WEST.items(): pts[n] = (lat, lon)
    P, R = [], []
    for n, (lat, lon) in pts.items():
        m = (f["region"] == names.index(n)) & (f["slot"] == 0)
        if not m.any(): continue
        r, c = np.argwhere(m).mean(0); ax, az = centre(int(round(c)), int(round(r)))
        p = affine(lat, lon); P.append(p); R.append((ax - p[0], az - p[1]))
    return np.array(P), np.array(R)


P, R = _anchors()


def corr(wx, wz):
    wx = np.asarray(wx, np.float32); wz = np.asarray(wz, np.float32)
    num_x = np.zeros(wx.shape, np.float32); num_z = np.zeros(wx.shape, np.float32); den = np.full(wx.shape, G0, np.float32)
    for (px, pz), (rx, rz) in zip(P, R):
        g = np.exp(-((wx - px) ** 2 + (wz - pz) ** 2) / np.float32(2 * SIGMA ** 2))
        num_x += g * rx; num_z += g * rz; den += g
    return num_x / den, num_z / den


def to_world(lat, lon):
    p = affine(lat, lon); cx, cz = corr(p[..., 0], p[..., 1]); return p[..., 0] + cx, p[..., 1] + cz


def to_lonlat(wx, wz):
    wx = np.asarray(wx, np.float32); wz = np.asarray(wz, np.float32); px, pz = wx, wz
    for _ in range(3):
        cx, cz = corr(px, pz); px, pz = wx - cx, wz - cz
    ll = (np.stack([px, pz], -1) - M[2]) @ MINV
    return ll[..., 0], ll[..., 1]                        # lon, lat


if __name__ == "__main__":
    print(f"{len(P)} anchors; residual hexes: max {np.hypot(*R.T).max() / 0.7:.0f}, median {np.median(np.hypot(*R.T)) / 0.7:.0f}")
    for n, (s, lat, lon) in WEST.items():
        x, z = to_world(lat, lon); lo, la = to_lonlat(x, z)
        print(f"  {s:18s} world ({float(x):.1f},{float(z):.1f}) round trip lat/lon ({float(la):.2f},{float(lo):.2f})")
