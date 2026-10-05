"""Check that BOB's river meshes fill the land-mesh river holes as well as vanilla's do.

The big rivers are holes cut into the land meshes (value 0 = -50 in land_mesh_N.compressed_map), filled by river
meshes, sea meshes or river tiles. A river mesh that is too narrow or too short leaves hole pixels showing through
("river missing" in game). Per river, this counts the hole pixels covered by the vanilla mesh but not by the built
mesh. Rivers are matched by shape, so BOB's own numbering doesn't matter.

usage: river_hole_coverage.py <built terrain dir> <vanilla terrain dir>
"""
import glob
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import compressed_map as C  # noqa: E402
import rivers_from_meshes as RM  # noqa: E402


def triangles(path):
    b = open(path, "rb").read()
    g = 0xA8
    _, _, voff, vc, ioff, ic = struct.unpack_from("<6I", b, g)
    mn = np.array(struct.unpack_from("<3f", b, g + 24))
    mx = np.array(struct.unpack_from("<3f", b, g + 36))
    stride = (ioff - voff) // vc
    v = np.frombuffer(b[g + voff:g + voff + vc * stride], np.uint8).reshape(vc, stride)[:, :12].copy().view("<f4")
    v = v.astype(float) + (mn + mx) / 2  # river mesh vertices are local to the bbox centre
    idx = np.frombuffer(b[g + ioff:g + ioff + ic * 2], "<u2").reshape(-1, 3)
    return v[:, [0, 2]][idx], mn, mx


def covered(points, tris):
    out = np.zeros(len(points), bool)
    lo, hi = tris.min(1), tris.max(1)
    for (a, b, c), l, h in zip(tris, lo, hi):
        m = (points[:, 0] >= l[0]) & (points[:, 0] <= h[0]) & (points[:, 1] >= l[1]) & (points[:, 1] <= h[1]) & ~out
        if not m.any():
            continue
        q = points[m]
        d1 = (q[:, 0] - b[0]) * (a[1] - b[1]) - (a[0] - b[0]) * (q[:, 1] - b[1])
        d2 = (q[:, 0] - c[0]) * (b[1] - c[1]) - (b[0] - c[0]) * (q[:, 1] - c[1])
        d3 = (q[:, 0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (q[:, 1] - a[1])
        inside = ~(((d1 < 0) | (d2 < 0) | (d3 < 0)) & ((d1 > 0) | (d2 > 0) | (d3 > 0)))
        out[np.nonzero(m)[0][inside]] = True
    return out


def main(built, vanilla):
    land = []
    for p in glob.glob(os.path.join(built, "global_meshes", "land_mesh_*.compressed_map")):
        rm = open(p.replace(".compressed_map", ".rigid_model_v2"), "rb").read()
        land.append((p, np.array(struct.unpack_from("<3f", rm, 0xA8 + 24)), np.array(struct.unpack_from("<3f", rm, 0xA8 + 36))))
    count = lambda d: len(glob.glob(os.path.join(d, "models", "river_*.wsmodel.rigid_model_v2")))
    vsec = {j: RM.cross_sections(RM.read_river_mesh(os.path.join(vanilla, "models", f"river_{j}.wsmodel.rigid_model_v2")))[:, 1:4]
            for j in range(count(vanilla))}
    total = 0
    print("vanilla river | matched built | hole px (vanilla covers) | built covers | gap")
    for i in range(count(built)):
        bpath = os.path.join(built, "models", f"river_{i}.wsmodel.rigid_model_v2")
        bsec = RM.cross_sections(RM.read_river_mesh(bpath))[:, 1:4]
        j = min(vsec, key=lambda k: np.median(RM.xz_distance(bsec, vsec[k])))
        tb, _, _ = triangles(bpath)
        tv, mn, mx = triangles(os.path.join(vanilla, "models", f"river_{j}.wsmodel.rigid_model_v2"))
        pts = []
        for p, lmn, lmx in land:
            if lmx[0] < mn[0] - 1 or lmn[0] > mx[0] + 1 or lmx[2] < mn[2] - 1 or lmn[2] > mx[2] + 1:
                continue
            a, _ = C.decode(p)
            h, w = a.shape
            ys, xs = np.nonzero(a == 0)
            X = lmn[0] + (xs + 0.5) / w * (lmx[0] - lmn[0])
            Z = lmx[2] - (ys + 0.5) / h * (lmx[2] - lmn[2])
            k = (X >= mn[0] - 1) & (X <= mx[0] + 1) & (Z >= mn[2] - 1) & (Z <= mx[2] + 1)
            pts.append(np.stack([X[k], Z[k]], 1))
        P = np.vstack(pts)
        cv, cb = covered(P, tv), covered(P, tb)
        gap = cv & ~cb
        total += gap.sum()
        where = f"  around ({P[gap][:, 0].mean():.1f},{P[gap][:, 1].mean():.1f})" if gap.any() else ""
        print(f"river_{j:<2d}      | river_{i:<2d}       | {cv.sum():6d} | {cb.sum():6d} | {gap.sum():5d}{where}")
    print(f"total hole px vanilla covers but the build doesn't: {total}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
