"""Crop box + Guandu-campaign sites on the vanilla heightmap, using georef.json (affine + IDW residual correction)."""
import json, os, numpy as np
from PIL import Image, ImageDraw, ImageFont
from georef import SEATS, WORLD_W, WORLD_H, RASTER_W, RASTER_H

HERE = os.path.dirname(os.path.abspath(__file__))
g = json.load(open(os.path.join(HERE, "georef.json")))
M, S = np.array(g["M"]), {k: tuple(v) for k, v in g["settlements"].items()}
anchors = [(SEATS[k][2], SEATS[k][1], np.array(S[k])) for k in SEATS if k in S]

def to_world(lat, lon):
    base = np.array([lon, lat, 1]) @ M
    w, r = [], []
    for alon, alat, xz in anchors:
        d2 = (alon - lon) ** 2 + (alat - lat) ** 2
        if d2 < 1e-6: return xz
        w.append(1 / d2); r.append(xz - np.array([alon, alat, 1]) @ M)
    w = np.array(w); corr = (w[:, None] * np.array(r)).sum(0) / w.sum()
    fade = min(1.0, 1.5 / np.sqrt(1 / w.max()))    # full correction near anchors, fading out beyond ~1.5 deg
    return base + corr * fade

def to_px(x, z):
    return x / WORLD_W * RASTER_W, (1 - z / WORLD_H) * RASTER_H

# 198 CE sites (approx modern coords of the Han sites)
SITES = {
    "Guandu": (34.73, 114.02), "Baima": (35.58, 114.63), "Yan Ford": (35.28, 114.28),
    "Wuchao": (35.20, 114.40), "Liyang": (35.62, 114.52), "Yangwu": (35.05, 114.03),
    "Chenliu": (34.66, 114.63), "Yijing": (38.99, 116.08), "Shouchun": (32.58, 116.78),
    "Pei": (34.72, 116.93), "Hulao": (34.85, 113.23), "Hangu": (34.63, 110.87),
}
BOX = dict(lat0=31.5, lat1=41.8, lon0=108.5, lon1=122.8)

if __name__ == "__main__":
    corners = [to_world(la, lo) for la in (BOX["lat0"], BOX["lat1"]) for lo in (BOX["lon0"], BOX["lon1"])]
    xs, zs = [c[0] for c in corners], [c[1] for c in corners]
    x0, x1 = max(0, min(xs)), min(WORLD_W, max(xs)); z0, z1 = max(0, min(zs)), min(WORLD_H, max(zs))
    px0, py1 = to_px(x0, z0); px1, py0 = to_px(x1, z1)
    print(f"crop world x {x0:.1f}..{x1:.1f}  z {z0:.1f}..{z1:.1f}  ({x1-x0:.1f} x {z1-z0:.1f} units)")
    print(f"crop px    col {px0:.0f}..{px1:.0f}  row {py0:.0f}..{py1:.0f}  ({px1-px0:.0f} x {py1-py0:.0f} px)")
    area = (x1 - x0) * (z1 - z0) / (WORLD_W * WORLD_H)
    print(f"area = {area*100:.1f}% of vanilla; at 2x zoom -> {area*4*100:.0f}% of vanilla, {2*(px1-px0):.0f} x {2*(py1-py0):.0f} px")
    for n, (la, lo) in SITES.items():
        x, z = to_world(la, lo); print(f"  {n:10s} world ({x:6.1f}, {z:6.1f})")

    raw = open("Z:/Claude/TerryClone/Vanilla/Map/terrain/campaigns/3k_dlc07_main_map/lf_height_map.dds", "rb").read()
    h = np.frombuffer(raw[len(raw) - RASTER_W * RASTER_H * 2:], "<u2").reshape(RASTER_H, RASTER_W)
    step = 4
    hs = h[::step, ::step].astype(float)
    v = (hs - hs.min()) / (np.percentile(hs, 99.5) - hs.min())
    rgb = np.stack([60 + 150 * v, 90 + 130 * v, 40 + 100 * v], -1).clip(0, 255).astype(np.uint8)
    img = Image.fromarray(rgb); d = ImageDraw.Draw(img)
    d.rectangle([px0 / step, py0 / step, px1 / step, py1 / step], outline=(255, 40, 40), width=3)
    for k, (x, z) in S.items():
        cx, cy = to_px(x, z); d.ellipse([cx/step-3, cy/step-3, cx/step+3, cy/step+3], fill=(255, 255, 255)); d.text((cx/step+5, cy/step-6), k, fill=(255, 255, 255))
    for n, (la, lo) in SITES.items():
        cx, cy = to_px(*to_world(la, lo)); d.ellipse([cx/step-4, cy/step-4, cx/step+4, cy/step+4], fill=(255, 220, 0)); d.text((cx/step+6, cy/step+2), n, fill=(255, 220, 0))
    img.save(os.path.join(HERE, "crop_full.png"))
    img.crop((int(px0/step) - 20, int(py0/step) - 20, int(px1/step) + 20, int(py1/step) + 20)).resize(
        (int((px1-px0)/step + 40) * 2, int((py1-py0)/step + 40) * 2)).save(os.path.join(HERE, "crop_north.png"))
