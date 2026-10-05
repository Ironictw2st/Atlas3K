"""Compare river meshes of two model folders (e.g. BOB vs native): pair rivers by bounding box (BOB numbers them by
entity id, the native step by name), then vertex / index counts, vertex layout, and the first differences.
usage: river_cmp.py <bob models dir> <native models dir>"""
import sys, glob, os
import numpy as np
sys.path.insert(0, r"C:/Users/Arsal Zubair/AppData/Roaming/Blender Foundation/Blender/4.4/extensions/user_default/io_scene_rmv2")
import rmv2_format as R


def load(p):
    f = R.load(open(p, "rb").read())
    out = []
    for m in f.lods[0].models:
        mesh = getattr(m, "mesh", None)
        pos = np.asarray(getattr(mesh, "positions", []), float)
        idx = np.asarray(getattr(mesh, "indices", []), int)
        out.append((pos, idx, m))
    return f, out


def summary(d):
    res = {}
    for p in sorted(glob.glob(os.path.join(d, "river_*.wsmodel.rigid_model_v2"))):
        f, parts = load(p)
        pos = np.concatenate([x[0][:, :3] for x in parts]) if parts else np.zeros((0, 3))
        n = int(os.path.basename(p).split("_")[1].split(".")[0])
        res[n] = dict(path=p, nv=len(pos), ni=sum(len(x[1]) for x in parts), parts=len(parts),
                      bbox=(pos.min(0), pos.max(0)) if len(pos) else None, size=os.path.getsize(p), pos=pos, f=f, partsraw=parts)
    return res


if __name__ == "__main__":
    B, N = summary(sys.argv[1]), summary(sys.argv[2])
    # pivot (model position) is not in the vertices; pair by bbox size + vertex range in world? use bbox extents
    def key(r): return np.concatenate([r["bbox"][1] - r["bbox"][0]])
    pairs = {}
    for bn, br in B.items():
        best = min(N.items(), key=lambda kv: np.abs(key(kv[1]) - key(br)).sum())
        pairs[bn] = best[0]
    for bn in sorted(B):
        br, nr = B[bn], N[pairs[bn]]
        print(f"bob river_{bn:2d} nv {br['nv']:5d} ni {br['ni']:5d} size {br['size']:6d} | native river_{pairs[bn]:2d} nv {nr['nv']:5d} ni {nr['ni']:5d} size {nr['size']:6d} | extent bob {np.round(key(br),2)} nat {np.round(key(nr),2)}")
    b0 = B[min(B)]
    print("bob river_%d first vertices:" % min(B)); print(np.round(b0["pos"][:12], 4))
    m = b0["partsraw"][0][2]
    print("model attrs:", [a for a in dir(m) if not a.startswith("_")][:30])
