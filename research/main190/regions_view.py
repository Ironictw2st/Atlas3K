"""Render regions (north half) with settlements and planned seats: research/main190/regions_view.png"""
import sys, numpy as np
from pathlib import Path
from PIL import Image, ImageDraw
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
from regions_plan import load, plan
f, names, w, h = load(); out, _, _ = plan(f, names, w, h)
R0 = int(sys.argv[1]) if len(sys.argv) > 1 else 380; S = 2
rng = np.random.default_rng(3); pal = rng.integers(60, 230, (len(names) + 1, 3))
reg = f["region"]; img = pal[np.clip(reg, 0, None)].astype(np.uint8)
np_ = [i for i, n in enumerate(names) if "non_playable" in n]
img[np.isin(reg, np_)] = (70, 70, 70)
img[f["imp"] == 1] = (img[f["imp"] == 1] * 0.55).astype(np.uint8)
img[f["terr"] == 1] = (30, 60, 140)
# borders
b = np.zeros_like(reg, bool); b[:, 1:] |= reg[:, 1:] != reg[:, :-1]; b[1:, :] |= reg[1:, :] != reg[:-1, :]
img[b & (f["terr"] != 1)] = (20, 20, 20)
img[f["slot"] == 0] = (255, 255, 255)
img = img[::-1][: h - R0]                      # north up, rows >= R0
im = Image.fromarray(img).resize((w * S, (h - R0) * S), Image.NEAREST); d = ImageDraw.Draw(im)
for i, n in enumerate(names):
    m = (reg == i) & (f["slot"] == 0)
    if not m.any() or "_capital" not in n: continue
    r, c = np.argwhere(m).mean(0)
    if r < R0: continue
    d.text((c * S + 3, (h - 1 - r) * S - 5), n.replace("3k_main_", "").replace("3k_dlc06_", "").replace("ironic_region_", "i:").replace("_capital", ""), fill=(255, 255, 255))
for k, (g, seat, c, r) in out.items():
    y = (h - 1 - r) * S; x = c * S
    d.line([x - 6, y - 6, x + 6, y + 6], fill=(255, 0, 0), width=3); d.line([x - 6, y + 6, x + 6, y - 6], fill=(255, 0, 0), width=3)
    d.text((x + 6, y + 2), k, fill=(255, 60, 60))
im.save(HERE / "regions_view.png"); print(im.size)
