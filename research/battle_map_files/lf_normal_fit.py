"""Fit BOB's lf_normal (bob_terrain FUN_18000e4d0 / FUN_18003ba70) against the Frida-dumped mip 0 RGBA (0, ny, 255, nx):
3x3 Sobel of the lf height field (clamped), normal = normalise(k*gx, k*gy, z), byte = trunc((n + 1) * 127.5).
Searches the height scale k, z, orientation and sign. usage: lf_normal_fit.py <mip0.bin> <lf_heights.tif>"""
import sys, itertools
import numpy as np, tifffile

F = np.float32
a = np.frombuffer(open(sys.argv[1], 'rb').read(), np.uint8).reshape(512, 512, 4).astype(np.int64)
s = tifffile.imread(sys.argv[2])
h = (s.astype(F) * F(F(1) / F(65535))).astype(F)


def sobel(f):
    p = np.pad(f, 1, mode='edge')
    gx = (p[:-2, :-2] - p[:-2, 2:] + F(2) * (p[1:-1, :-2] - p[1:-1, 2:]) + p[2:, :-2] - p[2:, 2:]).astype(F)
    gy = (p[:-2, :-2] - p[2:, :-2] + F(2) * (p[:-2, 1:-1] - p[2:, 1:-1]) + p[:-2, 2:] - p[2:, 2:]).astype(F)
    return gx, gy


best = []
for flip in (False, True):
    f = h[::-1] if flip else h
    gx0, gy0 = sobel(f)
    for swap in (False, True):
        gx, gy = (gy0, gx0) if swap else (gx0, gy0)
        for sx, sy in itertools.product((1, -1), repeat=2):
            for k in (1, 65535 / 1000, 65535, 1100, 5500, 500, 1000, 2000, 255, 1 / 8, 8, 1024, 2048, 4096, 32, 256, 128):
                for z in (1, 32, 8, 16, 64, 0.03125):
                    X = (gx * F(k) * F(sx)).astype(F); Y = (gy * F(k) * F(sy)).astype(F); Z = F(z)
                    inv = (F(1) / np.sqrt(X * X + Y * Y + Z * Z)).astype(F)
                    nx = (X * inv).astype(F); ny = (Y * inv).astype(F)
                    bx = ((nx + F(1)) * F(127.5)).astype(np.int64); by = ((ny + F(1)) * F(127.5)).astype(np.int64)
                    if flip: bx, by = bx[::-1], by[::-1]
                    err = (bx != a[..., 3]).sum() + (by != a[..., 1]).sum()
                    best.append((err, flip, swap, sx, sy, k, z))
for b in sorted(best)[:10]: print(b)
