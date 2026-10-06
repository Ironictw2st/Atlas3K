"""Prototype of BOB's battle grass generation (bob_vegetation FUN_180003690 -> qttoolutility QTU::generate_grass /
FUN_1800788c0), float32 per operation, compared with a corpus <climate>.grass_list.bin.
usage: grass_proto.py <corpus project dir> [--run bob_run1] [--limit N]"""
import glob, os, struct, sys, re
import xml.etree.ElementTree as ET
import numpy as np
import tifffile

F = np.float32
M64 = (1 << 64) - 1
SPEC = r"Z:/Claude/BattleMaps/out/grass_ref/terrain.pack/terrain/vegetation/battle/grass/grass_generation_spec.xml"


def u2f(u): return np.frombuffer(struct.pack("<I", u), np.float32)[0]


# ---------------------------------------------------------------- BOB sin (QtuTransform.Sin / FUN_180590110)
def bob_sin(x):
    x = F(x)
    ax = F(abs(x))
    t = F(ax * u2f(0x3ea2f983) + F(12582912.0))
    n = F(t - F(12582912.0))
    r = F(ax - F(u2f(0x40490000) * n))
    r = F(r - F(u2f(0x3a7da000) * n))
    r = F(r - F(u2f(0x34222000) * n))
    r = F(r - F(u2f(0x2cb4611a) * n))
    r2 = F(r * r)
    if struct.unpack("<I", struct.pack("<f", t))[0] & 1: r = F(-r)
    p = F(F(F(F(F(F(u2f(0x362edef8) * r2) + u2f(0xb94fb7ff)) * r2) + u2f(0x3c088766)) * r2) + u2f(0xbe2aaaa6))
    s = F(r + F(F(r2 * p) * r))
    return F(-s) if np.signbit(x) else s


def bob_sincos(x):
    x = F(x)
    if abs(x) < F(1.22070313e-4): return x, F(1.0)
    return bob_sin(x), bob_sin(F(abs(x) + F(1.57079637)))


# ---------------------------------------------------------------- spec
def load_spec(path=SPEC):
    root = ET.parse(path).getroot()
    default_density = F(float(root.findtext("default_density")))
    default_thr = F(float(root.findtext("default_blendmap_value_treshold")))
    model_paths, model_specs, textures = [], [], {}
    for tex in root.find("grass_types").findall("texture"):
        name = tex.get("val").strip()
        thr = tex.get("treshold")
        climates = {}
        for cl in tex.findall("climate"):
            first = len(model_specs)
            for m in cl.findall("model"):
                p = m.text.strip()
                if p not in model_paths: model_paths.append(p)
                model_specs.append((model_paths.index(p), F(float(m.get("alpha_mul", 0))), F(float(m.get("alpha_add", 0))),
                                    F(float(m.get("far_addition", 0)))))
            d = cl.findtext("density")
            dens = F(float(d)) if d is not None else F(-1.0)
            for c in cl.get("values").split(","):
                climates[c.strip()] = (first, len(model_specs) - first, dens)
        entry = textures.setdefault(name, {"thr": None, "climates": {}})
        if thr is not None: entry["thr"] = F(float(thr))
        entry["climates"].update(climates)
    return dict(default_density=default_density, default_thr=default_thr, paths=model_paths, specs=model_specs,
                textures=textures)


def climate_spec(spec, climate, texture):
    t = spec["textures"].get(texture)
    if t is None: return None
    c = t["climates"].get(climate) or t["climates"].get("*")
    if c is None: return None
    first, count, dens = c
    if dens < 0: dens = spec["default_density"]
    return first, count, dens


def texture_threshold(spec, texture):
    if not texture: return F(0.0)
    t = spec["textures"].get(texture)
    if t is None: return spec["default_thr"]
    return t["thr"] if t["thr"] is not None else F(0.0)


# ---------------------------------------------------------------- transforms (6 floats: X = m0 x + m1 y + m4, Y = m2 x + m3 y + m5)
def compose(p2, p3):  # FUN_1800d6110(out, p2, p3)
    f11, f12, f13, f14, f5, f7 = p2[0], p2[1], p2[2], p2[3], p2[4], p2[5]
    f1, f3, f2, f4, f10, f9 = p3[0], p3[1], p3[2], p3[3], p3[4], p3[5]
    return [F(F(f1 * f11) + F(f3 * f13)), F(F(f1 * f12) + F(f3 * f14)), F(F(f4 * f13) + F(f2 * f11)),
            F(F(f4 * f14) + F(f2 * f12)), F(F(f10 + F(f1 * f5)) + F(f3 * f7)), F(F(F(f4 * f7) + F(f2 * f5)) + f9)]


def invert(p):  # FUN_1800e5480
    f9 = F(F(1.0) / F(F(p[0] * p[3]) - F(p[1] * p[2])))
    f7 = F(-F(f9 * p[1])); f8 = F(-F(f9 * p[2])); f10 = F(f9 * p[0])
    return [F(f9 * p[3]), f7, f8, f10, F(-F(F(f7 * p[5]) + F(F(f9 * p[3]) * p[4]))), F(-F(F(f10 * p[5]) + F(f8 * p[4])))]


def terrain_map_to_world(density, cell, flag=True):
    s0 = F(density)
    t = F(s0 + F(1.0)) if flag else s0
    sc = F(s0 / F(cell))
    m = compose([sc, F(0), F(0), sc, F(0), F(0)], [F(1), F(0), F(0), F(1), t, t])
    m = invert(m)
    if not flag: m = compose([F(1), F(0), F(0), F(1), F(0.5), F(0.5)], m)
    return m


def cell_to_world(h, cell, g0=F(0), g1=F(0)):
    t = [F(1), F(0), F(-0.0), F(-1.0), g0, g1]
    t5 = t[5]
    t[5] = F(F(t[4] * F(0)) + F(F(-1.0) * t5)); t[4] = F(F(F(1.0) * t[4]) + F(t5 * F(0))) + F(0); t[5] = F(t[5] + F(0))
    t5 = t[5]
    t[5] = F(F(F(0) * t[4]) + F(F(1) * t[5])); t[4] = F(F(F(1) * t[4]) + F(F(0) * t5)) + F(0); t[5] = F(F(h) + t[5])
    c = F(cell)
    return [F(c * t[0]), F(c * t[1]), F(c * t[2]), F(c * t[3]), F(c * t[4]), F(c * t[5])]


def floor_i(v):  # cvttss2si + movmskps fix
    i = int(v)
    if float(i) != float(v) and v < 0: i -= 1
    return i


def ceil_i(v):
    i = int(v)
    if float(i) != float(v) and v > 0: i += 1
    return i


# ---------------------------------------------------------------- RNG
class Xoro:
    def __init__(self, seed):
        s0 = s1 = seed & M64
        if seed == 0: s0, s1 = 0x33001294d9708f82, 0xa524c8b000000004
        self.s0, self.s1 = s0, s1
        self._step()

    def _step(self):
        s0, s1 = self.s0, self.s1
        s1 ^= s0
        self.s0 = (((s0 >> 9) | (s0 << 55)) & M64) ^ s1 ^ ((s1 << 14) & M64)
        self.s1 = ((s1 >> 28) | (s1 << 36)) & M64

    def next(self):
        r = (self.s0 + self.s1) & M64
        self._step()
        return r


def generate(weights, tex_names, spec, climate, seed, cells_w=8, cells_h=8, density=128, cell=256.0, masked=(), excluded=None):
    """weights: (H, W, C) float32 in 0..1, indexed [y][x][c]. Returns list of (x, z, model index)."""
    H, W, C = weights.shape
    rng = Xoro(seed)
    c = F(cell)
    aabb = (F(-c), F(-c), F(F(cells_w + 1) * c), F(F(cells_h + 1) * c))
    width, height = F(aabb[2] - aabb[0]), F(aabb[3] - aabb[1])
    tmw = terrain_map_to_world(density, cell, True)
    m2c = compose(tmw, invert(cell_to_world(cells_h, cell)))
    half = F(0.5)
    thr = [texture_threshold(spec, n) for n in tex_names]
    out = []
    for x in range(W):
        fx = F(x)
        lf8 = F(m2c[0] * F(fx + half)); lfc = F(m2c[2] * F(fx + half))
        for y in range(H):
            fy = F(y)
            cx = F(F(m2c[4] + F(m2c[1] * F(fy + half))) + lf8)
            cy = F(F(m2c[5] + F(m2c[3] * F(fy + half))) + lfc)
            ci, cj = floor_i(cx), floor_i(cy)
            if not (0 <= ci < cells_w and 0 <= cj < cells_h) or (ci, cj) in masked: continue
            w = weights[y, x]
            order = sorted(range(C), key=lambda k: -w[k])  # FUN_1800bbae0: insertion sort, descending, stable
            ti = -1
            for k in order:
                if thr[k] < w[k]: ti = k; break
            if ti < 0: continue
            cs = climate_spec(spec, climate, tex_names[ti])
            if cs is None: continue
            first, count, dens = cs
            if not dens >= 0: continue
            s = F(F(1.0) / F(np.sqrt(dens)))
            inv = F(F(1.0) / s)
            x1, y1 = F(x + 1), F(y + 1)
            xe = F(F(tmw[4] + F(tmw[1] * y1)) + F(tmw[0] * x1))
            ze = F(F(tmw[5] + F(tmw[3] * y1)) + F(tmw[2] * x1))
            off_x = F(F(width - F(F(floor_i(F(inv * width))) * s)) * half)
            off_z = F(F(height - F(F(floor_i(F(inv * height))) * s)) * half)
            vx = F(F(F(F(F(tmw[4] + F(tmw[0] * fx)) + F(tmw[1] * fy)) - off_x) - aabb[0]) * inv)
            gx = F(F(F(F(ceil_i(vx)) * s) + aabb[0]) + off_x)
            vz = F(F(F(F(F(tmw[5] + F(tmw[3] * fy)) + F(tmw[2] * fx)) - off_z) - aabb[1]) * inv)
            gz0 = F(F(F(F(ceil_i(vz)) * s) + aabb[1]) + off_z)
            while gx < xe:
                if gz0 < ze:
                    gz = gz0
                    while True:
                        ra = rng.next(); rb = rng.next()
                        a = F(F((rb >> 48) & 0xffff) * u2f(0x37800080))
                        ang = F(F((ra >> 48) & 0xffff) * u2f(0x38c910a4))
                        sn, cs_ = bob_sincos(ang)
                        px = F(F(F(F(cs_ * a) * s) * half) + gx)
                        pz = F(F(F(F(sn * a) * s) * half) + gz)
                        if excluded is not None and excluded(px, pz):
                            gz = F(gz + s)
                            if not gz < ze: break
                            continue
                        r = rng.next(); v = r >> 32
                        lim = 0xffffffff % count
                        while v <= lim:
                            r = rng.next(); v = r >> 32
                        out.append((px, pz, v % count + first))
                        gz = F(gz + s)
                        if not gz < ze: break
                gx = F(gx + s)
    return out


def bob_half(v):
    """bob_vegetation FUN_1800ceee0: float -> half bits (its own rounding: m += (m - 1) & m & 0x1fff)."""
    u = struct.unpack("<I", struct.pack("<f", float(F(v))))[0]
    sign = (u >> 16) & 0x8000
    e = (u >> 23) & 0xff
    if e > 0x8e: return sign | 0x7c00
    m = u & 0x7fffffff
    if e > 0x70:
        m = (m + ((m - 1) & m & 0x1fff)) & 0xffffffff
        return (((m >> 13) & 0x3ff) | ((((m >> 23) + 0x10) * 0x400) & 0xffff) | sign) & 0xffff
    if e > 0x66:
        b = (e + 0x99) & 0xff
        mm = u & 0x7fffff
        if ((mm << (b & 0x1f)) & 0x3fffff) > 0x200:
            t = (0x7fffff >> (b & 0x1f)) & mm
            mm = (mm + ((t - 1) & t)) & 0xffffffff
        mm = (mm + 0x800000) >> ((0x7e - e) & 0x1f)
        return ((mm & 0xffff) | sign) & 0xffff
    return sign | 1 if m > 0x33000400 else sign


def read_grass_list(path):
    d = open(path, "rb").read()
    n, = struct.unpack_from("<I", d, 10); o = 14
    models = []
    for _ in range(n):
        v, L = struct.unpack_from("<HH", d, o); o += 4
        s = d[o:o + L].decode(); o += L
        am, aa, fa, cnt = struct.unpack_from("<fffI", d, o); o += 16
        r = np.frombuffer(d, np.float16, cnt * 3, o).reshape(-1, 3); o += cnt * 6
        models.append((s, (am, aa, fa), r))
    return models


def blend_weights(raw):
    """QTU TerrainMap::data_composited for a Blend8 map: channel c = v * (1/255); channel 0 then gets 1 - sum (sum in
    channel order), so an unpainted pixel is all channel 0 (Frida dump of the Array3, 100% of texels)."""
    w = raw.astype(np.float32) * F(F(1.0) / F(255.0))
    tot = np.zeros(raw.shape[:2], np.float32)
    for c in range(raw.shape[2]): tot = (tot + w[..., c]).astype(np.float32)
    w[..., 0] = (w[..., 0] + (F(1.0) - tot).astype(np.float32)).astype(np.float32)
    return w


def project_inputs(proj):
    terry = glob.glob(os.path.join(proj, "src", "tile", "*.terry"))[0]
    txt = open(terry, encoding="utf-8").read()
    tex = [re.search(rf'texture_channel_{i}="([^"]*)"', txt).group(1) for i in range(8)]
    climates = [c for c in re.search(r'climate_mask="([^"]*)"', txt).group(1).split(",") if c]
    seed = int(re.search(r'grass_seed="(\d+)"', txt).group(1))
    blend = glob.glob(os.path.join(proj, "src", "tile", "*.blend.*.tif"))[0]
    raw = tifffile.imread(blend)
    w = blend_weights(raw)
    height = tifffile.imread(glob.glob(os.path.join(proj, "src", "tile", "*.height.*.tif"))[0]).astype(np.float32)
    return tex, climates, seed, w, height


def grass_list_bytes(points, spec, height, density=128, cell=256.0):
    """The writer (bob_vegetation FUN_180003690 + EMPIREUTILITY::GRASS_LIST::save)."""
    import grass_order as go
    k = F(F(1.0) / F(F(F(cell) / F(density)) * F(1.0)))
    off = F(density)
    hw = height.shape[1]
    groups = {}
    m = go.CaHashMap(lambda key: go.desc_hash(key[0], go.fbits(key[1]), go.fbits(key[2]), go.fbits(key[3])))
    for x, z, mi in points:
        if not (F(0) <= x and F(0) <= z and x < F(2048) and z < F(2048)): continue
        row = int(F(F(z * k) + off)); col = int(F(off + F(k * x)))
        if not (row * hw + col < height.size): continue
        y = height[row, col]
        p, am, aa, fa = spec["specs"][mi]
        key = (spec["paths"][p], am, aa, fa)
        m.insert(key)
        groups.setdefault(key, []).append((bob_half(x), bob_half(y), bob_half(z)))
    out = bytearray(b"FASTBIN0") + struct.pack("<HI", 2, len(m.items))
    for key in m.items:
        s = key[0].encode("latin1")
        out += struct.pack("<HH", 1, len(s)) + s + struct.pack("<fffI", key[1], key[2], key[3], len(groups[key]))
        for a, b, c in groups[key]: out += struct.pack("<HHH", a, b, c)
    return bytes(out)


if __name__ == "__main__":
    proj = sys.argv[1]
    run = sys.argv[sys.argv.index("--run") + 1] if "--run" in sys.argv else "bob_run1"
    tex, climates, seed, w, height = project_inputs(proj)
    spec = load_spec()
    print("textures", tex, "climates", climates, "seed", seed)
    for climate in climates:
        ref_path = os.path.join(proj, run, "tile", f"{climate}.grass_list.bin")
        pts = generate(w, tex, spec, climate, seed)
        data = grass_list_bytes(pts, spec, height)
        if not os.path.exists(ref_path):
            print(climate, "no reference;", "native has", len(pts), "points"); continue
        ref = open(ref_path, "rb").read()
        same = data == ref
        diff = next((i for i in range(min(len(data), len(ref))) if data[i] != ref[i]), None)
        print(climate, "IDENTICAL" if same else f"DIFFERS at {diff} (native {len(data)} vs BOB {len(ref)})")
