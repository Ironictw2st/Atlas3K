#!/usr/bin/env python3
"""Warp the 190E terrain rasters onto the new grid (Central Plains band warp + west/north padding).

Source (read-only): assembly_kit_190E raw_data/terrain/campaigns/3k_dlc07_main_map. Every output pixel is mapped
through the warp's inverse (any warp, 2-D): heights/sea Catmull-Rom cubic, blend/tree/climate/tile nearest. Raster sizes follow vanilla: 8 px per hex (+4 rows),
sea 1/2, tree/tile/quarter climate 1/4; world = pixels at vanilla's pixels-per-unit.
Padding pixels (source outside the 190E rasters) are recorded in pad_mask.png for the DEM pass (dem_fill.py).
Output: research/main190/terrain/.
"""
import os, sys
import numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "..", "guandu"))
from warp import Warp, current
from tiff16 import write_gray16

# 190E ORIGINAL rasters (the kit copy is overwritten by install_ak.py - re-reading it would warp twice)
SRC = r"Z:/Claude/TerryClone/output/backups/main190_originals_20260929_130639/ak190E_terrain_3k_dlc07_main_map"
OUT = os.path.join(HERE, "terrain")
OW, OH = 595.0999755859375, 541.7861938476562          # 190E / vanilla world size (7136 x 5620 px)
HX, HZ = 0.668, 0.772
WARP = current()
FULL = (WARP.W * 8, WARP.H * 8 + 4)
HALF = (FULL[0] // 2, FULL[1] // 2)
QUARTER = (FULL[0] // 4, FULL[1] // 4)
NWW, NWH = FULL[0] * OW / 7136, FULL[1] * OH / 5620    # new raster world size


_CACHE = {}


def src_xy(out_size, src_size, r0=0, r1=None):
    """Source pixel coordinates (float, centre-based) for output rows r0..r1 of a raster of out_size covering the
    new world: new px -> new hex -> WARP.inverse -> 190E hex -> 190E px. Works for any warp (not only separable).
    Cached on disk per (warp, sizes) in terrain/_srcxy/ (the pinned warp's inverse is iterative, so slow)."""
    r1 = out_size[1] if r1 is None else r1
    key = (tuple(out_size), tuple(src_size))
    if key not in _CACHE:
        import hashlib
        tag = hashlib.md5(repr((type(WARP).__name__, WARP.W, WARP.H, getattr(WARP, "groups", None) is not None and
                               [tuple(np.round(g[0], 3)) + (round(g[2], 3), round(g[3], 3)) for g in WARP.groups],
                               key)).encode()).hexdigest()[:12]
        d = os.path.join(OUT, "_srcxy"); os.makedirs(d, exist_ok=True); fn = os.path.join(d, f"{tag}.npy")
        if not os.path.exists(fn):
            arr = np.lib.format.open_memmap(fn + ".part.npy", "w+", np.float32, (2, out_size[1], out_size[0]))
            for a0 in range(0, out_size[1], 256):
                a1 = min(out_size[1], a0 + 256); sx, sy = _src_xy(out_size, src_size, a0, a1)
                arr[0, a0:a1] = sx; arr[1, a0:a1] = sy
            arr.flush(); del arr; os.replace(fn + ".part.npy", fn)
        _CACHE[key] = np.load(fn, mmap_mode="r")
    a = _CACHE[key]
    return np.asarray(a[0, r0:r1], np.float64), np.asarray(a[1, r0:r1], np.float64)


def _src_xy(out_size, src_size, r0, r1):
    t = (np.arange(out_size[0]) + 0.5) / out_size[0]; hx = t * NWW / HX
    u = (np.arange(r0, r1) + 0.5) / out_size[1]; hz = (NWH - u * NWH) / HZ
    HXg, HZg = np.broadcast_arrays(hx[None, :], hz[:, None])
    ox, oy = WARP.inverse(HXg, HZg)
    return ox * HX / OW * src_size[0] - 0.5, (1 - oy * HZ / OH) * src_size[1] - 0.5


def _cubic_w(t):
    t2, t3 = t * t, t * t * t                                                          # Catmull-Rom
    return [(-t3 + 2 * t2 - t) / 2, (3 * t3 - 5 * t2 + 2) / 2, (-3 * t3 + 4 * t2 + t) / 2, (t3 - t2) / 2]


def resample2d(a, out_size, cubic, chunk=256):
    """Resample a source raster onto the new grid through the warp (row chunks)."""
    h, w = a.shape[:2]; out = np.empty((out_size[1], out_size[0]) + a.shape[2:], np.uint16 if cubic else a.dtype)
    af = a.astype(np.float32) if cubic else a
    for r0 in range(0, out_size[1], chunk):
        r1 = min(out_size[1], r0 + chunk); sx, sy = src_xy(out_size, (w, h), r0, r1)
        if cubic:
            ix, iy = np.floor(sx).astype(np.int64), np.floor(sy).astype(np.int64)
            wx, wy = _cubic_w((sx - ix).astype(np.float32)), _cubic_w((sy - iy).astype(np.float32))
            acc = np.zeros(sx.shape, np.float32)
            for j in range(4):
                yy = np.clip(iy + j - 1, 0, h - 1); row = np.zeros(sx.shape, np.float32)
                for i in range(4): row += af[yy, np.clip(ix + i - 1, 0, w - 1)] * wx[i]
                acc += row * wy[j]
            out[r0:r1] = np.clip(np.rint(acc), 0, 65535).astype(np.uint16)
        else:
            out[r0:r1] = af[np.clip(np.rint(sy).astype(np.int64), 0, h - 1), np.clip(np.rint(sx).astype(np.int64), 0, w - 1)]
    return out


def pad_mask(out_size, src_size, inset=0.0, chunk=512):
    """True where the output pixel's source lies outside the 190E raster (shrunk by inset px)."""
    m = np.zeros((out_size[1], out_size[0]), bool)
    for r0 in range(0, out_size[1], chunk):
        r1 = min(out_size[1], r0 + chunk); sx, sy = src_xy(out_size, src_size, r0, r1)
        m[r0:r1] = (sx < inset - 0.5) | (sx > src_size[0] - 0.5 - inset) | (sy < inset - 0.5) | (sy > src_size[1] - 0.5 - inset)
    return m


def do(name, out_size, cubic, out_name=None):
    im = Image.open(os.path.join(SRC, name)); im.load()
    w, h = im.size
    arr = resample2d(np.array(im), out_size, cubic)
    if cubic:
        write_gray16(os.path.join(OUT, out_name or name), arr)
    else:
        res = Image.fromarray(arr, im.mode)
        if im.mode == "P": res.putpalette(im.getpalette())
        tif = {"compression": "tiff_lzw", "strip_size": res.size[0] * 2, "tiffinfo": {277: 1, 339: 1, 284: 1}}
        res.save(os.path.join(OUT, out_name or name), **(tif if name.endswith(".tif") else {}))
    print(f"{name:48s} {w}x{h} -> {out_size[0]}x{out_size[1]} {'cubic' if cubic else 'nearest'}")
    return (w, h)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    print(f"grid {WARP.W}x{WARP.H} hexes; full raster {FULL}; world {NWW:.3f} x {NWH:.3f}")
    (w, h) = do("3k_dlc07_main_map.height.191fd803c1a801d.tif", FULL, True)
    pad = pad_mask(FULL, (w, h))
    Image.fromarray((pad * 255).astype(np.uint8)).save(os.path.join(OUT, "pad_mask.png"))
    print(f"padding pixels: {pad.mean():.1%}")
    do("lf_heights.tif", FULL, True)
    do("3k_dlc07_main_map.sea_height.191fd804ab3801e.tif", HALF, True)
    do("lf_sea_heights.tif", HALF, True)
    do("3k_dlc07_main_map.blend.191fd8068da8020.tif", FULL, False)
    do("3k_dlc07_main_map.tree.191fd7dc12fe7e4.tif", QUARTER, False)
    # climate: the 190E folder currently holds the full-res map as climate_map.png (see climate_change.py)
    full_name = "climate_map.png" if Image.open(os.path.join(SRC, "climate_map.png")).size[0] == 7136 else "climate_map_g.png"
    do(full_name, FULL, False, "climate_map_g.png")
    Image.fromarray(np.array(Image.open(os.path.join(OUT, "climate_map_g.png")))[::4, ::4]).save(os.path.join(OUT, "climate_map.png"))
    print("climate_map.png (quarter, [::4, ::4])")
    do("tile_map.png", QUARTER, False, "tile_map_warped.png")
    open(os.path.join(OUT, "_fresh_warp"), "w").write("terrain_main output not yet used by dem_fill")   # dem_fill's guard
