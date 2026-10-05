"""Try variants of the u/v computation in BOB's lf sampler against vanilla land_mesh_0 heights."""
import itertools

import numpy as np

import height_exact as HX
import merger_proto as M

f32 = np.float32
v_ref, idx_ref, bb = M.read_mesh(0)
raw = np.frombuffer(open(M.V + r"\lf_height_map.dds", 'rb').read(), '<u2', offset=128, count=7136 * 5620).reshape(5620, 7136)
tile = f32(595.1) / f32(1784)
V = v_ref[:4014]
ok = np.round(V[:, 2] / float(M.CELL)).astype(int) >= 2
Vs = V[ok]
maxx = f32(595.1)
maxz = f32(f32(1405) * tile)


class Variant(HX.LfSampler):
    def __init__(self, uv_mode, **kw):
        super().__init__(raw, maxx, maxz, tile=tile, **kw)
        self.uv_mode = uv_mode
        self.irx = f32(f32(1) / f32(self.maxx - self.minx))
        self.irz = f32(f32(1) / f32(self.maxz - self.minz))

    def sample01(self, x, z):
        if self.uv_mode == 'div':
            u = f32(f32(x - self.minx) / f32(self.maxx - self.minx)); v = f32(f32(1) - f32(f32(z - self.minz) / f32(self.maxz - self.minz)))
        elif self.uv_mode == 'recip':
            u = f32(f32(x - self.minx) * self.irx); v = f32(f32(1) - f32(f32(z - self.minz) * self.irz))
        elif self.uv_mode == 'maxz-z':
            u = f32(f32(x - self.minx) / f32(self.maxx - self.minx)); v = f32(f32(self.maxz - z) / f32(self.maxz - self.minz))
        W, H = f32(self.W), f32(self.H)
        fx = f32(u * W); fy = f32(v * H)
        x0 = HX.floor_f(fx); y0 = HX.floor_f(fy)
        fyu = f32(f32(v - self.ry) * H); fxr = f32(f32(u + self.rx) * W)
        cl = lambda a, hi: f32(0) if a < 0 else (hi if a > hi else a)
        wm, hm = f32(self.W - 1), f32(self.H - 1)
        A = self.value(int(cl(fx, wm)), int(cl(fyu, hm))); B = self.value(int(cl(fxr, wm)), int(cl(fyu, hm)))
        top = f32(f32(f32(B - A) * f32(fx - x0)) + A)
        C = self.value(int(cl(fx, wm)), int(cl(fy, hm))); D = self.value(int(cl(fxr, wm)), int(cl(fy, hm)))
        bot = f32(f32(f32(D - C) * f32(fx - x0)) + C)
        return f32(f32(f32(bot - top) * f32(fy - y0)) + top)


for mode in ('div', 'recip', 'maxz-z'):
    s = Variant(mode)
    ys = np.array([s.height(x, z) for x, _, z in Vs], np.float32)
    d = np.abs(ys - Vs[:, 1])
    ulp = d / np.spacing(np.abs(Vs[:, 1]))
    print(f'{mode:8s} exact {int((d == 0).sum())}/{len(Vs)}  2ulp {int(((ulp > 1.5) & (ulp < 2.5)).sum())}')
