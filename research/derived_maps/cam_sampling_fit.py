"""Which sampling rectangle matches BOB's camera map on terrain-only pixels? (lf grid 4 px per camera cell)"""
import numpy as np
from PIL import Image

V = r"Z:\Claude\TerryClone\Vanilla\Map\terrain\campaigns\3k_dlc07_main_map"
HERE = r"Z:\Claude\TerryClone\research\derived_maps"
im = Image.open(HERE + r"\campaign_maps__3k_dlc07_main_map__camera_heightmap.png")
van = np.array(im).astype(float) * float(im.info['height_scale'])
ours_im = Image.open(r"Z:\Claude\TerryClone\output\native_build_test\campaign_maps\3k_dlc07_main_map\camera_heightmap.png")
ours = np.array(ours_im).astype(float) * float(ours_im.info['height_scale'])
b = open(V + r"\lf_height_map.dds", 'rb').read()
L = np.maximum(np.frombuffer(b, '<u2', offset=128, count=7136 * 5620).reshape(5620, 7136).astype(float) * 0.000218712 - 3.12725, 0)
H, W = L.shape
ch, cw = van.shape
Lp = np.pad(L, 3, mode='edge')


def rect_max(r0, c0, size):
    """max over L[r0 + i, c0 + j] for i, j in [0, size), per camera cell; r0, c0 arrays of lf coords (unpadded)."""
    out = np.full((ch, cw), -1e9)
    for i in range(size):
        for j in range(size):
            out = np.maximum(out, Lp[(r0 + i + 3)[:, None], (c0 + j + 3)[None, :]])
    return out


ys, xs = np.arange(ch), np.arange(cw)
variants = {
    'block top-down [4y,4y+4)': rect_max(4 * ys, 4 * xs, 4),
    'corner top-down [4y-2,4y+2]': rect_max(4 * ys - 2, 4 * xs - 2, 5),
    'corner south-origin': rect_max(np.clip(H - 1 - 4 * ys - 2, -3, H), 4 * xs - 2, 5),
    'corner top-down [4y-2,4y+2)': rect_max(4 * ys - 2, 4 * xs - 2, 4),
}
terrain_only = np.abs(ours - variants['block top-down [4y,4y+4)']) < 1e-3   # cells where our props add nothing
mask = terrain_only & (van > 0.05)
print('cells', mask.sum())
for name, est in variants.items():
    e = np.abs(est - van)[mask]
    print(f'{name:32s} median {np.median(e):.4f}  mean {e.mean():.4f}  frac<0.01 {(e < 0.01).mean():.3f}  frac<0.05 {(e < 0.05).mean():.3f}')
