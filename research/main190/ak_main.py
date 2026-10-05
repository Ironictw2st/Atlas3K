#!/usr/bin/env python3
"""Assemble the warped 3k_dlc07_main_map assembly-kit terrain project (190E project + research/main190/terrain).

This is research/guandu/build_ak_project.py with the uniform crop/scale replaced by the main190 warp:
  new world (x, z) = WarpMapping.fwd_world(old x, old z)   (hex world units; row 0 / z = 0 is the south edge)
- ECTransform positions (absolute) are warped. Sizes, rotations, point clouds and light radii are kept, so
  objects stay life-size and the Central Plains props just spread out.
- River splines: every point is warped (absolute), tangents are scaled by the local Jacobian, and width is kept
  (the map scale outside the band is unchanged; BOB rebuilds the meshes).
- Polylines (absolute points): every point is warped.
- BOB-generated river meshes (model_path terrain/campaigns/<map>/models/...) are dropped; BOB rebuilds them.
- Nothing is dropped for position: the warp maps the old world onto a sub-area of the new one.
Output: research/main190/ak/3k_dlc07_main_map (same map name: the pack overrides the main map).
"""
import os, re, shutil, sys, glob
import numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "..", "guandu"))
from warp import Warp, WarpMapping, current
from terrain_main import FULL, HALF, QUARTER, NWW, NWH
from build_ak_project import ENT, POS, f
import north_cull

NAME = "3k_dlc07_main_map"
# 190E ORIGINAL project (the kit copy is overwritten by install_ak.py - re-reading it would warp twice)
SRC_DIR = r"Z:/Claude/TerryClone/output/backups/main190_originals_20260929_130639/ak190E_terrain_3k_dlc07_main_map"
VANILLA_RIVERS = r"Z:/Claude/TerryClone/Vanilla/3k_dlc07_main_map/3k_dlc07_main_map.1972bd217a4938e.layer"
RAST = os.path.join(HERE, "terrain")
OUT = os.path.join(HERE, "ak", NAME)
MAP = WarpMapping(current())
SKIP = {"o.tif", "lf_sea_heights_working.tif"}                       # 190E scratch files, not referenced


def fwd(x, z):
    nx, nz = MAP.fwd_world(x, z); return float(nx), float(nz)


def jac(x, z, e=0.05):
    """d(new)/d(old) at (x, z): 2x2 [[dx'/dx, dx'/dz], [dz'/dx, dz'/dz]]."""
    a = np.array(fwd(x + e, z)) - np.array(fwd(x - e, z)); b = np.array(fwd(x, z + e)) - np.array(fwd(x, z - e))
    return np.stack([a, b], 1) / (2 * e)


def do_river(e):
    m = POS.search(e); px, py, pz = map(float, m.group(2).split())
    PT = r'<point position="([^"]*)" tangent_in="([^"]*)" tangent_out="([^"]*)" width="([^"]*)"'
    pts = list(re.finditer(PT, e))
    absn = []
    for p in pts:
        rx, ry, rz = map(float, p.group(1).split(","))
        nx, nz = fwd(px + rx, pz + rz); absn.append((nx, py + ry, nz, jac(px + rx, pz + rz)))
    ox, oy, oz, _ = absn[0]
    out, idx = [], 0
    for line in e.split("\n"):
        pm = re.search(PT, line)
        if pm:
            x, y, z, J = absn[idx]; idx += 1
            def tg(v):
                a, b, c = map(float, v.split(",")); t = J @ np.array([a, c]); return f"{f(t[0])},{f(b)},{f(t[1])}"
            line = line.replace(pm.group(0), f'<point position="{f(x-ox)},{f(y-oy)},{f(z-oz)}" tangent_in="{tg(pm.group(2))}" '
                                f'tangent_out="{tg(pm.group(3))}" width="{pm.group(4)}"')
        out.append(line)
    return POS.sub(lambda m: f'{m.group(1)}{f(ox)} {f(oy)} {f(oz)}{m.group(3)}', "\n".join(out), count=1)


def do_entity(e, stats):
    if "<ECTransform" not in e: return e
    if re.search(r'model_path="terrain/campaigns/[^"]*/models/', e, re.I): stats["bob_mesh"] += 1; return None
    if "<ECRiverSpline" in e: stats["river"] += 1; return do_river(e)
    if "<ECPolyline" in e:
        stats["polyline"] += 1
        return re.sub(r'<point x="([^"]*)" y="([^"]*)"/>',
                      lambda m: '<point x="%s" y="%s"/>' % tuple(map(f, fwd(float(m.group(1)), float(m.group(2))))), e)
    m = POS.search(e); x, y, z = m.group(2).split()
    nx, nz = fwd(float(x), float(z))
    import x15_land
    nx, nz = x15_land.jeju_warp(nx, nz)                  # Jeju enlarged in place (jeju_scale.py)
    if north_cull.drop_prop(e, nx, nz): stats["north_cull"] = stats.get("north_cull", 0) + 1; return None   # north cull (user)
    import x15_land
    if x15_land.drop_prop(e, nx, nz): stats["x15_new_land"] = stats.get("x15_new_land", 0) + 1; return None     # x15 new land
    import prop_removals                                     # 2026-10-03: user-requested removals (korea_ref/prop_removals.json)
    if prop_removals.removed(e, nx, nz): stats["user_removed"] = stats.get("user_removed", 0) + 1; return None
    import town_props_scan                                   # 2026-10-02: no mountain / tree meshes burying the new towns
    hit, why = town_props_scan.covered(e, nx, nz)
    if hit:
        k = "town_veg" if why.startswith("vegetation") else "town_mountain"
        stats[k] = stats.get(k, 0) + 1; return None
    stats["kept"] += 1
    import prop_seat                                         # 2026-10-03: warped mountains / rocks keep their ground clearance
    if prop_seat.is_mountain(e):
        d = prop_seat.reseat_delta(float(x), float(z), nx, nz, prop_seat.radius(e))
        if abs(d) > 0.05:
            stats["reseated"] = stats.get("reseated", 0) + 1; y = f(float(y) + d)
        g = prop_seat.low_ground(nx, nz, 0)                  # lost its mountain tile: down onto the ground
        if float(y) - g > 0.3 and prop_seat.tile_changed(float(x), float(z), nx, nz):
            stats["tile_lost"] = stats.get("tile_lost", 0) + 1; y = f(prop_seat.seat_y(nx, nz, prop_seat.radius(e), re.search(r'model_path="([^"]*)"', e).group(1),
                                                                         float(re.search(r'scale="([-\d.e]+)', e).group(1))))
    return POS.sub(lambda m: f'{m.group(1)}{f(nx)} {y} {f(nz)}{m.group(3)}', e, count=1)


def do_layer(text, stats):
    dropped = set()
    def rep(m):
        r = do_entity(m.group(0), stats)
        if r is None: dropped.add(m.group(2)); return ""
        return r
    text = ENT.sub(rep, text)
    text = re.sub(r'\s*<to id="([0-9a-f]+)"/>', lambda m: "" if m.group(1) in dropped else m.group(0), text)
    return re.sub(r'\s*<from id="[0-9a-f]+">\s*</from>', "", text)


def main():
    if os.path.exists(OUT): shutil.rmtree(OUT)
    os.makedirs(OUT)
    stats = {k: 0 for k in ("kept", "polyline", "river", "bob_mesh")}
    layers = glob.glob(os.path.join(SRC_DIR, f"{NAME}.*.layer"))
    for p in layers:
        # rivers: 190E's layer is the old hand-guessed one (river_6 by Hedong/Chang'an ~2 units east of the real
        # river; 2 rivers hidden in the unseen shroud). 190E shipped vanilla's river meshes, so it never showed.
        # Use the vanilla layer rebuilt from those meshes (Vanilla/, same layer id and entity ids) instead.
        src = VANILLA_RIVERS if os.path.basename(p) == os.path.basename(VANILLA_RIVERS) else p
        t = open(src, encoding="utf-8").read()
        open(os.path.join(OUT, os.path.basename(p)), "w", encoding="utf-8", newline="").write(do_layer(t, stats))
    # rasters: the warped/filled set (tree_new is 190E's copy of the tree raster under the same id: written from ours)
    tree = [n for n in os.listdir(RAST) if ".tree." in n][0]
    for fn in os.listdir(RAST):
        p = os.path.join(RAST, fn)
        if os.path.isdir(p) or fn.startswith("preview") or fn in ("pad_mask.png", "tile_map_warped.png"): continue
        shutil.copy2(p, os.path.join(OUT, fn))
    shutil.copy2(os.path.join(RAST, tree), os.path.join(OUT, tree.replace(".tree.", ".tree_new.")))
    # vanilla layout (BOB's Tilemap requires climate_map.png = tile-map size): climate_map.png quarter-res,
    # climate_map_g.png full-res - as terrain_main.py writes them (190E's folder had them the other way round)
    assert Image.open(os.path.join(OUT, "climate_map.png")).size == QUARTER
    for fn in ("climate_change.py", f"{NAME}.terry.user"):
        shutil.copy2(os.path.join(SRC_DIR, fn), OUT)
    tm = os.path.join(HERE, "tile_map_rebuilt.png")
    if os.path.exists(tm):
        im = Image.open(tm); assert im.size == QUARTER, (im.size, QUARTER); im.save(os.path.join(OUT, "tile_map.png"))
    else:
        print("WARNING: tile_map_rebuilt.png missing (run tilemap_main.py); tile_map.png not written")
    t = open(os.path.join(SRC_DIR, f"{NAME}.terry"), encoding="utf-8").read()
    sizes = {"BlendCampaign": FULL, "LowFrequencyHeight": FULL, "LowFrequencyHeightSea": HALF, "CampaignTree": QUARTER}
    for typ, (w, h) in sizes.items():
        t, n = re.subn(rf'(type="{typ}" size=")\d+x\d+(")', rf"\g<1>{w}x{h}\g<2>", t); assert n == 1, typ
    open(os.path.join(OUT, f"{NAME}.terry"), "w", encoding="utf-8", newline="").write(t)
    for typ, (w, h) in sizes.items():
        lid = re.search(rf'type="{typ}" size="[^"]*" id="[0-9a-f]+"/>\s*<pc type="QTU::TerrainMapLayer">\s*<data id="([0-9a-f]+)"', t).group(1)
        fns = [x for x in os.listdir(OUT) if lid in x]
        for fn in fns:
            assert Image.open(os.path.join(OUT, fn)).size == (w, h), (fn, Image.open(os.path.join(OUT, fn)).size, (w, h))
        print(f"{typ:22s} {w}x{h} {fns}")
    # lake_props.add (2026-10-02 small_lake_1 discs) retired 2026-10-04: kit_edits.py runs lake-build on the kit instead
    import north_dress; north_dress.add(OUT, NAME)     # 2026-10-02: steppe + Hexi dressing (rocks, groves, ridges, Han wall)
    import village_dress; village_dress.add(OUT, NAME) # 2026-10-03: vanilla-standard villages / nomad camps in every new region
    import layer_sort; layer_sort.sort(OUT, NAME)       # 2026-10-03: generated props into per-region layers (new .terry Scene layers)
    missing = set(os.listdir(SRC_DIR)) - set(os.listdir(OUT)) - SKIP
    print(f"{len(layers)} layers -> {OUT}\n{stats}\nsource files not carried over: {sorted(missing)}")


if __name__ == "__main__":
    main()
