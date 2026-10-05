#!/usr/bin/env python3
"""Open ground around towns that sit in tree-heavy tile variants (2026-10-04, user: "repaint Yingtao").

Yingtao (ironic_central_yanmen_resource_1) sits on generic tiles of the TEMPERATE climate, whose tile meshes carry their
own broad-leaved trees (no props / tree-list trees there: checked in game and in the Atlas3K viewer); the clear
northern towns (Wuquan, Chengle) sit on generic tiles of the COLD climate. This paints a disc of cold climate around the
listed towns in climate_map.png (tile-map size, picks the tile climate) and climate_map_g.png (full size), in the
research terrain/ AND the kit, so the tile matcher picks the open cold variants there. The ground texture (blend map)
is a separate raster and is not touched. Idempotent (painting the same colour twice changes nothing); backups of the
first run in terrain/_pre_town_climate/ and <kit>/_pre_town_climate/.
"""
import shutil
from pathlib import Path
import numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
HERE = Path(__file__).parent
KIT = Path(r"C:/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/assembly_kit_190E/raw_data/terrain/campaigns/3k_190e_expanded_map")
WW, WH = 11824 * 0.08339405829596414, 9068 * 0.09640323665480427     # world size (lf grid x pixel size)
COLD = (0, 85, 85)
TOWNS = {}   # x, z, radius (world units). Yingtao was painted and REVERTED 2026-10-04 (its trees are its timber resource building, not tile vegetation)


def paint(path):
    im = Image.open(path); mode = im.mode; a = np.array(im.convert("RGB"))
    H, W = a.shape[:2]; changed = 0
    for name, (x, z, r) in TOWNS.items():
        cx, cy = x / WW * W, (WH - z) / WH * H
        rx, ry = r / WW * W, r / WH * H
        y0, y1 = int(cy - ry * 1.3) - 1, int(cy + ry * 1.3) + 2
        x0, x1 = int(cx - rx * 1.3) - 1, int(cx + rx * 1.3) + 2
        yy, xx = np.mgrid[y0:y1, x0:x1]
        d = np.hypot((xx - cx) / rx, (yy - cy) / ry)
        ang = np.arctan2(yy - cy, xx - cx)
        edge = 1 + 0.12 * np.sin(3 * ang + 1.3) + 0.08 * np.sin(7 * ang + 0.4)   # a slightly irregular rim
        m = d <= edge
        blk = a[y0:y1, x0:x1]
        before = (blk[m] != COLD).any(axis=1).sum()
        blk[m] = COLD; a[y0:y1, x0:x1] = blk; changed += int(before)
    if changed:
        bak = path.parent / "_pre_town_climate"
        bak.mkdir(exist_ok=True)
        if not (bak / path.name).exists(): shutil.copy2(path, bak / path.name)
        out = Image.fromarray(a, "RGB")
        out = out.convert(mode) if mode not in ("RGB",) else out
        out.save(path)
    return changed


if __name__ == "__main__":
    for root in (HERE / "terrain", KIT):
        for f in ("climate_map.png", "climate_map_g.png"):
            print(f"{root.name}/{f}: {paint(root / f)} px set to cold")
