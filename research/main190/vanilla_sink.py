#!/usr/bin/env python3
"""Per-model vanilla sink depth for mountain / rock props (2026-10-03, "FloatingRock.png").
From the ORIGINAL 190E layers: median (y - centre ground) / scale per model -> korea_ref/vanilla_sink.json.
Vanilla buries big mountain meshes deep (cold_ridge_small_1: origin ~67 model units x scale below the ground) so only
the top shows; north_dress used the lowest ground under the footprint and the whole lower mesh stood in the air."""
import re, glob, json, collections
from pathlib import Path
import numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
HERE = Path(__file__).parent
ORIG = "Z:/Claude/TerryClone/output/backups/main190_originals_20260929_130639/ak190E_terrain_3k_dlc07_main_map/"
HX, HZ = 0.668, 0.772


def main():
    hgt = np.array(Image.open(ORIG + "3k_dlc07_main_map.height.191fd803c1a801d.tif")); H8, W8 = hgt.shape
    def g(x, z):
        px = min(max(int(round(x / HX * 8 + 4)), 0), W8 - 1); py = min(max(int(round(H8 - 1 - (z / HZ * 8 + 4))), 0), H8 - 1)
        return hgt[py, px] * 0.000218712 - 3.12725
    terry = open(ORIG + "3k_dlc07_main_map.terry", encoding="utf-8", errors="replace").read(); used = set(re.findall(r'id="([0-9a-f]+)"', terry))
    S = collections.defaultdict(list)
    for p in glob.glob(ORIG + "*.layer"):
        if p.split(".")[-2] not in used: continue
        t = open(p, encoding="utf-8", errors="replace").read()
        for m in re.finditer(r'model_path="([^"]*/(?:mountains|rocks)/[^"]*)".*?position="([^ ]+) ([^ ]+) ([^"]+)".*?scale="([^ ]+)', t, re.S):
            x, y, z, s = float(m.group(2)), float(m.group(3)), float(m.group(4)), float(m.group(5))
            S[m.group(1).replace("\\", "/").lower()].append((y - g(x, z)) / s)
    out = {k: dict(n=len(v), sink=round(float(np.median(v)), 3)) for k, v in S.items() if len(v) >= 3}
    json.dump(out, open(HERE / "korea_ref" / "vanilla_sink.json", "w"), indent=0)
    for k in sorted(out, key=lambda k: -out[k]["n"]):
        if "terrace" not in k: print(f"{k.split('/')[-1]:40s} n {out[k]['n']:4d} sink/scale {out[k]['sink']}")


if __name__ == "__main__":
    main()
