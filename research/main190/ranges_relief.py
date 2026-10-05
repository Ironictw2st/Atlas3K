#!/usr/bin/env python3
"""Real relief under the new steppe / Hexi mountain ranges (user 2026-10-03, option 1 of the "FloatingProps.png" fix).

The x15 ranges (x15_land.tile_clear: cold mountain tiles on the steppe_mountain / hexi_mountain masks) were painted on a
flat heightmap: thin bands of mountain tiles on flat ground render as flat-topped plateaus with cliff edges. This lifts
the AK height raster (terrain/<HEIGHT>, 8 px / hex, u16) under the mountain tiles of the new land:
  lift = A x profile(signed distance to the tile edge)   - starts FOOT hexes outside the edge (no step), full at RISE inside
  A    = PEAK x width factor (half-width of the band: thin bands get a lower ridge) x ridge noise x (1 - existing relief)
         (real DEM mountains, e.g. the Qilian, already have relief and are left nearly alone)
ONE-OFF, in place (marker hex/.ranges_relief); backup terrain/_pre_ranges_relief/. Tiles / map.hex unchanged."""
import json, shutil, sys, time
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
Image.MAX_IMAGE_PIXELS = None
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
HEIGHT = HERE / "terrain" / "3k_dlc07_main_map.height.191fd803c1a801d.tif"
TILE = Path(r"C:/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/assembly_kit_190E/raw_data/terrain/campaigns/3k_190e_expanded_map/tile_map.png")
MARK = HERE / "hex" / ".ranges_relief"
U2W = 0.000218712
PEAK, RISE, FOOT, FULL_HALF_WIDTH, RELIEF_OK = 1.5, 4.0, 1.5, 5.0, 1.0      # world units / hexes


def main(dry=False):
    if MARK.exists() and not dry: print("ranges relief already applied", MARK.read_text()); return
    import town_fix as T, caime_tilemap as CT, x15_land
    _, _, w, h, _, f, names = T.load(str(HERE / "hex" / "map.hex"))
    tm = CT.hex_codes(Image.open(TILE), w, h)
    M = x15_land.masks(w, h)
    newl = M["hexi_play"] | M["steppe_play"] | M["hexi_desert"] | M["hexi_mountain"] | M["steppe_mountain"]
    land = f["terr"] == 0
    mt = np.isin(tm, x15_land.MOUNTAIN_KINDS) & land & newl
    town = (f["slot"] >= 0) | (f["sprawl"] > 0)
    hgt = np.array(Image.open(HEIGHT)); H8, W8 = hgt.shape
    off = H8 - 8 * h                                                        # extra top rows (north edge)
    # hex-grid fields (row 0 = south) -> pixel grid
    sd_in = ndi.distance_transform_edt(mt)                                  # hexes inside to the edge
    sd_out = ndi.distance_transform_edt(~mt)                                # hexes outside to the band
    halfw = ndi.maximum_filter(sd_in, size=21)                              # local half-width of the band
    blk = hgt[off:, :8 * w].reshape(h, 8, w, 8).astype(np.float32)
    rel7 = (ndi.maximum_filter(blk.max((1, 3)), 7) - ndi.minimum_filter(blk.min((1, 3)), 7))[::-1] * U2W
    s = np.where(mt, sd_in, -sd_out)                                        # signed distance, + inside
    prof = np.clip((s + FOOT) / (RISE + FOOT), 0, 1); prof = prof * prof * (3 - 2 * prof)
    width = np.clip(halfw / FULL_HALF_WIDTH, 0.35, 1.0)
    keep = np.clip(1 - rel7 / RELIEF_OK, 0, 1)                              # real relief already: lift less
    near_band = ndi.maximum_filter(mt, size=2 * int(FOOT) + 3)
    lift_hex = PEAK * prof * width * keep * near_band * land                # world units, per hex
    lift_hex[ndi.binary_dilation(town, iterations=2)] = 0                   # towns stay where CAIME put them
    # pixel field: upsample the hex lift smoothly, add ridge noise at pixel scale
    rows = np.arange(H8 - off)[::-1] / 8.0 - 0.5; cols = np.arange(8 * w) / 8.0 - 0.5
    rr, cc = np.meshgrid(np.clip(rows, 0, h - 1), np.clip(cols, 0, w - 1), indexing="ij")
    lp = ndi.map_coordinates(lift_hex, [rr, cc], order=1)
    rng = np.random.default_rng(11)
    noise = ndi.gaussian_filter(rng.standard_normal(lp.shape), 10) ; noise /= noise.std() + 1e-9
    fine = ndi.gaussian_filter(rng.standard_normal(lp.shape), 3) ; fine /= fine.std() + 1e-9
    lp = lp * np.clip(0.8 + 0.25 * noise + 0.08 * fine, 0.35, 1.4)
    lp = ndi.gaussian_filter(lp, 3)
    du = np.rint(lp / U2W).astype(np.int64)
    new = hgt.astype(np.int64); new[off:, :8 * w] += du
    new = np.clip(new, 0, 65535).astype(np.uint16)
    print(f"ranges relief: {int(mt.sum()):,} mountain-tile hexes on new land; lift max {lp.max():.2f} u, "
          f"mean over band {float(lift_hex[mt].mean()):.2f} u; pixels raised {int((du > 0).sum()):,}")
    if dry: return lift_hex
    bk = HERE / "terrain" / "_pre_ranges_relief"; bk.mkdir(exist_ok=True); shutil.copy2(HEIGHT, bk / HEIGHT.name)
    im = Image.fromarray(new); im.save(HEIGHT, compression="tiff_lzw")
    MARK.write_text(json.dumps(dict(ts=time.strftime("%Y%m%d_%H%M%S"), hexes=int(mt.sum()), peak=PEAK)))
    print("wrote", HEIGHT)


if __name__ == "__main__":
    main(dry="--dry" in sys.argv)
