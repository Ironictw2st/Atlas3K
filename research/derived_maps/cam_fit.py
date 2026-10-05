"""Fit BOB's camera_heightmap.png against vanilla 3k_dlc07: terrain-only part (blur, block sampling, sea clamp)."""
import numpy as np
from PIL import Image

V = r"Z:\Claude\TerryClone\Vanilla\Map\terrain\campaigns\3k_dlc07_main_map"
HERE = r"Z:\Claude\TerryClone\research\derived_maps"


def gaussian(X, s, r=None):
    r = r or max(1, int(3 * s + 0.5))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / s) ** 2)
    k /= k.sum()
    P = np.pad(X, ((0, 0), (r, r)), mode='edge')
    Y = sum(k[i] * P[:, i:i + X.shape[1]] for i in range(2 * r + 1))
    P = np.pad(Y, ((r, r), (0, 0)), mode='edge')
    return sum(k[i] * P[i:i + X.shape[0]] for i in range(2 * r + 1))


def load():
    b = open(V + r"\lf_height_map.dds", 'rb').read()
    H = np.frombuffer(b, '<u2', offset=128, count=7136 * 5620).reshape(5620, 7136).astype(np.float64) * 0.000218712 - 3.12725
    cam = np.array(Image.open(HERE + r"\campaign_maps__3k_dlc07_main_map__camera_heightmap.png")).astype(np.float64) * 0.000382
    return H, cam


if __name__ == '__main__':
    H, cam = load()
    h, w = cam.shape
    Hc = np.maximum(H, 0)
    blocks = {'max': Hc.reshape(h, 4, w, 4).max(axis=(1, 3)), 'mean': Hc.reshape(h, 4, w, 4).mean(axis=(1, 3)), 'pt': Hc[::4, ::4]}
    for name, X in blocks.items():
        for s in (0, 0.5, 1, 1.5, 2, 3):
            Y = gaussian(X, s) if s else X
            e = cam - Y
            print(f'{name:4} sigma {s}: median|e| {np.median(np.abs(e)):.4f}  mean e {e.mean():.3f}  frac |e|<0.05 {(np.abs(e) < 0.05).mean():.3f}')
