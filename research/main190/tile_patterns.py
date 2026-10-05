#!/usr/bin/env python3
"""Predict missing tiles from the tile map alone: cells whose 3x3 colour neighbourhood never occurs in vanilla's
tile map (so BOB's tile set may have no tile for it). Compare with tile_holes.py after a BOB Tilemap run.

usage: tile_patterns.py <tile_map.png> [holes png from tile_holes.py]   (prints precision/recall if given)
"""
import sys, numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
VAN = r"Z:/Claude/TerryClone/Vanilla/3k_dlc07_main_map/tile_map.png"


def codes(p):
    a = np.array(Image.open(p).convert("RGB")).astype(np.int64)
    return (a[..., 0] << 16) | (a[..., 1] << 8) | a[..., 2]


def palette_ids(*arrs):
    u = np.unique(np.concatenate([a.ravel() for a in arrs])); return {int(v): i for i, v in enumerate(u)}, u


def keys(ids, pal):
    # 3x3 neighbourhood key: base-B number of the 9 palette ids (B = palette size), in unsigned 64-bit arithmetic
    # (exact while B**9 < 2**64, i.e. B <= 137; above that a rolling hash with negligible collision risk)
    h, w = ids.shape; p = np.pad(ids, 1, mode="edge").astype(np.uint64); k = np.zeros((h, w), np.uint64)
    B = np.uint64(max(len(pal), 2)) if len(pal) <= 137 else np.uint64(1000003)
    for dy in range(3):
        for dx in range(3): k = k * B + p[dy:dy + h, dx:dx + w]
    return k


def flag(tm_path):
    V, T = codes(VAN), codes(tm_path)
    m, u = palette_ids(V, T)
    lut = np.vectorize(m.get)
    vi, ti = lut(V), lut(T)
    kv, kt = keys(vi, u), keys(ti, u)
    seen = np.isin(kt, np.unique(kv))
    return ~seen, T


if __name__ == "__main__":
    bad, T = flag(sys.argv[1])
    print(f"cells with a 3x3 pattern vanilla never has: {int(bad.sum()):,} of {bad.size:,}")
    u, c = np.unique(T[bad], return_counts=True)
    for x, n in sorted(zip(u, c), key=lambda t: -t[1])[:12]: print(f"   centre {x:06x}: {n}")
    if len(sys.argv) > 2:
        k = np.array(Image.open(sys.argv[2]).convert("RGB"))
        sus = (k[..., 0] == 255) & (k[..., 1] == 0)
        near = bad.copy()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1): near |= np.roll(np.roll(bad, dy, 0), dx, 1)
        print(f"suspect hole cells within 1 of a flagged cell: {int((sus & near).sum())} of {int(sus.sum())} "
              f"(recall {((sus & near).sum() / max(1, sus.sum())):.0%})")
