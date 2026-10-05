#!/usr/bin/env python3
"""Data for the Blender north test (tools/blender/north_test.py): a terrain patch around the Goguryeo / Changbai highland
and the height field of one ridge for the custom mountain prop, both in game world units (x east, z north, y up;
lf u16 -> world = u * 0.000218712 - 3.12725). Writes korea_ref/north_test_data.npz."""
import json, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
import town_fix as T
from hexgrid import HX, HZ
from regions_carve import hex_blend_and_height
U2W = 0.000218712; W0 = 3.12725


def main():
    _, _, w, h, _, f, names = T.load(str(HERE / "hex" / "map.hex"))
    plan = json.load(open(HERE / "korea_ref" / "north_plan.json", encoding="utf-8"))
    _, hh = hex_blend_and_height(w, h)
    y = hh.astype(np.float32) * U2W - W0
    # the ridge: the highest mountain prop site of the plan
    site = max(plan["mountain_props"], key=lambda p: y[p["hex"][1], p["hex"][0]])
    sc, sr = site["hex"]
    R = 24                                                         # hexes around the ridge for the prop mesh
    r0, r1, c0, c1 = sr - R, sr + R + 1, sc - R, sc + R + 1
    ridge = y[r0:r1, c0:c1]
    # terrain patch: 140 x 110 hexes around the site (decimated x2 for Blender)
    tr0, tr1, tc0, tc1 = max(0, sr - 55), min(h, sr + 55), max(0, sc - 70), min(w, sc + 70)
    terr = y[tr0:tr1:2, tc0:tc1:2]
    biome = np.zeros((h, w), np.int8)
    code = {"highland": 1, "taiga": 2, "mixed": 3, "steppe": 4}
    for r, runs in plan["biome_rle"].items():
        for s, n, b in runs: biome[int(r), s:s + n] = code[b]
    np.savez_compressed(HERE / "korea_ref" / "north_test_data.npz",
                        ridge=ridge, ridge_origin=np.array([c0 * HX, r0 * HZ]), hx=HX, hz=HZ,
                        site=np.array([site["x"], site["z"], y[sr, sc]]),
                        terr=terr, terr_origin=np.array([tc0 * HX, tr0 * HZ]), terr_step=2,
                        biome=biome[tr0:tr1:2, tc0:tc1:2], water=(f["terr"][tr0:tr1:2, tc0:tc1:2] == 1),
                        props=np.array([[p["x"], p["z"]] for p in plan["mountain_props"]]))
    print("site", site, "ridge relief", float(ridge.max() - np.median(ridge)), "terrain patch", terr.shape)


if __name__ == "__main__":
    main()
