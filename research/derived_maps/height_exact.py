"""BOB's exact lf height at a world point (WARSCAPE::TERRAIN_RENDER_SETUP::get_height_worker + FUN_1803a1e30)."""
import math

import numpy as np

f32 = np.float32


def floor_f(v):
    """int(v) rounded toward -inf, as the SSE code does (trunc, minus 1 for negative non-integers)."""
    i = int(v)
    if f32(i) != v and v < 0:
        i -= 1
    return f32(i)


class LfSampler:
    def __init__(self, raw_u16, maxx, maxz, minx=f32(0), minz=f32(0), scale=f32(5500), offset=f32(1200), tile=None):
        self.raw = raw_u16
        self.H, self.W = raw_u16.shape
        self.minx, self.minz, self.maxx, self.maxz = f32(minx), f32(minz), f32(maxx), f32(maxz)
        self.rx = f32(f32(1) / f32(self.W))
        self.ry = f32(f32(1) / f32(self.H))
        tile = f32(595.1) / f32(1784) if tile is None else f32(tile)
        self.f = f32(f32(f32(1.0) / f32(128.0)) * tile)
        self.scale, self.offset = f32(scale), f32(offset)
        self.inv = f32(1.0 / 65535)

    def value(self, col, row):
        return f32(f32(self.raw[row, col]) * self.inv)

    def sample01(self, x, z):
        u = f32(f32(x - self.minx) / f32(self.maxx - self.minx))
        v = f32(f32(1) - f32(f32(z - self.minz) / f32(self.maxz - self.minz)))
        W, H = f32(self.W), f32(self.H)
        fx = f32(u * W); fy = f32(v * H)
        x0 = floor_f(fx); y0 = floor_f(fy)
        fyu = f32(f32(v - self.ry) * H)     # row above
        fxr = f32(f32(u + self.rx) * W)     # column right
        cl = lambda a, hi: f32(0) if a < 0 else (hi if a > hi else a)
        wm, hm = f32(self.W - 1), f32(self.H - 1)
        A = self.value(int(cl(fx, wm)), int(cl(fyu, hm)))
        B = self.value(int(cl(fxr, wm)), int(cl(fyu, hm)))
        top = f32(f32(f32(B - A) * f32(fx - x0)) + A)
        C = self.value(int(cl(fx, wm)), int(cl(fy, hm)))
        D = self.value(int(cl(fxr, wm)), int(cl(fy, hm)))
        bot = f32(f32(f32(D - C) * f32(fx - x0)) + C)
        return f32(f32(f32(bot - top) * f32(fy - y0)) + top)

    def height(self, x, z):
        l = self.sample01(f32(x), f32(z))
        return f32(f32(f32(l * self.scale) * self.f) - f32(self.f * self.offset))


if __name__ == '__main__':
    import merger_proto as M
    v_ref, idx_ref, bb = M.read_mesh(0)
    raw = np.frombuffer(open(M.V + r"\lf_height_map.dds", 'rb').read(), '<u2', offset=128, count=7136 * 5620).reshape(5620, 7136)
    V = v_ref[:4014]
    tile = f32(595.1) / f32(1784)
    for name, (mx, mz) in {
        '595.1 x 1405*tile': (f32(595.1), f32(f32(1405) * tile)),
        '1784*tile x 1405*tile': (f32(f32(1784) * tile), f32(f32(1405) * tile)),
        'dbl 595.1 x 5620*595.1/7136': (f32(595.1), f32(5620 * 595.1 / 7136)),
        '595.1 x f32(5620*px)': (f32(595.1), f32(f32(5620) * f32(f32(595.1) / f32(7136)))),
    }.items():
        s = LfSampler(raw, mx, mz, tile=tile)
        ys = np.array([s.height(x, z) for x, _, z in V], np.float32)
        d = np.abs(ys - V[:, 1])
        print(f'{name:32s} exact {int((d == 0).sum())}/{len(V)}  max {d.max():.2e}')
