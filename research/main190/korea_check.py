"""Korea diagnostics on the warped map.hex: regions, coast types, roads (read-only)."""
import sys, numpy as np
from pathlib import Path
sys.path.insert(0, "guandu"); sys.path.insert(0, ".")
import crop_scale_map_hex as C, hexmap
from rebuild_hex import unpack, components
from hexgrid import neighbour
p = "main190/hex/map.hex"; src = Path(p).read_bytes()
L = hexmap.load(p)["lists"]; names = L["land_regions"] + L["sea_regions"]
P, w, h = C.locate_dims(src); g = np.frombuffer(src, np.uint8, 16 * w * h, P + 8).reshape(h, w, 16); f = unpack(g)
# Korea: land hexes east of col 1000 north of row 500 (east of Liaodong gulf); list region names there
box = np.zeros((h, w), bool); box[430:760, 1000:1132] = True
reg = f["region"]; land = f["terr"] != 1
print("dims", w, h, "terr codes", np.unique(f["terr"], return_counts=True))
ks, cnt = np.unique(reg[box & land & (reg >= 0)], return_counts=True)
for k, c in sorted(zip(ks, cnt), key=lambda t: -t[1])[:40]:
    m = box & (reg == k); rr, cc = np.nonzero(m)
    print(f"{names[k]:45s} {c:5d} hexes  cols {cc.min()}-{cc.max()} rows {rr.min()}-{rr.max()} slots {sorted(set(f['slot'][m][f['slot'][m]>=0]))} road {int((f['road'][m]>0).sum())} beach {int((f['terr'][m]==2).sum())} cliff {int((f['terr'][m]==3).sum())}")

# ---- raster stats at coast hexes ----
sys.path.insert(0, "main190")
import tifffile
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
from terrain_main import FULL, NWW, NWH
H = tifffile.imread("main190/terrain/3k_dlc07_main_map.height.191fd803c1a801d.tif")
B = np.array(Image.open("main190/terrain/3k_dlc07_main_map.blend.191fd8068da8020.tif"))
TR = np.array(Image.open("main190/terrain/3k_dlc07_main_map.tree.191fd7dc12fe7e4.tif"))
rr, cc = np.mgrid[0:h, 0:w]
px = np.clip((cc * 0.668 / NWW * FULL[0]).astype(int), 0, FULL[0] - 1)
py = np.clip(((1 - (rr * 0.772 + (cc & 1) * 0.386) / NWH) * FULL[1]).astype(int), 0, FULL[1] - 1)
hh = H[py, px]; bb = B[py, px]; tt = TR[py // 4, px // 4]
korea = np.zeros((h, w), bool); korea[440:760, 960:1132] = True
for nm, sel in (("mainland", ~korea), ("korea", korea)):
    for t, tn in ((2, "beach"), (3, "cliff"), (0, "land")):
        m = sel & (f["terr"] == t)
        u, c = np.unique(bb[m], return_counts=True); o = np.argsort(-c)[:6]
        ut, ct = np.unique(tt[m], return_counts=True); ot = np.argsort(-ct)[:4]
        print(f"{nm:8s} {tn:5s} n={m.sum():6d} h pct {np.percentile(hh[m], [10, 50, 90]).astype(int)} blend {[(int(u[i]), round(c[i]/c.sum(), 2)) for i in o]} tree {[(int(ut[i]), round(ct[i]/ct.sum(), 2)) for i in ot]}")
