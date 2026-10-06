"""Python prototype of qttoolutility QTU::ProceduralTerrainContent::generate (BOB Vegetation / Procedural Generation),
float32-exact. Input = a frida_veg_procedural.js dump (compiled tables, maps, seed); output = the 3 instance vectors.
Matched BOB's instances bit for bit on r2_tmp_forest (13,046 + 0 + 346).

State per grid cell (u32): low u16 = entry (bits 0-10 group index; 0x7fe = excluded, 0x7ff = free; bits 11-15 object
index inside the group), byte 2 / 3 = x / z jitter (0..255).
Functions (qttoolutility): FUN_180086820 init, FUN_180086d30 pass, FUN_1800870d0 place, FUN_1800872d0 resolve
(keys + std::sort FUN_1800bc8d0, grouping FUN_1800c3dc0/c4830, separation FUN_1800c4030/c4680), FUN_1800ed670 sample,
FUN_1800874d0 choose group, FUN_180087710 group weight, FUN_180087920 choose object, FUN_1800dc460 slope normal.
usage: veg_proc_proto.py <label> [call]"""
import struct, sys
import numpy as np
from veg_dump import dump

F = np.float32
K255 = F(0.003921568859368563)   # 1/255
HALF = F(0.5)
ONE = F(1.0)
THRESH = F(0.05)
HK = F(0.15259021520614624)      # u16 height scale (10000/65535)
HOFF = F(5000.0)
PK = F(0.00015259021893143654)   # 1/65535
TWO_PI = F(6.2831854820251465)
SOBEL = [F(v) for v in (1, 0, -1, 2, 0, -2, 1, 0, -1)]
EXCLUDED, FREE = 0x7FE, 0x7FF


class MT:
    """std::mt19937 drawing raw 32-bit outputs through numpy in blocks."""
    def __init__(self, seed):
        key = np.zeros(624, np.uint32)
        key[0] = seed
        for i in range(1, 624):
            p = int(key[i - 1])
            key[i] = (1812433253 * (p ^ (p >> 30)) + i) & 0xFFFFFFFF
        self.bg = np.random.MT19937()
        self.bg.state = {"bit_generator": "MT19937", "state": {"key": key, "pos": 624}}
        self.buf, self.i, self.n = None, 0, 0

    def u32(self):
        if self.i >= self.n:
            self.buf = self.bg.random_raw(1 << 16).astype(np.uint64).tolist()
            self.i, self.n = 0, len(self.buf)
        v = self.buf[self.i]
        self.i += 1
        return v

    def byte(self):                      # uniform_int_distribution<int>(0, 255): one draw, u % 256
        return self.u32() % 256

    def canonical(self):                 # generate_canonical<float, 24>: one draw, float(u) / 2^32
        return F(F(self.u32()) / F(4294967296.0))

    def uniform01(self):                 # uniform_real_distribution<float>(0, 1): r * (b - a) + a
        return F(F(self.canonical() * F(1.0)) + F(0.0))


class Compiled:
    def __init__(self, d):
        h = d["compiled_header"]
        self.ends = struct.unpack("<8h", h[:16])
        self.aw, self.ah = struct.unpack("<2f", h[0x58:0x60])
        self.nx, self.ny = struct.unpack("<2i", h[0x60:0x68])
        self.pix, self.offx, self.offy, self.ox, self.oz, self.s = (F(v) for v in struct.unpack("<6f", h[0x68:0x80]))
        self.tw, self.th = struct.unpack("<2i", h[0x80:0x88])
        self.cell = F(struct.unpack("<f", h[0x88:0x8c])[0])
        self.inv_unit = F(struct.unpack("<f", h[0xb0:0xb4])[0])
        self.set_tables(d["groups"], d["objects"], [
            (F(struct.unpack_from("<f", p["raw"], 0x1C)[0]), F(struct.unpack_from("<f", p["raw"], 0x24)[0]))
            for p in d["object_params"]])

    def set_tables(self, groups, objects, scales):
        g = groups.astype(np.int64)
        self.g_prob = (g[:, 0] | g[:, 1] << 8).tolist()
        self.g_first = (g[:, 2] | g[:, 3] << 8).tolist()
        self.g_count = g[:, 4].tolist()
        self.g_mask = g[:, 5].tolist()
        self.g_chan = [v - 256 if v > 127 else v for v in g[:, 6].tolist()]
        self.g_b = g[:, 7:10].tolist()
        self.g_h = [(a | b << 8, c | e << 8, f_ | i << 8) for a, b, c, e, f_, i in g[:, 10:16].tolist()]
        self.g_slope = g[:, 16:18].tolist()
        self.g_gp = g[:, 18].tolist()
        self.g_gr = g[:, 19].tolist()
        o = objects.astype(np.int64)
        self.o_prob = o[:, 0].tolist()
        self.o_rad = o[:, 1].tolist()
        self.o_flags = o[:, 2].tolist()
        self.o_b = o[:, 3:6].tolist()
        self.o_h = [(a | b << 8, c | e << 8, f_ | i << 8) for a, b, c, e, f_, i in o[:, 6:12].tolist()]
        self.o_scale = scales


def hval(u):
    return F(F(F(u) * HK) - HOFF)


def falloff(low, high, fall, v):
    """The shared range test: 1 inside [low, high], linear falloff of width `fall` outside, None (0) beyond."""
    f = F(low - v)
    if f <= fall:
        if f <= 0:
            f = F(v - high)
            if f < 0:
                return ONE
            if fall <= f:
                return None
        r = F(ONE - F(f / fall))
        return None if r == 0 else r
    return None


class Gen:
    def __init__(self, d, compiled=None, height=None, blend=None, seed=None):
        self.c = c = compiled or Compiled(d)
        self.height = d["height"] if height is None else height
        self.blend = d["blend"] if blend is None else blend
        self.hw = self.height.shape[1]
        self.hh = self.height.shape[0]
        self.hflat = self.height.ravel().tolist()
        self.bflat = self.blend.reshape(-1, 8)
        if seed is None:
            seed = struct.unpack_from("<I", d["input_raw"], 0x40)[0]
        self.mt = MT(seed)
        n = c.nx * c.ny
        self.entry = [FREE] * n             # FUN_180086820 (no mask and no exclusion polygons in the corpus)
        self.jx = [0] * n
        self.jz = [0] * n
        self.mask = 0
        self.inv_pix = F(ONE / c.pix)

    # ------------------------------------------------------------------ positions (three float orders in BOB)
    def pos_a(self, i):    # FUN_1800e51e0 / c3dc0 / c4030: ((j*k - 0.5) + col) * s + o
        c = self.c
        col, row = i % c.nx, i // c.nx
        x = F(F(F(F(F(self.jx[i]) * K255) - HALF) + F(col)) * c.s) + c.ox
        z = F(F(F(F(F(self.jz[i]) * K255) - HALF) + F(row)) * c.s) + c.oz
        return F(x), F(z)

    def pos_b(self, i):    # FUN_180086d30 / c4680: ((j*k + col) - 0.5) * s + o
        c = self.c
        col, row = i % c.nx, i // c.nx
        x = F(F(F(F(F(self.jx[i]) * K255) + F(col)) - HALF) * c.s) + c.ox
        z = F(F(F(F(F(self.jz[i]) * K255) + F(row)) - HALF) * c.s) + c.oz
        return F(x), F(z)

    def pos_c4830(self, i):  # x = ((j*k + col) - 0.5); z = ((j*k - 0.5) + row)
        c = self.c
        col, row = i % c.nx, i // c.nx
        x = F(F(F(F(F(self.jx[i]) * K255) + F(col)) - HALF) * c.s) + c.ox
        z = F(F(F(F(F(self.jz[i]) * K255) - HALF) + F(row)) * c.s) + c.oz
        return F(x), F(z)

    # ------------------------------------------------------------------ sampling (FUN_1800ed670)
    def sample(self, x, z, slope):
        c = self.c
        fx = F(F(self.inv_pix * x) + c.offx)
        fy = F(F(self.inv_pix * z) + c.offy)
        ix, iy = int(np.floor(fx)), int(np.floor(fy))
        w = self.bflat[iy * self.hw + ix]
        h = F(self.hflat[iy * self.hw + ix])
        nz = F(-1.0)
        if slope:
            nz = self.normal_z(ix, iy)
        return w, h, nz

    def hat(self, x, y):
        x = 0 if x < 0 else (self.hw - 1 if x > self.hw - 1 else x)
        y = 0 if y < 0 else (self.hh - 1 if y > self.hh - 1 else y)
        return F(self.hflat[y * self.hw + x])

    def normal_z(self, x, y):            # FUN_1800dc460 with the Sobel kernels of FUN_1800bf7d0 / bf4e0
        sc = self.c.inv_unit
        ga = F(0.0)
        gb = F(0.0)
        for j in range(3):
            for i in range(3):
                v = F(sc * self.hat(x - 1 + i, y - 1 + j))
                ga = F(ga + F(v * SOBEL[3 * i + j]))
                gb = F(gb + F(v * SOBEL[3 * j + i]))
        ga = F(ga / F(8.0))
        gb = F(gb / F(8.0))
        f4 = ONE
        inv = F(ONE / np.sqrt(F(F(F(gb * gb) + F(ga * ga)) + F(f4 * f4))))
        return F(f4 * inv)

    # ------------------------------------------------------------------ weights
    def group_weight(self, gi, w, h, nz, slope):     # FUN_180087710
        c = self.c
        m = c.g_mask[gi]
        s = F(0.0)
        first = True
        for b in range(8):
            if m & (1 << b):
                s = F(w[b]) if first else F(s + F(w[b]))
                first = False
        lo, hi, fa = c.g_b[gi]
        f5 = F(F(fa) * K255)
        f2 = F(F(F(lo) * K255) - s)
        if f5 < f2:
            return F(0)
        if f2 <= 0:
            f2 = F(s - F(F(hi) * K255))
            f3 = ONE
            if f2 >= 0:
                if f5 <= f2:
                    return F(0)
                f3 = F(ONE - F(f2 / f5))
                if f3 == 0:
                    return F(0)
        else:
            f3 = F(ONE - F(f2 / f5))
            if f3 == 0:
                return F(0)
        f2 = F(0.0)
        if slope:
            smax, smin = c.g_slope[gi]
            if (smax == 0xFF and smin == 0) or (nz <= F(F(smax) * K255) and F(F(smin) * K255) <= nz):
                hl, hh_, hf = c.g_h[gi]
                f4 = hval(hf)
                f5b = F(hval(hl) - h)
                if f5b <= f4:
                    if f5b <= 0:
                        f5b = F(h - hval(hh_))
                        if f5b < 0:
                            return F(F(F(c.g_prob[gi]) * PK) * F(ONE + f3))
                        if f4 <= f5b:
                            return F(0)
                    f2 = F(ONE - F(f5b / f4))
                    if f2 != 0:
                        return F(F(F(c.g_prob[gi]) * PK) * F(f2 + f3))
            return F(0)
        return F(F(F(c.g_prob[gi]) * PK) * F(f2 + f3))

    def choose_group(self, w, h, nz):                 # FUN_1800874d0
        c = self.c
        cands = []
        tot = F(0.0)
        start = 0
        for ch in range(8):
            end = c.ends[ch]
            if THRESH <= F(w[ch]):
                for gi in range(start, end):
                    v = self.group_weight(gi, w, h, nz, True)
                    if v != 0:
                        tot = F(tot + v)
                        cands.append((tot, gi))
            start = end
        if not cands:
            return None
        if len(cands) == 1:
            return cands[0][1]
        r = F(self.mt.uniform01() * tot)
        for cum, gi in cands:                         # first cumulative >= r
            if not (cum < r):
                return gi
        return cands[-1][1]

    def choose_object(self, gi, w, h):                # FUN_180087920
        c = self.c
        cands = []
        tot = F(0.0)
        cw = F(w[c.g_chan[gi]])
        first = c.g_first[gi]
        for k in range(c.g_count[gi]):
            oi = first + k
            if c.o_flags[oi] & self.mask & 0x3F == 0:
                continue
            lo, hi, fa = c.o_b[oi]
            r1 = falloff(F(F(lo) * K255), F(F(hi) * K255), F(F(fa) * K255), cw)
            if r1 is None:
                continue
            hl, hh_, hf = c.o_h[oi]
            r2 = falloff(hval(hl), hval(hh_), hval(hf), h)
            if r2 is None:
                continue
            p = F(F(F(c.o_prob[oi]) * K255) * F(r2 + r1))
            if p != 0:
                tot = F(tot + p)
                cands.append((tot, k))
        if not cands:
            return -1
        if len(cands) == 1:
            return cands[0][1]
        r = F(self.mt.uniform01() * tot)
        for cum, k in cands:
            if not (cum < r):
                return k
        return cands[-1][1]

    # ------------------------------------------------------------------ passes
    def place(self):                                   # FUN_1800870d0
        c = self.c
        for i in range(c.nx * c.ny):
            if self.entry[i] & 0x7FF == EXCLUDED:
                continue
            self.entry[i] = self.entry[i] | 0x7FF
            self.jx[i] = self.mt.byte()
            self.jz[i] = self.mt.byte()
            x, z = self.pos_a(i)
            w, h, nz = self.sample(x, z, True)
            gi = self.choose_group(w, h, nz)
            if gi is not None:
                k = self.choose_object(gi, w, h)
                if k >= 0:
                    self.entry[i] = (gi & 0x7FF) | (k << 11)

    def obj_index(self, e):
        return self.c.g_first[e & 0x7FF] + (e >> 11)

    @staticmethod
    def ceil_div(r, s):
        q = F(r / s)
        t = int(q)
        return t if F(t) == q else t + 1

    def resolve(self):                                 # FUN_1800872d0
        c = self.c
        keys = []
        for i in range(c.nx * c.ny):
            e = self.entry[i]
            if e & 0x7FF < EXCLUDED:
                gi = e & 0x7FF
                oi = c.g_first[gi] + (e >> 11)
                keys.append((c.o_rad[oi] & 0x3F, i % c.nx, self.jx[i], i, c.g_gp[gi], c.g_gr[gi]))
        keys.sort()                                    # strict order: priority, column, x jitter, cell
        for prio, col, jx, i, gp, gr in keys:          # FUN_1800c3dc0: grouping, ascending
            if gp == 0 or gr == 0:
                continue
            e = self.entry[i]
            if e & 0x7FF >= EXCLUDED:
                continue
            if not (self.mt.uniform01() <= F(F(gp) * K255)):
                continue
            gi = e & 0x7FF
            r = F(gr)
            r2 = F(r * r)
            px, pz = self.pos_a(i)
            ir = self.ceil_div(r, c.s)
            row = i // c.nx
            x0, y0 = max(col - ir, 0), max(row - ir, 0)
            x1, y1 = min(col + 1 + ir, c.nx), min(row + 1 + ir, c.ny)
            for yy in range(y0, y1):
                for xx in range(x0, x1):
                    if xx == col and yy == row:
                        continue
                    j = yy * c.nx + xx
                    ej = self.entry[j] & 0x7FF
                    if ej < EXCLUDED and ej != (self.entry[i] & 0x7FF):
                        qx, qz = self.pos_c4830(j)
                        dz = F(pz - qz)
                        d2 = F(F(dz * dz) + F(F(px - qx) * F(px - qx)))
                        if d2 <= r2:
                            w, h, nz = self.sample(qx, qz, False)
                            if THRESH <= F(w[c.g_chan[gi]]):
                                if self.group_weight(gi, w, h, nz, False) != 0:
                                    k = self.choose_object(gi, w, h)
                                    if k >= 0:
                                        self.entry[j] = (self.entry[i] & 0x7FF) | (k << 11)
        for prio, col, jx, i, gp, gr in reversed(keys):  # FUN_1800c4030: separation, descending
            e = self.entry[i]
            if e & 0x7FF >= EXCLUDED:
                continue
            gi = e & 0x7FF
            oi = self.obj_index(e)
            r = F(c.o_rad[oi])
            if r == 0:
                continue
            ch = c.g_chan[gi]
            r2 = F(r * r)
            flag = c.o_flags[oi] >> 7
            px, pz = self.pos_a(i)
            ir = self.ceil_div(r, c.s)
            row = i // c.nx
            x0, y0 = max(col - ir, 0), max(row - ir, 0)
            x1, y1 = min(col + 1 + ir, c.nx), min(row + 1 + ir, c.ny)
            for yy in range(y0, y1):
                for xx in range(x0, x1):
                    j = yy * c.nx + xx
                    if j == i:
                        continue
                    ej = self.entry[j]
                    if ej & 0x7FF >= EXCLUDED:
                        continue
                    qx, qz = self.pos_b(j)
                    dx = F(px - qx)
                    dz = F(pz - qz)
                    thr = r2
                    if flag == 0:
                        oj = self.obj_index(ej)
                        if c.o_flags[oj] & 0x80:
                            t = F(c.o_rad[oj])
                            thr = F(t * t)
                    if F(F(dz * dz) + F(dx * dx)) <= thr and c.g_chan[ej & 0x7FF] == ch:
                        self.entry[j] = ej | 0x7FF

    def emit(self):                                    # the end of FUN_180086d30
        c = self.c
        out = []
        for i in range(c.nx * c.ny):
            e = self.entry[i]
            if e & 0x7FF < EXCLUDED:
                oi = self.obj_index(e)
                if c.o_flags[oi] & 0x40:
                    continue
                x, z = self.pos_b(i)
                lo, rng = c.o_scale[oi]
                sc = F(F(self.mt.uniform01() * rng) + lo)
                rot = F(self.mt.uniform01() * TWO_PI)
                out.append((oi, x, z, sc, rot))
        return out

    def run_pass(self, mask):
        self.mask = mask
        self.place()
        self.resolve()
        return self.emit()

    def run(self):
        return [self.run_pass(m) for m in (0x33, 4, 8)]


def compare(mine, theirs, name):
    n = min(len(mine), len(theirs))
    for k in range(n):
        a = mine[k]
        b = theirs[k]
        if a[0] != b["obj"] or a[1] != b["x"] or a[2] != b["z"] or a[3] != b["scale"] or a[4] != b["rot"]:
            print(f"{name}: first difference at {k}: mine {a} bob {tuple(b)}")
            return False
    if len(mine) != len(theirs):
        print(f"{name}: count mine {len(mine)} bob {len(theirs)}")
        return False
    print(f"{name}: identical ({n})")
    return True


if __name__ == "__main__":
    d = dump(sys.argv[1])[int(sys.argv[2]) if len(sys.argv) > 2 else 0]
    g = Gen(d)
    for p, m in enumerate((0x33, 4, 8)):
        compare(g.run_pass(m), d["instances"][p], f"pass {p} (mask {m:#x})")
