#!/usr/bin/env python3
"""Radial Central Plains warp (round 6 candidate): the Central Plains grow, the rest keeps its shape.

Box (190E hex cols/rows) from Runan (476,394) in the south to Dongjun (514,513) in the north, Luoyang (430) to
Xiapi (556) west-east, with a margin. Inside the box's ellipse the map is magnified K; outside, every point is pushed
straight out from the centre by the same distance the ellipse edge moved (so sizes stay ~1 and the skew is small and
spread thin), then the whole map may be scaled uniformly by S (the hybrid: S*K_bubble = K overall in the Central
Plains, no stretching anywhere - uniform scaling keeps shapes).
Same interface as warp.Warp: forward/inverse in 190E hex units <-> new hex units, W/H = new size (multiples of 4),
west/north padding added after the warp (in new hexes).
"""
import numpy as np
from warp import W0, H0

BOX = (415, 572, 380, 525)          # cols c0..c1, rows r0..r1: Luoyang/Yingchuan .. Xiapi, Runan .. Dongjun


class RadialWarp:
    def __init__(self, k=1.6, scale=1.0, west=128, north=48, box=BOX):
        self.k, self.s = k / scale, scale                  # bubble magnification, uniform scale
        c0, c1, r0, r1 = box
        self.cx, self.cy = (c0 + c1) / 2, (r0 + r1) / 2
        self.ax, self.ay = (c1 - c0) / 2, (r1 - r0) / 2      # ellipse inscribed in the box (Runan .. Dongjun inside)
        xs = np.array([0, W0 - 1, 0, W0 - 1] + list(np.linspace(0, W0 - 1, 64)) * 2 + [0] * 64 + [W0 - 1] * 64, float)
        ys = np.array([0, 0, H0 - 1, H0 - 1] + [0] * 64 + [H0 - 1] * 64 + list(np.linspace(0, H0 - 1, 64)) * 2, float)
        bx, by = self._bubble(xs, ys)
        self.ox, self.oy = -bx.min() * self.s, -by.min() * self.s          # shift so the old map starts at 0
        self.west, self.north = west * self.s, north * self.s
        w = (bx.max() - bx.min()) * self.s + self.west; h = (by.max() - by.min()) * self.s + self.north
        self.W, self.H = int(4 * np.ceil(w / 4)), int(4 * np.ceil(h / 4))

    def _bubble(self, x, y):
        u, v = (x - self.cx) / self.ax, (y - self.cy) / self.ay; r = np.hypot(u, v) + 1e-12
        rn = np.where(r <= 1, self.k * r, r + (self.k - 1))
        return self.cx + u / r * rn * self.ax, self.cy + v / r * rn * self.ay

    def forward(self, x, y):
        bx, by = self._bubble(np.asarray(x, float), np.asarray(y, float))
        return bx * self.s + self.ox + self.west, by * self.s + self.oy

    def inverse(self, nx, ny):
        bx = (np.asarray(nx, float) - self.west - self.ox) / self.s; by = (np.asarray(ny, float) - self.oy) / self.s
        u, v = (bx - self.cx) / self.ax, (by - self.cy) / self.ay; rn = np.hypot(u, v) + 1e-12
        r = np.where(rn <= self.k, rn / self.k, rn - (self.k - 1))
        return self.cx + u / rn * r * self.ax, self.cy + v / rn * r * self.ay
