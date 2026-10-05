#!/usr/bin/env python3
"""No trees in or near settlements and roads (user rule, round 6) - map-wide, all settlements.

Mask = settlement footprints (slot >= 0 or sprawl) grown by TOWN_RING hexes, plus road hexes grown by ROAD_RING.
 - tree class raster terrain/<TREE> (quarter res): NO_TREE under the mask
 - trees.campaign_tree_list (map_extras, written by extras_main.py): instances inside the mask are dropped
Run after the carve (hex/map.hex final) and after class_fill / korea_fix; extras_main.py calls tree_mask() too.
"""
import os, struct, sys
from pathlib import Path
import numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
from regions_plan import load
from hexgrid import neighbour_arrays, nearest_hex
from terrain_main import QUARTER, NWW, NWH

TREE = "3k_dlc07_main_map.tree.191fd7dc12fe7e4.tif"
NO_TREE = 19
TOWN_RING, ROAD_RING = 2, 1
WIDE_TOWNS = {"ironic_central_yanmen_resource_1": 4}   # Yingtao (in game 2026-10-04: trees crowding the town)


def grow(m, NA, k):
    for _ in range(k):
        g = m.copy()
        for nr, nc, v in NA: g |= v & m[nr, nc]
        m = g
    return m


def tree_mask(hexp=HERE / "hex" / "map.hex"):
    f, names, w, h = load(hexp); NA = neighbour_arrays(h, w)
    town = (f["slot"] >= 0) | (f["sprawl"] > 0)
    road = (f["road"] > 0) | (f["bridge"] > 0)
    # 2026-10-04: no trees in the lakes (lake-build water meshes; in game shrubs stood in Juyan's water)
    lake = (f["terr"] == 1) & np.isin(f["region"], [i for i, n in enumerate(names) if "sea_lake" in n])
    # 2026-10-04: towns that looked crowded in game get a wider clearing (rings of hexes around their town hexes)
    wide = np.zeros_like(town)
    for name, rings in WIDE_TOWNS.items():
        if name in names: wide |= grow(town & (f["region"] == names.index(name)), NA, rings)
    return grow(town, NA, TOWN_RING) | grow(road, NA, ROAD_RING) | lake | wide, (w, h)


def hex_at(mask, wh, x, z):
    c, r = nearest_hex(np.asarray(x), np.asarray(z), *wh)
    return mask[np.clip(r, 0, wh[1] - 1), np.clip(c, 0, wh[0] - 1)]


def clear_raster(mask, wh):
    p = HERE / "terrain" / TREE; im = Image.open(p); a = np.array(im); before = (a == NO_TREE).mean()
    Wq, Hq = a.shape[1], a.shape[0]
    xs = (np.arange(Wq) + 0.5) / Wq * NWW
    for r0 in range(0, Hq, 256):
        r1 = min(Hq, r0 + 256); zs = (1 - (np.arange(r0, r1) + 0.5) / Hq) * NWH
        X, Z = np.broadcast_arrays(xs[None, :], zs[:, None])
        blk = a[r0:r1]; blk[hex_at(mask, wh, X, Z)] = NO_TREE; a[r0:r1] = blk
    res = Image.fromarray(a, "P"); res.putpalette(im.getpalette())
    res.save(p, compression="tiff_lzw", strip_size=res.size[0] * 2, tiffinfo={277: 1, 339: 1, 284: 1})
    print(f"tree raster: no-tree share {before:.1%} -> {(a == NO_TREE).mean():.1%}")


def filter_tree_list(path, mask, wh):
    d = Path(path).read_bytes(); ver, a, b, ww, wh_, n = struct.unpack_from("<IIIffI", d, 0); p = 24
    out = [d[:24]]; kept = dropped = 0
    for _ in range(n):
        ln = struct.unpack_from("<H", d, p)[0]; name = d[p + 2:p + 2 + ln]; p += 2 + ln
        cnt = struct.unpack_from("<I", d, p)[0]; p += 4; insts = []
        for _ in range(cnt):
            x, y, z, flag, var, sc = struct.unpack_from("<fffBBI", d, p); q = p + 18 + 4 * sc
            if hex_at(mask, wh, np.array([x]), np.array([z]))[0]: dropped += 1
            else: insts.append(d[p:q]); kept += 1
            p = q
        out.append(struct.pack("<H", ln) + name + struct.pack("<I", len(insts)) + b"".join(insts))
    assert p == len(d)
    Path(path).write_bytes(b"".join(out))
    print(f"tree list: {dropped:,} instances in/near settlements and roads or in lakes dropped, {kept:,} kept")


if __name__ == "__main__":
    m, wh = tree_mask(); print(f"mask: {m.mean():.1%} of hexes")
    import trees_x15; trees_x15.main()        # 2026-10-02: decoded-vanilla raster + town / road / river / coast clean-up
    tl = HERE / "map_extras" / "campaign_maps" / "3k_190e_expanded_map" / "display" / "trees" / "trees.campaign_tree_list"
    if tl.exists(): filter_tree_list(tl, m, wh)
