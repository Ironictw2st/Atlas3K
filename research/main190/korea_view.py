"""Render Korea (hex level): height shade, sea, impassable, coast type, roads, rivers, settlement slots."""
import sys, numpy as np
from pathlib import Path
sys.path.insert(0, "guandu"); sys.path.insert(0, "."); sys.path.insert(0, "main190")
import crop_scale_map_hex as C, hexmap, tifffile
from PIL import Image, ImageDraw
from rebuild_hex import unpack
from hexgrid import neighbour
from terrain_main import FULL, NWW, NWH
p = sys.argv[1] if len(sys.argv) > 1 else "main190/hex/map.hex"
out = sys.argv[2] if len(sys.argv) > 2 else "main190/korea_view.png"
R0, R1, C0, C1 = 420, 780, 930, 1132
src = Path(p).read_bytes(); P, w, h = C.locate_dims(src)
f = unpack(np.frombuffer(src, np.uint8, 16 * w * h, P + 8).reshape(h, w, 16))
H = tifffile.imread("main190/terrain/3k_dlc07_main_map.height.191fd803c1a801d.tif")
S = 6
img = Image.new("RGB", ((C1 - C0) * S, (R1 - R0) * S + S)); d = ImageDraw.Draw(img)
def xy(c, r): return ((c - C0) * S + S / 2, (R1 - r) * S - (c & 1) * S / 2)
for r in range(R0, R1):
    for c in range(C0, C1):
        px = min(int(c * 0.668 / NWW * FULL[0]), FULL[0] - 1); py = min(int((1 - (r * 0.772 + (c & 1) * 0.386) / NWH) * FULL[1]), FULL[1] - 1)
        t = f["terr"][r, c]; v = int(np.clip((int(H[py, px]) - 14000) / 30000 * 200 + 40, 40, 240))
        col = (30, 60, 140) if t == 1 else (240, 220, 120) if t == 2 else (150, 60, 160) if t == 3 else (v, v, v)
        if t != 1 and f["imp"][r, c]: col = (v // 2, v // 3, v // 3)
        if f["slot"][r, c] >= 0: col = (255, 140, 0) if f["slot"][r, c] == 0 else (200, 120, 60)
        x, y = xy(c, r); d.rectangle([x - S / 2, y - S / 2, x + S / 2 - 1, y + S / 2 - 1], fill=col)
for r in range(R0, R1):
    for c in range(C0, C1):
        for fld, colr in (("river", (80, 160, 255)), ("road", (220, 30, 30))):
            for k in range(6):
                if (f[fld][r, c] >> k) & 1:
                    nc, nr = neighbour(c, r, k)
                    if C0 <= nc < C1 and R0 <= nr < R1: d.line([xy(c, r), xy(nc, nr)], fill=colr, width=2)
img.save(out); print(out, img.size)
