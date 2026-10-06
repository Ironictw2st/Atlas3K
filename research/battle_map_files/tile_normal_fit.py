"""Fit the tile normal.dds mip 0 (B,G,R,A = 0, ny, 255, nx) against the tile's float height TIF (1280x1280):
Sobel (edge-clamped) times k, normal = normalise(k*gx, k*gy, z), byte = trunc((n+1)*127.5). usage: tile_normal_fit.py <mip0.bin> <height.tif>"""
import itertools, sys
import numpy as np, tifffile

F = np.float32
a = np.frombuffer(open(sys.argv[1], 'rb').read(), np.uint8).reshape(1280, 1280, 4).astype(np.int64)
h = tifffile.imread(sys.argv[2]).astype(F)


def sobel(f):
    p = np.pad(f, 1, mode='edge')
    gx = (p[:-2, :-2] - p[:-2, 2:] + F(2) * (p[1:-1, :-2] - p[1:-1, 2:]) + p[2:, :-2] - p[2:, 2:]).astype(F)
    gy = (p[:-2, :-2] - p[2:, :-2] + F(2) * (p[:-2, 1:-1] - p[2:, 1:-1]) + p[:-2, 2:] - p[2:, 2:]).astype(F)
    return gx, gy


res = []
for flip in (False, True):
    f = h[::-1] if flip else h
    gx0, gy0 = sobel(f)
    for swap, sx, sy in itertools.product((False, True), (1, -1), (1, -1)):
        gx, gy = (gy0, gx0) if swap else (gx0, gy0)
        for k in (1, 0.5, 0.25, 0.125, 2, 1 / 8, 1 / 16, 1 / 32):
            for z in (1, 2, 4, 8, 16, 0.5, 0.25, 32):
                X = (gx * F(k * sx)).astype(F); Y = (gy * F(k * sy)).astype(F)
                inv = (F(1) / np.sqrt(X * X + Y * Y + F(z) * F(z))).astype(F)
                bx = (((X * inv).astype(F) + F(1)) * F(127.5)).astype(np.int64)
                by = (((Y * inv).astype(F) + F(1)) * F(127.5)).astype(np.int64)
                if flip: bx, by = bx[::-1], by[::-1]
                res.append(((bx != a[..., 3]).sum() + (by != a[..., 1]).sum(), flip, swap, sx, sy, k, z))
for r in sorted(res)[:8]: print(r)
