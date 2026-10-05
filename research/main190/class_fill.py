#!/usr/bin/env python3
"""Fill the padding of the warped 190E class rasters (blend, tree). Run after dem_fill.py.

terrain_main.py leaves the padding as edge-clamped streaks. Blend classes here come from rules on real elevation
(DEM metres, see dem_fill.py) per geographic zone, using the 190E palette classes that 190E itself uses for that kind
of ground:
  desert 0 (Alxa) / 3 gray; mountain 4-7 (Qilian reds); steppe 19-22 (Ordos greens); forest 27.
  hexi   (lat >= 37, lon < 110): mountains > 2700 m (Qilian, Longshou); the oasis/steppe strip within OASIS hexes of
         them (the corridor itself); desert beyond (Badain Jaran, Gobi)
  tibet  (lat < 37, west):       mountains > 2500 m, else steppe/forest valleys (non-playable)
  steppe (110 <= lon < 120):     mountains > 1600 m (Yin shan, Greater Khingan), Gobi desert north of 42.3N & west
         of 113E, else grassland (Xianbei steppe)
  manchu (lon >= 120):           hills > 700 m forest/mountain, else grassland/forest plain
Zone edges are jittered with smooth noise. Within a class mix, the pick uses ranked two-octave smooth noise, so
the result is patches rather than speckle. The seam is dithered over SEAM hexes into the edge-clamped classes.
Tree classes are drawn from the 190E tree distribution for each blend class.
Climate keeps terrain_main's edge-clamped zones, and tile_map is regenerated from map.hex by build_tilemap.py.
Originals are in terrain/_warp_only/.
"""
import os, sys, shutil
import numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "..", "guandu"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "output", "pylibs"))
from terrain_main import src_xy, FULL, QUARTER, OW, OH
from dem_fill import mosaic, sample, box3, liang_weight
import rubber

T = os.path.join(HERE, "terrain"); KEEP = os.path.join(T, "_warp_only")
BLEND = "3k_dlc07_main_map.blend.191fd8068da8020.tif"
TREE = "3k_dlc07_main_map.tree.191fd7dc12fe7e4.tif"
PPH = 2                                   # quarter raster: px per hex
INSET_HEX, SEAM, OASIS = 4, 12, 14
DESERT = {0: .85, 3: .1, 19: .05}
MOUNTAIN = {4: .8, 5: .1, 6: .05, 7: .05}
STEPPE = {21: .4, 20: .2, 22: .2, 19: .2}
GRASS = {21: .45, 20: .15, 19: .2, 27: .2}
FOREST = {27: .6, 22: .3, 21: .1}
HILLS = {4: .5, 27: .4, 5: .1}


def smooth_noise(shape, cell, seed):
    rng = np.random.default_rng(seed)
    g = rng.uniform(-1, 1, (shape[0] // cell + 2, shape[1] // cell + 2))
    y = np.arange(shape[0]) / cell; x = np.arange(shape[1]) / cell
    y0, x0 = y.astype(int), x.astype(int); fy, fx = (y - y0)[:, None], (x - x0)[None, :]
    return (g[y0][:, x0] * (1 - fy) * (1 - fx) + g[y0][:, x0 + 1] * (1 - fy) * fx
            + g[y0 + 1][:, x0] * fy * (1 - fx) + g[y0 + 1][:, x0 + 1] * fy * fx)


def ranked(v):
    u = np.empty_like(v, dtype=np.float64); u[np.argsort(v, kind="stable")] = (np.arange(len(v)) + 0.5) / len(v)
    return u


def pick(mix, u):
    ks = np.array(list(mix)); cdf = np.cumsum(list(mix.values())); cdf /= cdf[-1]
    return ks[np.minimum(np.searchsorted(cdf, u), len(ks) - 1)]


def main():
    os.makedirs(KEEP, exist_ok=True)
    for n in (BLEND, TREE): shutil.copy2(os.path.join(T, n), os.path.join(KEEP, n))    # fresh terrain_main output
    size, src = QUARTER, (1784, 1405)
    xs, ys = src_xy(size, src)                                          # 2-D (any warp)
    ins = INSET_HEX * PPH
    dx = np.maximum(np.maximum(xs - (src[0] - 1 - ins), ins - xs), 0); dy = np.maximum(np.maximum(ys - (src[1] - 1 - ins), ins - ys), 0)
    d = np.maximum(dx, dy)
    WX = (xs + 0.5) / src[0] * OW; WZ = (1 - (ys + 0.5) / src[1]) * OH
    # the Liang zone (Hexi corridor, see dem_fill.py) is reclassified from the DEM too, not only the padding
    # natural (noisy) edge of the Liang zone instead of the 0.5 contour of a lat/lon ramp
    liang = liang_weight(WX, WZ) + 0.25 * smooth_noise(xs.shape, 10 * PPH, 31) > 0.5
    pad = (d > 0) | liang
    d = np.where(liang, SEAM * PPH, d)                                  # no seam dither in / next to the Liang zone
    mos = mosaic()
    m = sample(mos, WX, WZ)                                             # DEM metres (blurred), NaN = no tile
    import warp
    lon0, lat0 = (__import__("hexi_geo").to_lonlat if warp.is_hexi() else rubber.to_lonlat)(WX, WZ)
    lon = lon0 + 1.0 * smooth_noise(pad.shape, 24 * PPH, 1); lat = lat0 + 0.7 * smooth_noise(pad.shape, 24 * PPH, 2)
    zone = np.where(lon >= 120, 3, np.where(lon >= 110, 2, np.where(lat >= 37, 0, 1)))
    thr = np.array([2700, 2500, 1600, 700])[zone]
    mnt = np.nan_to_num(m) > thr
    # the corridor: non-mountain land below ~2300 m within ~OASIS hexes of the mountain front (Hexi: the band between
    # the Qilian and the Longshou / Heli hills) - round 6: wide enough to read as a corridor from the zoomed-out map
    near = (box3(mnt.astype(np.float32), OASIS * PPH // 2) > 0.002) & (np.nan_to_num(m, nan=9999) < 2300)
    u = ranked((0.5 * smooth_noise(pad.shape, 6 * PPH, 3) + smooth_noise(pad.shape, 24 * PPH, 4))[pad])
    zp, mp, np_, lonp, latp = zone[pad], mnt[pad], near[pad], lon[pad], lat[pad]
    gobi = (latp > 42.3) & (lonp < 113)
    cls = np.zeros(len(u), np.int64)
    rules = [((zp == 0) & mp, MOUNTAIN), ((zp == 0) & ~mp & np_, STEPPE), ((zp == 0) & ~mp & ~np_, DESERT),
             ((zp == 1) & mp, MOUNTAIN), ((zp == 1) & ~mp, FOREST),
             ((zp == 2) & mp, MOUNTAIN), ((zp == 2) & ~mp & gobi, DESERT), ((zp == 2) & ~mp & ~gobi, GRASS),
             ((zp == 3) & mp, HILLS), ((zp == 3) & ~mp, FOREST)]
    for sel, mix in rules:
        cls[sel] = pick(mix, u[sel])
    import tifffile
    hq = tifffile.imread(os.path.join(T, "3k_dlc07_main_map.height.191fd803c1a801d.tif"))[::4, ::4][:size[1], :size[0]]
    water = ((np.nan_to_num(m, nan=1.0) <= 0) | (hq < 14220))[pad]            # DEM sea or (no DEM) warped sea
    # blend at quarter res -> upsample x4 to FULL; seam dither against the clamped classes
    im = Image.open(os.path.join(KEEP, BLEND)); full = np.array(im)
    q = full[::4, ::4][:size[1], :size[0]].copy()
    st = np.clip(d[pad] / (SEAM * PPH), 0, 1)
    # seam dither with smooth noise (blotches, not a per-pixel checkerboard stripe along the old map edge)
    keep = ranked(smooth_noise(pad.shape, 3 * PPH, 32)[pad]) < 1 - st * st * (3 - 2 * st)
    newq = q.copy(); newq[pad] = np.where(keep | water, q[pad], cls)
    up = np.repeat(np.repeat(newq, 4, 0), 4, 1)[:FULL[1], :FULL[0]]
    padF = np.repeat(np.repeat(pad, 4, 0), 4, 1)[:FULL[1], :FULL[0]]
    out = np.where(padF, up, full).astype(np.uint8)
    res = Image.fromarray(out, "P"); res.putpalette(im.getpalette())
    tif = {"compression": "tiff_lzw", "strip_size": res.size[0] * 2, "tiffinfo": {277: 1, 339: 1, 284: 1}}
    res.save(os.path.join(T, BLEND), **tif)
    print(f"{BLEND}: zone share {np.round(np.bincount(zp, minlength=4) / len(zp), 2)}; mountain {mp.mean():.0%}")
    # trees: per blend class, the 190E tree-class distribution
    tim = Image.open(os.path.join(KEEP, TREE)); tr = np.array(tim)
    tab = np.zeros((256, 256), np.int64); np.add.at(tab, (q[~pad], tr[~pad]), 1)
    ut = ranked((smooth_noise(pad.shape, 4 * PPH, 6) + 0.5 * smooth_noise(pad.shape, 16 * PPH, 7))[pad])
    bq = newq[pad]; tcls = tr[pad].copy()
    for b in np.unique(bq):
        sel = (bq == b) & ~keep
        if not sel.any() or tab[b].sum() == 0: continue
        tcls[sel] = np.minimum(np.searchsorted(np.cumsum(tab[b]) / tab[b].sum(), ut[sel]), 255)
    tout = tr.copy(); tout[pad] = tcls
    res = Image.fromarray(tout.astype(np.uint8), "P"); res.putpalette(tim.getpalette())
    res.save(os.path.join(T, TREE), **tif | {"strip_size": res.size[0] * 2})
    print(f"{TREE}: filled {pad.sum()} px")


if __name__ == "__main__":
    main()
