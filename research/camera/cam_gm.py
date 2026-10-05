"""Camera heightmap prototype, global-mesh term only (float32, BOB's order) vs BOB's float buffer.
usage: cam_gm.py <global_meshes dir> <blocks.npy> <bob .f32> <bob .json> [bounds=grid|tight] [flip=0|1]"""
import json, sys
import numpy as np
sys.path.insert(0, r"Z:/Claude/TerryClone/research/trees")
import camap_read
F = np.float32
ZS = F(1.15476); TILE = F(F(595.1) / F(1784)); BS = F(F(223) * (TILE / F(2)))


def sample_gm(cm, hdr, u, v, flip):
    """warscape FUN_18039f3e0 (decoded from the disassembly)."""
    H, W = cm.shape
    if flip: cm = cm[::-1]
    fx = (F(W) * u).astype(F); fy = (F(H) * v).astype(F)
    tx = (fx - np.floor(fx)).astype(F); ty = (fy - np.floor(fy)).astype(F)
    x0 = np.trunc(fx).astype(F); y0 = np.trunc(fy).astype(F); x1 = (x0 + F(1)).astype(F); y1 = (y0 + F(1)).astype(F)
    cx = lambda a: np.clip(a, F(0), F(W - 1)).astype(np.int64); cy = lambda a: np.clip(a, F(0), F(H - 1)).astype(np.int64)
    lo, hi = F(hdr[1]), F(hdr[4])
    val = lambda xi, yi: ((cm[yi, xi].astype(F) * F(1 / 65535)).astype(F) * (hi - lo) + lo).astype(F)
    A = val(cx(x0), cy(y1)); B = val(cx(x1), cy(y1)); C = val(cx(x0), cy(y0)); D = val(cx(x1), cy(y0))
    inv = F(-50)
    allinv = (A == inv) & (B == inv) & (C == inv) & (D == inv)
    fb = np.where(A != inv, A, np.where(C != inv, C, np.where(B != inv, B, D)))
    A = np.where(A == inv, fb, A); B = np.where(B == inv, fb, B); C = np.where(C == inv, fb, C); D = np.where(D == inv, fb, D)
    r0 = ((D - C).astype(F) * tx + C).astype(F); r1 = ((B - A).astype(F) * tx + A).astype(F)
    out = ((r0 - r1).astype(F) * ty + r1).astype(F)
    return np.where(allinv, inv, out)


def height_gm(px, pz, blocks, maps, bounds, flip):
    zt = (pz / ZS).astype(F)
    res = np.full(px.shape, F(-50)); done = np.zeros(px.shape, bool)
    for (n, mnx, mnz, mxx, mxz) in blocks:
        n = int(n)
        if bounds == "bob":                                  # BOB's own block AABBs (Frida dump), index = land_mesh_N
            mnx, mnz, mxx, mxz = F(mnx), F(mnz), F(mxx), F(mxz)
        elif bounds == "grid":
            c = int(round(mnx / float(BS))); r = int(round(mnz / float(BS)))
            if abs(mnx - c * float(BS)) > 1e-3: c = int(mnx // float(BS))
            if abs(mnz - r * float(BS)) > 1e-3: r = int(mnz // float(BS))
            import os
            mode = os.environ.get("CAM_BOUNDS", "f32")
            if mode == "f32": mnx, mxx = F(F(c) * BS), F(F(c + 1) * BS); mnz, mxz = F(F(r) * BS), F(F(r + 1) * BS)
            elif mode == "dbl":                              # native GlobalMeshBuilder.Coord: index * extent / gridTotal in double
                ext = 1784 * float(TILE); cr = lambda i: F(i * ext / 3568)
                mnx, mxx, mnz, mxz = cr(c * 223), cr((c + 1) * 223), cr(r * 223), cr((r + 1) * 223)
            elif mode == "f32idx":                           # float(index) * (T/2) in float32
                hh = F(TILE / F(2)); cr = lambda i: F(F(i) * hh)
                mnx, mxx, mnz, mxz = cr(c * 223), cr((c + 1) * 223), cr(r * 223), cr((r + 1) * 223)
            elif mode == "f32ext":                           # float(index) * ext / gridTotal in float32
                ext = F(F(1784) * TILE); cr = lambda i: F(F(F(i) * ext) / F(3568))
                mnx, mxx, mnz, mxz = cr(c * 223), cr((c + 1) * 223), cr(r * 223), cr((r + 1) * 223)
        else:
            mnx, mnz, mxx, mxz = F(mnx), F(mnz), F(mxx), F(mxz)
        m = ~done & (px >= mnx) & (px <= mxx) & (zt >= mnz) & (zt <= mxz)
        if not m.any(): continue
        cm, hdr = maps[n]
        u = ((px[m] - mnx).astype(F) / (mxx - mnx)).astype(F); v = ((zt[m] - mnz).astype(F) / (mxz - mnz)).astype(F)
        h = sample_gm(cm, hdr, u, v, flip)
        res[m] = h; done[m] = True                       # FUN_180350620: first containing block, valid or not
    return res


if __name__ == "__main__":
    gm, bnp, dump, meta = sys.argv[1:5]
    bounds = sys.argv[5] if len(sys.argv) > 5 else "grid"; flip = int(sys.argv[6]) if len(sys.argv) > 6 else 0
    info = json.load(open(meta)); W, H = info["W"], info["H"]
    s = info["samplesPerUnit"]; stepX, stepZ, halfX, halfZ = map(F, (info["stepX"], info["stepZ"], info["halfX"], info["halfZ"]))
    bob = np.fromfile(dump, np.float32).reshape(H, W)
    blocks = np.load(bnp)
    maps = {int(b[0]): camap_read.read(f"{gm}/land_mesh_{int(b[0])}.compressed_map") for b in blocks}
    uu, vv = np.meshgrid(np.arange(W), np.arange(H))
    fxc = (uu.astype(F) * stepX).astype(F); fzc = (vv.astype(F) * stepZ).astype(F)
    minX = (fxc - halfX).astype(F); maxX = (fxc + halfX).astype(F); minZ = (fzc - halfZ).astype(F); maxZ = (fzc + halfZ).astype(F)
    dx = (maxX - minX).astype(F); dz = (maxZ - minZ).astype(F)
    nx = np.ceil((dx * F(s)).astype(F)); nz = np.ceil((dz * F(s)).astype(F))
    assert nx.min() == nx.max() and nz.min() == nz.max(), "varying sample counts"
    nx, nz = int(nx.flat[0]), int(nz.flat[0])
    sx = (dx / F(nx)).astype(F); sz = (dz / F(nz)).astype(F)
    best = np.full((H, W), F(-1))
    z = minZ.copy()
    for j in range(nz):
        x = minX.copy()
        for k in range(nz):                                 # BOB: the inner loop also runs nz times
            best = np.maximum(height_gm(x, z, blocks, maps, bounds, flip), best)
            x = (x + sx).astype(F)
        z = (z + sz).astype(F)
    cxp = ((maxX - minX).astype(F) * F(0.5) + minX).astype(F); czp = ((maxZ - minZ).astype(F) * F(0.5) + minZ).astype(F)
    best = np.maximum(best, height_gm(cxp, czp, blocks, maps, bounds, flip))
    ex = best.view(np.int32) == bob.view(np.int32)
    d = best.astype(np.float64) - bob
    print(f"bounds={bounds} flip={flip}: bit-exact {ex.mean():.4%}  |d|<1e-4 {(np.abs(d) < 1e-4).mean():.4%}  "
          f"proto<bob by >0.01 {(d < -0.01).mean():.4%}  proto>bob by >0.01 {(d > 0.01).mean():.4%}")
    np.save(dump.replace(".f32", f".gm_{bounds}_{flip}.npy"), best)
