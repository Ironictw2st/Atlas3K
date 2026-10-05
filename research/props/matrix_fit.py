"""Fit BOB's euler->matrix float32 arithmetic against record matrices (budugen_capital.0.17 sample)."""
import numpy as np, struct, math
F = np.float32
rows = [
 ("AAEA83BD00000000DF9EA1BE0000000077F3A43E00000000DF9EA13E00000000AAEA83BD", 101.533043, (0.322169989,)*3),
 ("656AA0BE000000005CA899BD0000000077F3A43E000000005CA8993D00000000656AA0BE", 166.533066, (0.322169989,)*3),
 ("54CCA4BE00000000773263BC0000000077F3A43E000000007732633C0000000054CCA4BE", 177.533051, (0.322169989,)*3),
 ("735B92BE00000000CA2918BE0000000077F3A43E00000000CA29183E00000000735B92BE", 152.533005, (0.322169989,)*3),
 ("B0F77E3E00000000F7FC043B000000003CF77E3E00000000F7FC04BB00000000B0F77E3E", -0.466939986, (0.248999998, 0.248989999, 0.248999998)),
 ("F41B863E00000000199FA73C000000008C84863E00000000199FA7BC00000000F41B863E", -4.46676016, (0.262730002,)*3),
]
def bob(h): return np.frombuffer(bytes.fromhex(h), "<f4")
def sx(v): return [hex(np.float32(x).view(np.uint32)) for x in v]
cands = {}
def c_double(a, s):  # native: double then cast
    r = math.radians(a); return F(math.cos(r) * s[0]), F(-math.sin(r) * s[0]), F(math.sin(r) * s[2])
def c_f32(a, s):
    r = F(a) * F(math.pi / 180); c = F(math.cos(F(r))); si = F(math.sin(F(r)))
    return F(c * F(s[0])), F(-si * F(s[0])), F(si * F(s[2]))
def c_f32b(a, s):
    r = F(F(a) * F(math.pi)) / F(180); c = F(math.cos(r)); si = F(math.sin(r))
    return F(c * F(s[0])), F(-si * F(s[0])), F(si * F(s[2]))
def c_quat(a, s):
    r = F(a) * F(math.pi / 180); h = F(r * F(0.5)); qy = F(math.sin(h)); qw = F(math.cos(h))
    m00 = F(F(1) - F(F(2) * F(qy * qy))); m02 = F(F(2) * F(qy * qw))  # y-rot: m02 = 2(xz+wy) = 2wy ; m20 = -2wy
    return F(m00 * F(s[0])), F(-m02 * F(s[0])), F(m02 * F(s[2]))
def c_quat2(a, s):
    r = F(a) * F(math.pi / 180); h = F(r * F(0.5)); qy = F(math.sin(h)); qw = F(math.cos(h))
    yy = F(qy * qy); m00 = F(F(1) - F(yy + yy)); wy = F(qw * qy); m02 = F(wy + wy)
    return F(m00 * F(s[0])), F(-m02 * F(s[0])), F(m02 * F(s[2]))
def c_quat3(a, s):  # with normalisation of quaternion, ww-yy form
    r = F(a) * F(math.pi / 180); h = F(r * F(0.5)); qy = F(math.sin(h)); qw = F(math.cos(h))
    m00 = F(F(qw * qw) - F(qy * qy)); wy = F(qw * qy); m02 = F(wy + wy)
    return F(m00 * F(s[0])), F(-m02 * F(s[0])), F(m02 * F(s[2]))
def c_quat_d(a, s):  # double half angle, float quat
    h = math.radians(a) / 2; qy = F(math.sin(h)); qw = F(math.cos(h))
    yy = F(qy * qy); m00 = F(F(1) - F(yy + yy)); wy = F(qw * qy); m02 = F(wy + wy)
    return F(m00 * F(s[0])), F(-m02 * F(s[0])), F(m02 * F(s[2]))
for name, fn in [("double", c_double), ("f32", c_f32), ("f32b", c_f32b), ("quat", c_quat), ("quat2", c_quat2), ("quat3", c_quat3), ("quat_d", c_quat_d)]:
    ok = 0
    for h, a, s in rows:
        b = bob(h); m0, m2, m6 = fn(a, s)
        good = (F(m0).view(np.uint32), F(m2).view(np.uint32), F(m6).view(np.uint32)) == (b[0].view(np.uint32), b[2].view(np.uint32), b[6].view(np.uint32))
        ok += good
    print(name, ok, "/", len(rows))

# Qt5 QQuaternion::fromEulerAngles(pitch=x, yaw=y, roll=z) + toRotationMatrix / QMatrix4x4::rotate, then column scale
D2R = F(math.pi / 180)
def qt_quat(rx, ry, rz):
    p = F(F(rx) * D2R) * F(0.5); y = F(F(ry) * D2R) * F(0.5); r = F(F(rz) * D2R) * F(0.5)
    c1, s1 = F(math.cos(y)), F(math.sin(y)); c2, s2 = F(math.cos(r)), F(math.sin(r)); c3, s3 = F(math.cos(p)), F(math.sin(p))
    c1c2 = F(c1 * c2); s1s2 = F(s1 * s2)
    w = F(F(c1c2 * c3) + F(s1s2 * s3)); x = F(F(c1c2 * s3) + F(s1s2 * c3))
    yq = F(F(F(s1 * c2) * c3) - F(F(c1 * s2) * s3)); z = F(F(F(c1 * s2) * c3) - F(F(s1 * c2) * s3))
    return w, x, yq, z
def to_rot(q):
    w, x, y, z = q
    f2x, f2y, f2z = F(x * F(2)), F(y * F(2)), F(z * F(2))
    f2xw, f2yw, f2zw = F(f2x * w), F(f2y * w), F(f2z * w)
    f2xx, f2xy, f2xz = F(f2x * x), F(f2x * y), F(f2x * z)
    f2yy, f2yz, f2zz = F(f2y * y), F(f2y * z), F(f2z * z)
    return [[F(F(1) - F(f2yy + f2zz)), F(f2xy - f2zw), F(f2xz + f2yw)],
            [F(f2xy + f2zw), F(F(1) - F(f2xx + f2zz)), F(f2yz - f2xw)],
            [F(f2xz - f2yw), F(f2yz + f2xw), F(F(1) - F(f2xx + f2yy))]]
def rotate4(q):
    w, x, y, z = q
    xx, yy, zz = F(x * x), F(y * y), F(z * z); xy, xz, yz = F(x * y), F(x * z), F(y * z); xw, yw, zw = F(x * w), F(y * w), F(z * w)
    return [[F(F(1) - F(F(2) * F(yy + zz))), F(F(2) * F(xy - zw)), F(F(2) * F(xz + yw))],
            [F(F(2) * F(xy + zw)), F(F(1) - F(F(2) * F(xx + zz))), F(F(2) * F(yz - xw))],
            [F(F(2) * F(xz - yw)), F(F(2) * F(yz + xw)), F(F(1) - F(F(2) * F(xx + yy)))]]
for name, mk in [("qt toRotationMatrix", to_rot), ("qt rotate4", rotate4)]:
    for layout in ("rows", "cols"):
        ok = 0
        for h, a, s in rows:
            b = bob(h).view(np.uint32); R = mk(qt_quat(0.0, a, 0.0))
            m = [F(R[i][j] * F(s[j])) for i in range(3) for j in range(3)] if layout == "rows" else [F(R[j][i] * F(s[i])) for i in range(3) for j in range(3)]
            got = np.array(m, dtype=np.float32).view(np.uint32)
            ok += (got == b[:9]).all()
            if not (got == b[:9]).all() and layout == "rows": print("   ", name, a, sx(m), [hex(v) for v in b[:9]])
        print(name, layout, ok, "/", len(rows))

print("---- variants (cols layout, i.e. transposed)")
import itertools
def quat_variant(a, half_mode, trig):
    if half_mode == "f32": h = F(F(F(a) * D2R) * F(0.5))
    elif half_mode == "f32_div": h = F(F(F(a) * F(math.pi)) / F(360))
    elif half_mode == "dbl": h = math.radians(float(F(a))) / 2
    elif half_mode == "dbl_raw": h = math.radians(a) / 2
    elif half_mode == "f32_rad_then_half_dbl": h = float(F(F(a) * D2R)) / 2
    if trig == "f32": return F(math.cos(F(h))), F(math.sin(F(h)))
    return F(math.cos(h)), F(math.sin(h))
def mats(qw, qy, mode):
    if mode == "a":  # 1-2yy, 2wy
        yy = F(qy * qy); return F(F(1) - F(yy + yy)), F(F(qw * qy) + F(qw * qy))
    if mode == "b":  # ww - yy
        return F(F(qw * qw) - F(qy * qy)), F(F(2) * F(qw * qy))
    if mode == "c":  # double-precision from float quat
        return F(1 - 2 * float(qy) * float(qy)), F(2 * float(qw) * float(qy))
    if mode == "d":  # normalised quaternion: s = 2/(n), 
        n = F(F(qw * qw) + F(qy * qy)); s = F(F(2) / n); return F(F(1) - F(F(qy * qy) * s)), F(F(qw * qy) * s)
    if mode == "e":  # ww+xx-yy-zz
        return F(F(F(qw * qw) + F(0)) - F(qy * qy)), F(F(qy * qw) * F(2))
for hm, tr, md in itertools.product(["f32", "f32_div", "dbl", "dbl_raw", "f32_rad_then_half_dbl"], ["f32", "dbl"], "abcde"):
    ok = 0
    for h, a, s in rows:
        b = bob(h)
        qw, qy = quat_variant(a, hm, tr); m00, m02 = mats(qw, qy, md)
        m0 = F(m00 * F(s[0])); m2 = F(-m02 * F(s[0])); m6 = F(m02 * F(s[2]))
        ok += [F(v).view(np.uint32) for v in (m0, m2, m6)] == [b[0].view(np.uint32), b[2].view(np.uint32), b[6].view(np.uint32)]
    if ok >= 4: print(hm, tr, md, ok)

print("---- QTU ECTransform (on_property_changed quaternion + update_transform matrix)")
PI_F, INV180, HALF, ONE = F(math.pi), F(1 / 180), F(0.5), F(1)
def u2f(u): return np.array([u], dtype=np.uint32).view(np.float32)[0]
INVPI, MAGIC = u2f(0x3ea2f983), u2f(0x4b400000)
PI1, PI2, PI3, PI4 = u2f(0x40490000), u2f(0x3a7da000), u2f(0x34222000), u2f(0x2cb4611a)
C1, C2, C3, C4 = u2f(0xbe2aaaa6), u2f(0x3c088766), u2f(0xb94fb7ff), u2f(0x362edef8)
def vsin(x):  # qttoolutility FUN_180590110 (SSE4.1 path, |x| < 10000): Cody-Waite reduction by pi, odd polynomial
    x = F(x); ax = F(abs(x)); t = F(F(ax * INVPI) + MAGIC); n = F(t - MAGIC)
    r = F(F(F(F(ax - F(PI1 * n)) - F(PI2 * n)) - F(PI3 * n)) - F(PI4 * n)); r2 = F(r * r)
    if int(t.view(np.uint32)) & 1: r = -r
    P = F(F(F(F(F(F(C4 * r2) + C3) * r2) + C2) * r2) + C1)
    out = F(r + F(F(r2 * P) * r))
    return -out if x < 0 or (x == 0 and np.signbit(x)) else out
def sc(v):  # qttoolutility FUN_180590130: sin(x) and sin(|x| + pi/2) (float sum), x itself and 1 below 2^-13
    v = F(v)
    if abs(v) < F(2.0 ** -13): return v, F(1)
    return vsin(v), vsin(F(abs(v) + F(math.pi / 2)))
def qtu_quat(rx, ry, rz):
    r = [F(F(F(a) * PI_F) * INV180) for a in (rx, ry, rz)]
    xl, xh = sc(F(r[0] * HALF)); yl, yh = sc(F(r[1] * HALF)); zl, zh = sc(F(r[2] * HALF))
    f7 = F(zl * yl); f8 = F(zl * yh); f9 = F(zh * yh); f10 = F(zh * yl)
    return (F(F(f9 * xl) - F(f7 * xh)), F(F(f8 * xl) + F(f10 * xh)), F(F(f8 * xh) - F(f10 * xl)), F(F(f7 * xl) + F(f9 * xh)))
def qtu_matrix(q, s, p):
    x, y, z, w = q; sx_, sy, sz = (F(v) for v in s); px, py, pz = (F(v) for v in p)
    x2 = F(x + x); w2 = F(w + w)
    zz2 = F(F(z + z) * z); yy2 = F(F(y + y) * y)
    f13 = F(F(w2 * z) + F(y * x2)); f19 = F(F(y * x2) - F(w2 * z)); f18 = F(F(z * x2) - F(w2 * y))
    f12 = F(ONE - F(x2 * x)); zy2 = F(z * F(y + y)); f9 = F(F(w2 * x) + zy2); l148 = F(zy2 - F(w2 * x))
    f17 = F(F(w2 * y) + F(z * x2))
    m11 = F(f12 - zz2); m00 = F(F(ONE - yy2) - zz2); m22 = F(f12 - yy2)
    Z = F(0)
    r0 = [F(F(px * Z) + F(m00 * sx_)), F(F(px * Z) + F(f19 * sy)), F(F(px * Z) + F(f17 * sz))]
    r1 = [F(F(py * Z) + F(f13 * sx_)), F(F(py * Z) + F(sy * m11)), F(F(py * Z) + F(sz * l148))]
    r2 = [F(F(pz * Z) + F(f18 * sx_)), F(F(pz * Z) + F(sy * f9)), F(F(pz * Z) + F(sz * m22))]
    return [r0, r1, r2]
for layout in ("rows", "cols"):
    ok = 0
    for h, a, s in rows:
        b = bob(h).view(np.uint32); R = qtu_matrix(qtu_quat(0.0, a, 0.0), s, (1, 1, 1))
        m = [R[i][j] for i in range(3) for j in range(3)] if layout == "rows" else [R[j][i] for i in range(3) for j in range(3)]
        got = np.array(m, dtype=np.float32).view(np.uint32); ok += (got == b[:9]).all()
        if layout == "cols" and not (got == b[:9]).all(): print("   ", a, [hex(v) for v in got], [hex(v) for v in b[:9]])
    print("qtu", layout, ok, "/", len(rows))
