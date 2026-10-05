"""Tile map <-> hex grid. The campaign tile map is the hex grid at 2x2 px per hex (+1 row, odd columns 1 px higher):
hex (col, row) covers x = 2*col + {0,1}, y = (H-1) - (2*row + (col & 1) + {0,1}), H = 2*rows + 1 (row 0 = south).
Verified on vanilla: 99.993% of pixels agree with the map.hex sea flag."""
import numpy as np

def hex_pixels(w, h):
    """Pixel (y, x) index arrays of shape (h, w, 4) for every hex."""
    rows, cols = np.mgrid[0:h, 0:w]
    H = 2 * h + 1
    ys, xs = [], []
    for dy in (0, 1):
        for dx in (0, 1):
            ys.append((H - 1) - (2 * rows + (cols & 1) + dy)); xs.append(2 * cols + dx)
    return np.stack(ys, -1), np.stack(xs, -1)

def read_codes(img):
    a = np.asarray(img.convert("RGB")).astype(np.int32)
    return (a[..., 0] << 16) | (a[..., 1] << 8) | a[..., 2]
