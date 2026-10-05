"""Prototype of BOB's camera heightmap sampling (tooldatabuilder generate_camera_height_map, FUN_18009b110 /
FUN_18006bf20, height provider warscape FUN_18034cf20) - global mesh term only, float32 everywhere.
usage: cam_proto.py <global_meshes dir> <bob float dump .f32> <dump .json> [orient]"""
import json, sys, glob, re
from pathlib import Path
import numpy as np
sys.path.insert(0, r"Z:/Claude/TerryClone/research/trees")
sys.path.insert(0, r"C:/Users/Arsal Zubair/AppData/Roaming/Blender Foundation/Blender/4.4/extensions/user_default/io_scene_rmv2")
import camap_read
F = np.float32
TILE = F(F(595.1) / F(1784)); ZS = F(1.15476)


def blocks(gm_dir):
    """land_mesh_N -> (minX, minZ, maxX, maxZ) in tile space from the mesh vertices, plus the height map."""
    import rmv2_format as R
    out = []
    for p in sorted(glob.glob(str(Path(gm_dir) / "land_mesh_*.rigid_model_v2")), key=lambda s: int(re.search(r"_(\d+)\.rigid", s).group(1))):
        f = R.load(open(p, "rb").read())
        pos = np.concatenate([np.asarray(m.mesh.positions, float)[:, :3] for m in f.lods[0].models if getattr(getattr(m, "mesh", None), "positions", None) is not None])
        n = int(re.search(r"_(\d+)\.rigid", p).group(1))
        cm = p.replace(".rigid_model_v2", ".compressed_map")
        out.append(dict(n=n, minX=float(pos[:, 0].min()), maxX=float(pos[:, 0].max()), minZ=float(pos[:, 2].min()), maxZ=float(pos[:, 2].max()), cm=cm))
    return out


if __name__ == "__main__":
    gm, dump, meta = sys.argv[1:4]
    info = json.load(open(meta)); W, H = info["W"], info["H"]
    bob = np.fromfile(dump, np.float32).reshape(H, W)
    bl = blocks(gm)
    print(len(bl), "land meshes; first", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in bl[0].items() if k != "cm"})
    xs = sorted(set(round(b["minX"], 3) for b in bl)); zs = sorted(set(round(b["minZ"], 3) for b in bl))
    print("block minX values", xs[:5], "... minZ", zs[:5])
    np.save(Path(dump).with_suffix(".blocks.npy"), np.array([[b["n"], b["minX"], b["minZ"], b["maxX"], b["maxZ"]] for b in bl]))
