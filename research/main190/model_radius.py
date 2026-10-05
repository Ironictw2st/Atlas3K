#!/usr/bin/env python3
"""Horizontal footprint radius (max |xz| of LOD0 vertices, the same as Atlas3K GlobalPropsBuilder.Radius) of every
campaign mountain / rock / vegetation / area-of-interest model extracted from the vanilla models.pack into
korea_ref/models/ -> korea_ref/model_radius.json (key: lower-case pack path; .wsmodel keys map to their geometry)."""
import glob, json, os, re, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, r"C:/Users/Arsal Zubair/AppData/Roaming/Blender Foundation/Blender/4.4/extensions/user_default/io_scene_rmv2")
import rmv2_format as R
HERE = Path(__file__).parent
BASE = HERE / "korea_ref" / "models"


def key_of(p):
    return os.path.relpath(p, BASE).replace(os.sep, "/").lower()


def radius(path):
    f = R.load(open(path, "rb").read())
    mx = 0.0
    for m in f.lods[0].models:
        mesh = getattr(m, "mesh", None)
        pos = getattr(mesh, "positions", None) if mesh is not None else None
        if pos is None: continue
        p = np.asarray(pos, float)
        mx = max(mx, float(np.sqrt(p[:, 0] ** 2 + p[:, 2] ** 2).max()))
    return mx


def main():
    out, bad = {}, []
    for p in glob.glob(str(BASE / "**" / "*.rigid_model_v2"), recursive=True):
        try: out[key_of(p)] = radius(p)
        except Exception as e: bad.append((key_of(p), str(e)[:100]))
    for p in glob.glob(str(BASE / "**" / "*.wsmodel"), recursive=True):
        t = open(p, encoding="utf-8", errors="replace").read()
        m = re.search(r"<geometry>([^<]+)</geometry>", t) or re.search(r'geometry="([^"]+)"', t)
        if m: out[key_of(p)] = out.get(m.group(1).strip().lower().replace("\\", "/"), 0.0)
    json.dump(out, open(HERE / "korea_ref" / "model_radius.json", "w"), indent=0)
    print(len(out), "models; failures", len(bad), bad[:3])
    for k in sorted(out, key=lambda k: -out[k])[:8]: print(f"{out[k]:8.1f}  {k}")
    print({k.split('/')[-1]: round(v, 1) for k, v in out.items() if "cold_peak_2" in k or "cold_ridge_2_mirror" in k})


if __name__ == "__main__":
    main()
