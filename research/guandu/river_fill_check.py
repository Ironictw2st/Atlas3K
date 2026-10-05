#!/usr/bin/env python3
"""How much of the land-mesh hole area is filled by the map's own river meshes (models/river_N) and sea meshes.

Holes not covered by any river mesh, sea mesh or water hex are see-through in game.
usage: river_fill_check.py <terrain dir> [out.png]
"""
import glob, os, struct, sys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
import compressed_map as CM  # noqa: E402
from river_hole_coverage import triangles, covered  # noqa: E402


def mesh_tris(path):
    t, mn, mx = triangles(path)
    return t, mn, mx


def main(terrain, out=None, step=2):
    pts = []
    for p in glob.glob(os.path.join(terrain, "global_meshes", "land_mesh_*.compressed_map")):
        rm = open(p.replace(".compressed_map", ".rigid_model_v2"), "rb").read()
        mn = np.array(struct.unpack_from("<3f", rm, 0xA8 + 24)); mx = np.array(struct.unpack_from("<3f", rm, 0xA8 + 36))
        a, _ = CM.decode(p); h, w = a.shape
        ys, xs = np.nonzero(a[::step, ::step] == 0); ys *= step; xs *= step
        pts.append(np.stack([mn[0] + (xs + 0.5) / w * (mx[0] - mn[0]), mx[2] - (ys + 0.5) / h * (mx[2] - mn[2])], 1))
    P = np.vstack(pts)
    cov = np.zeros(len(P), bool)
    kinds = {}
    for pat, key in (("models/river_*.wsmodel.rigid_model_v2", "river"), ("global_meshes/sea_mesh_*.rigid_model_v2", "sea")):
        n0 = cov.sum()
        for p in glob.glob(os.path.join(terrain, *pat.split("/"))):
            try:
                t, mn, mx = mesh_tris(p)
            except Exception:
                continue
            m = (P[:, 0] >= mn[0] - 0.5) & (P[:, 0] <= mx[0] + 0.5) & (P[:, 1] >= mn[2] - 0.5) & (P[:, 1] <= mx[2] + 0.5) & ~cov
            if m.any():
                c = covered(P[m], t); idx = np.nonzero(m)[0]; cov[idx[c]] = True
        kinds[key] = int(cov.sum() - n0)
    print(f"hole samples {len(P)}: filled by river meshes {kinds['river']}, by sea meshes {kinds['sea']}, "
          f"UNFILLED {int((~cov).sum())} ({(~cov).mean():.1%})")
    if out:
        W = int(np.ceil(P[:, 0].max())) + 1; H = int(np.ceil(P[:, 1].max())) + 1
        img = np.zeros((H * 2, W * 2, 3), np.uint8)
        xi = (P[:, 0] * 2).astype(int); zi = (P[:, 1] * 2).astype(int)
        img[zi[cov], xi[cov]] = (0, 120, 255); img[zi[~cov], xi[~cov]] = (255, 0, 0)
        Image.fromarray(img[::-1]).save(out); print("wrote", out, "(blue filled, red unfilled = see-through)")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
