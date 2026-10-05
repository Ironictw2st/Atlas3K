"""Compare a native camera_heightmap.png with vanilla 3k_dlc07's (world units, via each file's height_scale)."""
import sys
import numpy as np
from PIL import Image

HERE = r"Z:\Claude\TerryClone\research\derived_maps"
ours_path = sys.argv[1] if len(sys.argv) > 1 else r"Z:\Claude\TerryClone\output\native_build_test\campaign_maps\3k_dlc07_main_map\camera_heightmap.png"


def load(p):
    im = Image.open(p)
    return np.array(im).astype(np.float64) * float(im.info['height_scale']), im.info['height_scale'], im.mode


van, vs, _ = load(HERE + r"\campaign_maps__3k_dlc07_main_map__camera_heightmap.png")
ours, os_, mode = load(ours_path)
e = ours - van
a = np.abs(e)
print(f'mode {mode}  height_scale ours {os_} vanilla {vs}  shape {ours.shape}')
print(f'|e| median {np.median(a):.4f}  mean {a.mean():.4f}  p90 {np.percentile(a, 90):.3f}  p99 {np.percentile(a, 99):.3f}  mean e {e.mean():+.4f}')
for t in (0.05, 0.1, 0.25, 0.5, 1, 2):
    print(f'  frac |e| < {t}: {(a < t).mean():.4f}')
print(f'corr {np.corrcoef(ours.ravel(), van.ravel())[0, 1]:.5f}')
d = np.clip(e, -3, 3)
img = np.zeros(ours.shape + (3,), np.uint8)
img[..., 0] = np.clip(d / 3 * 255, 0, 255)       # red: ours higher
img[..., 2] = np.clip(-d / 3 * 255, 0, 255)      # blue: vanilla higher
img[..., 1] = np.clip(van / 14 * 90, 0, 255)
Image.fromarray(img).resize((892, 702)).save(HERE + r"\cam_ours_minus_vanilla.png")
