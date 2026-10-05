"""BOB's river height patches (bob_terrain FUN_18005eb30): the river .rigid_model_v2's triangles rasterised into a
max-height field at 16 px per unit (WARSCAPE::rasterise_max_heights, INVALID_HEIGHT = -50), origin = model bbox
snapped down/up to 16 units, cut into 512 x 512 patches; patches with any valid pixel are quantised
trunc((h - lo) * (1 / (hi - lo)) * 65535) with lo/hi = the patch's min/max.
Compares the decoded u16 rasters, header and collection rectangles with BOB's.
usage: bob_patch.py [bob terrain dir]"""
import math, struct, sys, glob, os, numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
F = np.float32
INVALID = F(-50)


def read_model(path):
    b = open(path, 'rb').read()
    U = lambda o: struct.unpack_from('<I', b, o)[0]
    vo, vc, io, ic = U(0xB0), U(0xB4), U(0xB8), U(0xBC)
    V = np.frombuffer(b[0xA8 + vo:0xA8 + vo + vc * 48], np.uint8).reshape(vc, 48)
    pos = V[:, :12].copy().view(np.float32).reshape(vc, 3)
    piv = np.array(struct.unpack_from('<3f', b, 0xF8 + 0x224), np.float32)
    I = np.frombuffer(b[0xA8 + io:0xA8 + io + ic * 2], np.uint16).astype(np.int64)
    return pos, piv, I


def inside(X, Y, a, b, c):
    """FUN_180476ea0 (warscape)."""
    r = False
    ra, rc, rb = a[1] > Y, c[1] > Y, b[1] > Y
    if ra != rc:
        t = F(F(F(F(Y - a[1]) * F(c[0] - a[0])) / F(c[1] - a[1])) + a[0]); r = bool(t > X)
    if rb != ra:
        t = F(F(F(F(Y - b[1]) * F(a[0] - b[0])) / F(a[1] - b[1])) + b[0])
        if X < t: r = not r
    if rc != rb:
        t = F(F(F(F(b[0] - c[0]) * F(Y - c[1])) / F(b[1] - c[1])) + c[0])
        if X < t: r = not r
    return r


def rasterise(verts, idx, m0, m3, m8, m11, field):
    H, W = field.shape
    pts = []
    for v in verts:
        x, y, z = v
        px = F(F(F(F(y * F(0)) + F(x * m0)) + F(z * F(0))) + m3)
        py = F(F(F(F(y * F(0)) + F(x * F(0))) + F(z * m8)) + m11)
        pts.append((px, py))
    for t in range(0, len(idx), 3):
        ia, ib, ic = idx[t], idx[t + 1], idx[t + 2]
        a, b, c = pts[ia], pts[ib], pts[ic]
        xs = [int(a[0]), int(b[0]), int(c[0])]; ys = [int(a[1]), int(b[1]), int(c[1])]
        x0, x1 = min(xs) - 1, max(xs) + 1; y0, y1 = min(ys) - 1, max(ys) + 1
        if x1 < 0 or W < x0 or y1 < 0 or H < y0: continue
        x0, y0 = max(x0, 0), max(y0, 0); x1, y1 = min(x1, W), min(y1, H)
        ar = F(abs(F(F(F(c[0] - a[0]) * F(b[1] - a[1])) - F(F(c[1] - a[1]) * F(b[0] - a[0])))))
        for Y in range(y0, y1):
            fy = F(Y)
            for X in range(x0, x1):
                fx = F(X)
                if not inside(fx, fy, a, b, c): continue
                inv = F(F(2) / ar)
                wc = F(F(F(abs(F(F(F(fy - a[1]) * F(b[0] - a[0])) - F(F(fx - a[0]) * F(b[1] - a[1]))))) * F(0.5)) * inv)
                wb = F(F(F(abs(F(F(F(fy - a[1]) * F(c[0] - a[0])) - F(F(fx - a[0]) * F(c[1] - a[1]))))) * F(0.5)) * inv)
                wa = F(F(F(1) - wb) - wc)
                h = F(F(F(verts[ib][1] * wb) + F(verts[ia][1] * wa)) + F(verts[ic][1] * wc))
                if not (h <= field[Y, X]): field[Y, X] = h
    return field


def patches(model_path, world_mode='add'):
    pos, piv, idx = read_model(model_path)
    verts = (pos + piv).astype(F) if world_mode == 'add' else pos
    lo = verts.min(0); hi = verts.max(0)
    fl = lambda v: F(math.floor(F(v * F(0.0625)))); ce = lambda v: F(math.ceil(F(v * F(0.0625))))
    ax, az, bx, bz = fl(lo[0]), fl(lo[2]), ce(hi[0]), ce(hi[2])
    minx, minz = F(ax * F(16)), F(az * F(16))
    W = int(F(F(bx * F(256)) - F(ax * F(256)))); Hh = int(F(F(bz * F(256)) - F(az * F(256))))
    field = np.full((Hh, W), INVALID, np.float32)
    rasterise(verts, idx, F(16), F(minx * F(-16)), F(16), F(minz * F(-16)), field)
    out = []
    for z in range(0, Hh, 512):
        for x in range(0, W, 512):
            blk = np.full((512, 512), INVALID, np.float32)
            sub = field[z:z + 512, x:x + 512]; blk[:sub.shape[0], :sub.shape[1]] = sub
            if not (blk != INVALID).any(): continue
            l, h = F(blk.min()), F(blk.max())
            rng = F(1) if l == h else F(h - l)
            q = (((blk - l).astype(F) * F(F(1) / rng)).astype(F) * F(65535)).astype(F).astype(np.int64).astype(np.uint16)
            rect = (F(F(F(x) * F(0.0625)) + minx), F(F(F(z) * F(0.0625)) + minz),
                    F(F(F(x + 512) * F(0.0625)) + minx), F(F(F(z + 512) * F(0.0625)) + minz))
            out.append((x, z, q, (0.0, float(l), 0.0, 0.0, float(h), 0.0), rect))
    return out


if __name__ == "__main__":
    import compressed_map as C
    R = sys.argv[1] if len(sys.argv) > 1 else 'Z:/Claude/TerryClone/output/bob_runs/frida_rivers2_main190_bob_terrain'
    coll = C.read_patch_collection(R + '/height_patches/rivers.height_patch_collection')
    nb = len(glob.glob(R + '/height_patches/*.compressed_map'))
    tot = same = hdr = rect = 0; names = set()
    only = sys.argv[2] if len(sys.argv) > 2 else '*'
    for m in sorted(glob.glob(R + f'/models/river_{only}.wsmodel.rigid_model_v2')):
        n = int(os.path.basename(m).split('_')[1].split('.')[0])
        for x, z, q, h, r in patches(m):
            name = f'river_{n}_patch_{x}x{z}.compressed_map'; names.add(name); tot += 1
            p = R + '/height_patches/' + name
            if not os.path.exists(p): print('extra', name); continue
            bq, bh = C.decode(p)
            eq = np.array_equal(bq, q); same += eq; hdr += tuple(F(v) for v in bh) == tuple(F(v) for v in h)
            rect += tuple(F(v) for v in coll.get(name, ())) == r
            if not eq:
                d = bq.astype(int) - q.astype(int); print(f'{name}: {np.count_nonzero(d)} px differ (max |d| {np.abs(d).max()}), hdr bob {bh[1]:.6g}/{bh[4]:.9g} ours {h[1]:.6g}/{h[4]:.9g}')
    print(f'patches ours {tot} bob {nb}; identical rasters {same}/{tot}, headers {hdr}/{tot}, collection rects {rect}/{tot}')
