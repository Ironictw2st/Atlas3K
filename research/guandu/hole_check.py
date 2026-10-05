#!/usr/bin/env python3
"""Land-mesh holes vs tile-map lines, per hex.

The land mesh (global_meshes/land_mesh_N.compressed_map, value 0 = hole) is cut open where line tiles (rivers,
roads, crossings, canals) and big rivers go; tile geometry / river meshes / sea meshes fill those holes. If the
meshes were built from a different tile list than the one the game places, the holes and the tiles disagree and
the ground is see-through beside the lines.

For every hex this finds the fraction of land-mesh samples that are holes, then compares with the tile map's
code for that hex (tilemap_hex: 2x2 px per hex). Run it on vanilla too: that is what "normal" looks like.

usage: hole_check.py <terrain dir> <tile_map.png> <hex cols> <hex rows> [out.png]
"""
import glob, os, struct, sys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
import compressed_map as CM  # noqa: E402
from hexgrid import nearest_hex  # noqa: E402
from tilemap_hex import hex_pixels, read_codes  # noqa: E402

LINE = {  # tile-map colours of line tile sets (tile_colours.json)
    0x0000ff: "river", 0xb4b4ff: "river_start", 0x7f00ff: "river_crossing", 0x2c067f: "river_crossing_imperial",
    0xda43ff: "river_crossing_track", 0x5d4218: "road_paved", 0xc10018: "road_imperial", 0x5d0018: "road_track",
    0x000068: "canal", 0x0037d0: "canal_links"}
WATER = {0x3971b7, 0x538dd5, 0xccccff}          # sea / river mouth: filled by sea meshes, holes expected


def hole_fraction(terrain, W, H):
    holes = np.zeros((H, W)); total = np.zeros((H, W))
    for p in glob.glob(os.path.join(terrain, "global_meshes", "land_mesh_*.compressed_map")):
        rm = open(p.replace(".compressed_map", ".rigid_model_v2"), "rb").read()
        mn = np.array(struct.unpack_from("<3f", rm, 0xA8 + 24)); mx = np.array(struct.unpack_from("<3f", rm, 0xA8 + 36))
        a, _ = CM.decode(p)
        h, w = a.shape
        ys, xs = np.mgrid[0:h, 0:w]
        X = mn[0] + (xs + 0.5) / w * (mx[0] - mn[0]); Z = mx[2] - (ys + 0.5) / h * (mx[2] - mn[2])
        c, r = nearest_hex(X.ravel(), Z.ravel(), W, H)
        np.add.at(total, (r, c), 1); np.add.at(holes, (r, c), (a.ravel() == 0))
    return np.where(total > 0, holes / np.maximum(total, 1), np.nan), total


def main(terrain, tile_map, W, H, out=None):
    frac, total = hole_fraction(terrain, W, H)
    code = read_codes(Image.open(tile_map))
    ys, xs = hex_pixels(W, H)
    hc = code[np.clip(ys, 0, code.shape[0] - 1), np.clip(xs, 0, code.shape[1] - 1)][..., 0]
    covered = total > 0
    hole = (frac > 0.25) & covered
    is_line = np.isin(hc, list(LINE)); is_water = np.isin(hc, list(WATER))
    print(f"hexes with land-mesh samples: {int(covered.sum())} of {W*H}")
    print(f"holes (>25% of samples): {int(hole.sum())}")
    print(f"  on line-tile hexes:  {int((hole & is_line).sum())}   of {int((is_line & covered).sum())} line hexes "
          f"({(hole & is_line).sum() / max(1, (is_line & covered).sum()):.0%})")
    print(f"  on water hexes:      {int((hole & is_water).sum())}")
    off = hole & ~is_line & ~is_water
    print(f"  on NEITHER (unexplained, see-through if nothing fills them): {int(off.sum())}")
    # a hole on a line hex's NEIGHBOUR ring suggests the holes are cut for a shifted/different line layout
    for name in sorted(set(LINE.values())):
        cs = [k for k, v in LINE.items() if v == name]
        m = np.isin(hc, cs) & covered
        if m.any(): print(f"    {name:26s} hexes {int(m.sum()):6d}  with hole {int((hole & m).sum()):6d}")
    if out:
        img = np.zeros((H, W, 3), np.uint8)
        img[is_line] = (90, 90, 90); img[hole & is_line] = (0, 200, 0); img[off] = (255, 0, 0); img[hole & is_water] = (0, 80, 200)
        Image.fromarray(img[::-1]).save(out)
        print("wrote", out, "(grey line tile, green hole on line, red hole on neither, blue hole on water)")


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], a[1], int(a[2]), int(a[3]), a[4] if len(a) > 4 else None)
