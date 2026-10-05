"""LOD0 vertex bounds (min/max x, y, z and max |xz| radius) of every extracted model -> output/props_parity/model_bounds.json,
keyed by the lower-case pack path used in global_props (wsmodel keys resolve to their geometry file).
Uses the io_scene_rmv2 Blender add-on's rmv2_format reader. usage: model_bounds.py"""
import json, re, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, r"C:/Users/Arsal Zubair/AppData/Roaming/Blender Foundation/Blender/4.4/extensions/user_default/io_scene_rmv2")
import rmv2_format as R
OUT = Path(r"Z:/Claude/TerryClone/output/props_parity"); M = OUT / "models"


def bounds(p):
    f = R.load(open(p, "rb").read())
    pts = []
    for m in f.lods[0].models:
        pos = getattr(getattr(m, "mesh", None), "positions", None)
        if pos is not None and len(pos): pts.append(np.asarray(pos, float)[:, :3])
    if not pts: return None
    a = np.concatenate(pts)
    c = (a.min(0) + a.max(0)) / 2
    def hb(lods):
        mins = [m.bbox_min for L in lods for m in L.models if getattr(m, "bbox_min", None) is not None]
        maxs = [m.bbox_max for L in lods for m in L.models if getattr(m, "bbox_max", None) is not None]
        return (np.min(mins, 0).round(5).tolist(), np.max(maxs, 0).round(5).tolist()) if mins else None
    allv = [np.asarray(m.mesh.positions, float)[:, :3] for L in f.lods for m in L.models if getattr(getattr(m, "mesh", None), "positions", None) is not None and len(m.mesh.positions)]
    av = np.concatenate(allv) if allv else a
    return dict(min=a.min(0).round(5).tolist(), max=a.max(0).round(5).tolist(), r=float(np.sqrt(a[:, 0] ** 2 + a[:, 2] ** 2).max()),
                r3=float(np.sqrt((a ** 2).sum(1)).max()), r3c=float(np.sqrt(((a - c) ** 2).sum(1)).max()), c=c.round(5).tolist(),
                h0=hb(f.lods[:1]), hall=hb(f.lods), vall=(av.min(0).round(5).tolist(), av.max(0).round(5).tolist()))


res = {}
for k in [m.strip() for m in open(OUT / "models.txt", encoding="utf-8") if m.strip()]:
    p = M / k
    if not p.exists(): continue
    if k.endswith(".wsmodel"):
        g = re.search(r"<geometry>([^<]+)</geometry>", p.read_text(encoding="utf-8", errors="replace"))
        p = M / g.group(1).strip().lower() if g else None
        if p is None or not p.exists(): continue
    try: res[k] = bounds(p)
    except Exception as e: res[k] = None; print("fail", k, e)
json.dump(res, open(OUT / "model_bounds.json", "w"), indent=0)
print(len(res), "models,", sum(v is not None for v in res.values()), "with bounds")
