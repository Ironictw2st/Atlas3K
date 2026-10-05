#!/usr/bin/env python3
"""Ground seating for mountain / rock props (user 2026-10-03: "some mountain props are floating").

A mountain mesh has a flat base at y = 0 and a footprint of LOD0 radius x scale (korea_ref/model_radius.json); placed
at the ground height of its centre on uneven ground, the base edges hang over the lower ground (north_dress peaks /
ridges: ~9 units across, centre a median 1.4 units above the lowest ground under them). seat_y() = the lowest ground
under FOOT x footprint, minus SINK. reseat_delta() keeps a warped stock prop's clearance: the change of the centre
ground between the original 190E terrain at the old position and the current terrain at the new position."""
import json, re
from pathlib import Path
import numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
HERE = Path(__file__).parent
U2W = 0.000218712; W0 = 3.12725
HX, HZ = 0.668, 0.772
FOOT, SINK = 0.6, 0.05
CUR = HERE / "terrain" / "3k_dlc07_main_map.height.191fd803c1a801d.tif"
ORIG = Path(r"Z:/Claude/TerryClone/output/backups/main190_originals_20260929_130639/ak190E_terrain_3k_dlc07_main_map/3k_dlc07_main_map.height.191fd803c1a801d.tif")
_H, _R = {}, None


def _hgt(which):
    if which not in _H: _H[which] = np.array(Image.open(CUR if which == "cur" else ORIG))
    return _H[which]


def radius(entity_text):
    global _R
    if _R is None: _R = json.load(open(HERE / "korea_ref" / "model_radius.json"))
    m = re.search(r'model_path="([^"]*)"', entity_text)
    sc = re.search(r'scale="([-\d.e]+) ([-\d.e]+) ([-\d.e]+)"', entity_text)
    s = max(abs(float(sc.group(1))), abs(float(sc.group(3)))) if sc else 1.0
    return _R.get(m.group(1).replace("\\", "/").lower(), 0.0) * s if m else 0.0


def is_mountain(entity_text):
    m = re.search(r'model_path="([^"]*)"', entity_text)
    mp = m.group(1).replace("\\", "/").lower() if m else ""
    return "/mountains/" in mp or "/rocks/" in mp


def low_ground(x, z, rad, which="cur"):
    h = _hgt(which); H8, W8 = h.shape
    px = min(max(int(round(x / HX * 8 + 4)), 0), W8 - 1); py = min(max(int(round(H8 - 1 - (z / HZ * 8 + 4))), 0), H8 - 1)
    k = max(0, int(rad * FOOT / HX * 8))
    win = h[max(0, py - k):py + k + 1, max(0, px - k):px + k + 1]
    return float(win.min()) * U2W - W0


_SINK = None


def seat_y(x, z, rad, model=None, scale=None):
    """Vanilla's own depth for this model when known (korea_ref/vanilla_sink.json, vanilla_sink.py: big mountain meshes
    are buried ~50-70 model units x scale so only the top shows); else the lowest ground under the footprint."""
    global _SINK
    if _SINK is None:
        p = HERE / "korea_ref" / "vanilla_sink.json"
        _SINK = json.load(open(p)) if p.exists() else {}
    k = (model or "").replace("\\", "/").lower()
    if k in _SINK and scale:
        return low_ground(x, z, 0) + _SINK[k]["sink"] * scale
    return low_ground(x, z, rad) - (SINK if rad > 2 else 0.0)


def reseat_delta(ox, oz, nx, nz, rad):
    # centre ground only: the warp stretches the terrain under unscaled props, so a footprint minimum compares unlike
    # areas (tried 2026-10-03: raised 481 stock props); the centre keeps 190E's own clearance
    return low_ground(nx, nz, 0, "cur") - low_ground(ox, oz, 0, "orig")


# 2026-10-03 (user screenshot "Floating.png"): 3K mountain tiles carry their own height; 190E's mountain / terrace props
# stand on them ~2 units above the lf ground. Where a tile rule (x15_land.tile_clear tier 1 / 2, Korea north, the tile
# editor) replaced that tile, the prop hangs in the air -> seat it on the ground instead.
TILE_CUR = Path(r"C:/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/assembly_kit_190E/raw_data/terrain/campaigns/3k_190e_expanded_map/tile_map.png")
TILE_ORIG = ORIG.parent / "tile_map.png"
HEX_ORIG = ORIG.parent.parent / "190Expanded_map.hex"
_T = None


def _tiles():
    global _T
    if _T is None:
        import sys
        for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
        import town_fix as T, caime_tilemap as CT
        _, _, w, h, _, _, _ = T.load(str(HERE / "hex" / "map.hex")); _, _, ow, oh, _, _, _ = T.load(str(HEX_ORIG))
        cur = TILE_CUR if TILE_CUR.exists() else HERE / "tile_map_rebuilt.png"
        _T = (CT.hex_codes(Image.open(cur), w, h), w, h, CT.hex_codes(Image.open(TILE_ORIG), ow, oh), ow, oh)
    return _T


def tile_changed(ox, oz, nx, nz):
    from hexgrid import nearest_hex
    cur, w, h, org, ow, oh = _tiles()
    c, r = nearest_hex(np.array([nx]), np.array([nz]), w, h); oc, orr = nearest_hex(np.array([ox]), np.array([oz]), ow, oh)
    return int(cur[r[0], c[0]]) != int(org[orr[0], oc[0]])
