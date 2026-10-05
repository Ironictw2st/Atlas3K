"""Camera heightmap prototype: global mesh + height patches (+ fallback 0), float32 in BOB's order, vs BOB's buffer.
usage: cam_full.py <global_meshes dir> <blocks.npy> <bob .f32> <bob .json> <patches.json> <patchmap.json>"""
import json, os, sys
import numpy as np
sys.path.insert(0, r"Z:/Claude/TerryClone/research/trees")
import camap_read
from cam_gm import sample_gm, F, ZS, BS
NEG = F(-3.4028234663852886e+38); INV = F(-50)


def sample_patch(raw, lo, hi, u, v):
    """warscape FUN_18039f140: max of the corners (x0, y-1), (x1, y-1), (x1, y)."""
    H, W = raw.shape
    if os.environ.get("CAM_PFLIP") == "1" or (os.environ.get("CAM_PFLIP") == "river" and raw.shape[0] >= 512): raw = raw[::-1]
    x0 = np.trunc((F(W) * u).astype(F)).astype(F); y0 = np.trunc((F(H) * v).astype(F)).astype(F)
    x1 = (x0 + F(1)).astype(F); ym = (y0 - F(1)).astype(F)
    cx = lambda a: np.clip(a, F(0), F(W - 1)).astype(np.int64); cy = lambda a: np.clip(a, F(0), F(H - 1)).astype(np.int64)
    vf = lambda xi, yi: ((raw[yi, xi].astype(F) * F(1 / 65535)).astype(F) * (hi - lo) + lo).astype(F)
    v1 = vf(cx(x0), cy(ym)); v2 = vf(cx(x1), cy(ym)); v4 = vf(cx(x1), cy(y0))
    r = np.where(v2 <= v1, v1, v2)
    return np.where(r <= v4, v4, r)


def main():
    gm, bnp, dump, meta, pj, pm = sys.argv[1:7]
    info = json.load(open(meta)); W, H = info["W"], info["H"]
    s = info["samplesPerUnit"]; stepX, stepZ, halfX, halfZ = map(F, (info["stepX"], info["stepZ"], info["halfX"], info["halfZ"]))
    bob = np.fromfile(dump, np.float32).reshape(H, W)
    blocks = np.load(bnp)
    maps = {int(b[0]): camap_read.read(f"{gm}/land_mesh_{int(b[0])}.compressed_map") for b in blocks}
    objs = json.load(open(pj))["objs"]; pmap = {int(k): v for k, v in json.load(open(pm)).items()}
    pcache = {}
    us = np.arange(W).astype(F); vs = np.arange(H).astype(F)
    cxu = (us * stepX).astype(F); czv = (vs * stepZ).astype(F)
    minX = (cxu - halfX).astype(F); maxX = (cxu + halfX).astype(F); minZ = (czv - halfZ).astype(F); maxZ = (czv + halfZ).astype(F)
    dx = (maxX - minX).astype(F); dz = (maxZ - minZ).astype(F)
    nx = int(np.ceil((dx * F(s)).astype(F))[0]); nz = int(np.ceil((dz * F(s)).astype(F))[0])
    sx = (dx / F(nx)).astype(F); sz = (dz / F(nz)).astype(F)
    # sample x per (u, k) and z per (v, j): accumulated as BOB does
    xs = [minX]; [xs.append((xs[-1] + sx).astype(F)) for _ in range(nz - 1)]
    zs = [minZ]; [zs.append((zs[-1] + sz).astype(F)) for _ in range(nz - 1)]
    xs.append(((maxX - minX).astype(F) * F(0.5) + minX).astype(F)); zs.append(((maxZ - minZ).astype(F) * F(0.5) + minZ).astype(F))
    pairs = [(j, k) for j in range(nz) for k in range(nz)] + [(nz, nz)]       # last = the centre sample
    from cam_gm import height_gm
    best = np.full((H, W), F(-1))
    stats = dict(fallback=0)
    for (j, k) in pairs:
        X = np.broadcast_to(xs[k][None, :], (H, W)).astype(F); Z = np.broadcast_to(zs[j][:, None], (H, W)).astype(F)
        g = height_gm(X, Z, blocks, maps, os.environ.get("CAM_MODE", "grid"), 0)
        stats["fallback"] += int((g <= INV).sum())
        g = np.where(g > INV, g, F(0))                     # fallback (tiles) not ported yet: 0
        # height patches at the world point
        p = np.full((H, W), NEG)
        xk, zj = xs[k], zs[j]
        for o in objs:
            a = o["aabb"]
            u0 = np.searchsorted(xk, F(a[0]), "left"); u1 = np.searchsorted(xk, F(a[2]), "right")
            v0 = np.searchsorted(zj, F(a[1]), "left"); v1 = np.searchsorted(zj, F(a[3]), "right")
            if u0 >= u1 or v0 >= v1: continue
            x = np.broadcast_to(xk[None, u0:u1], (v1 - v0, u1 - u0)).astype(F); z = np.broadcast_to(zj[v0:v1, None], (v1 - v0, u1 - u0)).astype(F)
            inv = [F(t) for t in o["inv"]]; loc = [F(t) for t in o["local"]]; m = [F(t) for t in o["m"]]
            lx = ((z * inv[2]).astype(F) + (x * inv[0]).astype(F) + inv[3]).astype(F)
            lz = ((z * inv[10]).astype(F) + (x * inv[8]).astype(F) + inv[11]).astype(F)
            ok = (loc[0] <= lx) & (lx <= loc[2]) & (loc[1] <= lz) & (lz <= loc[3])
            if not ok.any(): continue
            uu = ((lx - loc[0]).astype(F) / (loc[2] - loc[0])).astype(F); vv = ((lz - loc[1]).astype(F) / (loc[3] - loc[1])).astype(F)
            path = pmap[o["i"]]
            if path not in pcache:
                raw, hdr = camap_read.read(path); pcache[path] = (raw, F(hdr[1]), F(hdr[4]))
            raw, lo, hi = pcache[path]
            hh = sample_patch(raw, lo, hi, uu, vv)
            sc = np.sqrt(F(F(F(m[5] * m[5]) + F(m[1] * m[1])) + F(m[9] * m[9]))).astype(F)
            val = ((sc * hh).astype(F) + m[7]).astype(F)
            val = np.where(ok & (hh != INV), val, NEG)
            sub = p[v0:v1, u0:u1]; p[v0:v1, u0:u1] = np.maximum(sub, val)
        h = np.where(g <= p, p, g)
        best = np.where(h <= best, best, h)                  # BOB: maxss
    ex = best.view(np.int32) == bob.view(np.int32); d = best.astype(np.float64) - bob
    print(f"bit-exact {ex.mean():.4%}  |d|<1e-4 {(np.abs(d) < 1e-4).mean():.4%}  bob higher>0.01 {(d < -0.01).mean():.4%}  proto higher>0.01 {(d > 0.01).mean():.4%}  fallback samples {stats['fallback']}")
    np.save(dump.replace(".f32", ".full.npy"), best)


if __name__ == "__main__":
    main()
