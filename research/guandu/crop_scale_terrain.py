#!/usr/bin/env python3
"""Crop + upscale the vanilla AK terrain rasters to match hex/map_x<S>/map.hex (crop_scale_map_hex.py).

The raster mapping follows the hex mapping exactly: new hex col c <- old col COL0 + c*CW/NW (same for rows), with
hex col c at world x = c*0.668 and hex row r at world z = r*0.772, so terrain and hexes line up.
Heights/sea: separable Catmull-Rom bicubic, u16, vertical values unchanged. Blend/tree/climate: nearest.
Outputs go to research/guandu/terrain/ (AK project file names kept so they can be dropped into a project copy).
"""
import os, sys, numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from crop_scale_map_hex import COL0, COL1, ROW0, ROW1, NW, NH

SRC = r"Z:/Claude/TerryClone/Vanilla/3k_dlc07_main_map"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "terrain")
OW, OH = 595.0999755859375, 541.7861938476562          # vanilla world size
CW, CH = COL1 - COL0, ROW1 - ROW0                      # cropped hexes
# Raster sizes follow vanilla: 8 px per hex column/row plus 4 px at the top for the odd columns' half-hex
# (vanilla 892x702 hexes -> 7136x5620). Sea = 1/2, tree/tile/quarter climate = 1/4 (tile map = 2*rows+1).
FULL = (NW * 8, NH * 8 + 4)
HALF = (FULL[0] // 2, FULL[1] // 2)
QUARTER = (FULL[0] // 4, FULL[1] // 4)
# world size of the rasters, at vanilla's pixels per world unit (DB extents use the hex rule instead)
NWW, NWH = FULL[0] * OW / 7136, FULL[1] * OH / 5620


def src_coords(n_out, new_world, old_world, n_src, axis):
    """Source pixel coordinate (float, centre-based) for each output pixel along one axis."""
    t = (np.arange(n_out) + 0.5) / n_out * new_world          # new world coord along axis (north-origin for z)
    if axis == "x":
        old = COL0 * 0.668 + t * CW / NW
        return old / old_world * n_src - 0.5
    z_new = new_world - t                                       # south-origin world z
    old_z = ROW0 * 0.772 + z_new * CH / NH
    return (1 - old_z / old_world) * n_src - 0.5


def cubic_weights(x):
    i = np.floor(x).astype(np.int64); f = (x - i).astype(np.float32)
    w = np.stack([((-0.5 * f + 1) * f - 0.5) * f, (1.5 * f - 2.5) * f * f + 1,
                  ((-1.5 * f + 2) * f + 0.5) * f, (0.5 * f - 0.5) * f * f], 1)
    return i, w


def resample_cubic(a, xs, ys):
    a = a.astype(np.float32)
    ix, wx = cubic_weights(xs); iy, wy = cubic_weights(ys)
    tmp = sum(a[:, np.clip(ix + k - 1, 0, a.shape[1] - 1)] * wx[:, k] for k in range(4))
    out = sum(tmp[np.clip(iy + k - 1, 0, a.shape[0] - 1), :] * wy[:, k, None] for k in range(4))
    return np.clip(np.rint(out), 0, 65535).astype(np.uint16)


def resample_nearest(a, xs, ys):
    ix = np.clip(np.rint(xs).astype(np.int64), 0, a.shape[1] - 1)
    iy = np.clip(np.rint(ys).astype(np.int64), 0, a.shape[0] - 1)
    return a[iy][:, ix]


def do(name, out_size, cubic, out_name=None):
    im = Image.open(os.path.join(SRC, name)); im.load()
    w, h = im.size
    xs = src_coords(out_size[0], NWW, OW, w, "x"); ys = src_coords(out_size[1], NWH, OH, h, "z")
    if cubic:
        arr = resample_cubic(np.array(im), xs, ys)
        from tiff16 import write_gray16                  # Terry-readable layout (PIL's single-strip TIFF is not)
        write_gray16(os.path.join(OUT, out_name or name), arr)
        res = Image.fromarray(arr)
    else:
        arr = resample_nearest(np.array(im), xs, ys)
        res = Image.fromarray(arr, im.mode)
        if im.mode == "P": res.putpalette(im.getpalette())
        # palette TIFFs in Atlas3K's TiffMap.WritePalette8 layout (what Terry reads): LZW, 2 rows per strip,
        # SamplesPerPixel=1, SampleFormat=UINT, PlanarConfig=contig
        tif = {"compression": "tiff_lzw", "strip_size": res.size[0] * 2, "tiffinfo": {277: 1, 339: 1, 284: 1}}
        res.save(os.path.join(OUT, out_name or name), **(tif if name.endswith(".tif") else {}))
    print(f"{name:48s} {w}x{h} -> {res.size[0]}x{res.size[1]} {'cubic' if cubic else 'nearest'}")
    return res


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    print(f"crop hexes {CW}x{CH} -> {NW}x{NH}; world {NWW:.3f} x {NWH:.3f}; full raster {FULL}")
    half, quarter = HALF, QUARTER
    do("3k_dlc07_main_map.height.191fd803c1a801d.tif", FULL, True)
    do("lf_heights.tif", FULL, True)
    do("3k_dlc07_main_map.sea_height.191fd804ab3801e.tif", half, True)
    do("lf_sea_heights.tif", half, True)
    do("3k_dlc07_main_map.blend.191fd8068da8020.tif", FULL, False)
    do("3k_dlc07_main_map.tree.191fd7dc12fe7e4.tif", quarter, False)
    # climate: full-res master + quarter-res [::4, ::4] sampling (what BOB's climate_map.cm expects)
    full_name = "climate_map.png" if Image.open(os.path.join(SRC, "climate_map.png")).size[0] == 7136 else "climate_map_g.png"
    full = do(full_name, FULL, False, "climate_map_g.png")
    Image.fromarray(np.array(full)[::4, ::4]).save(os.path.join(OUT, "climate_map.png"))
    print(f"climate_map.png (quarter, [::4,::4])                 -> {quarter[0]}x{quarter[1]}")
