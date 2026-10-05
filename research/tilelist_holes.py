"""Tile-map points a tile_list.bin leaves uncovered (layer 1 and also-place tiles), vs a simulation's.

usage: tilelist_holes.py <tile_map.png> <tile_list.bin> [sim.csv]
Footprints use the campaign tile database (size, mask) and BOB's rotation (TILE_MAP::rotate_in_tile_space).
A point counts as a hole when its colour is a tile-set colour and no tile covers it. With sim.csv (TileMatchSimulator
output: location,x,y,rotation,climate,layer) the simulated coverage is compared point by point."""
import glob
import os
import struct
import sys

import numpy as np
from PIL import Image

DB = r"Z:/Claude/TerryClone/Vanilla/terrain/tiles/campaign/_tile_database"
BS = chr(92)


def read_str(b, o):
    n = struct.unpack_from("<H", b, o)[0]
    return b[o + 2:o + 2 + n].decode("latin1"), o + 2 + n


def tiles_by_location():
    out = {}
    for f in glob.glob(os.path.join(DB, "tiles", "*.bin")):
        b = open(f, "rb").read()
        v = struct.unpack_from("<H", b, 8)[0]
        o = 10
        _, o = read_str(b, o)
        _, o = read_str(b, o)
        mask, o = read_str(b, o)
        if v > 5:
            _, o = read_str(b, o)
        w, h = struct.unpack_from("<ii", b, o)
        i = b.find(b"terrain" + BS.encode() + b"tiles")
        while i >= 0:
            n = struct.unpack_from("<H", b, i - 2)[0]
            loc = b[i:i + n].decode().lower().rstrip(BS)
            out[loc] = (w, h, mask)
            i = b.find(b"terrain" + BS.encode() + b"tiles", i + 1)
    return out


def set_colours():
    b = open(os.path.join(DB, "_settings.bin"), "rb").read()
    cols = set()
    for o in range(4, len(b) - 4):
        if struct.unpack_from("<H", b, o)[0] != 2:
            continue
        try:
            name, p = read_str(b, o + 2)
            if not name or not all(c.islower() or c.isdigit() or c == "_" for c in name):
                continue
            for _ in range(4):
                _, p = read_str(b, p)
            r, g, bl = struct.unpack_from("<3f", b, p)
            if all(0 <= c <= 255 and c == int(c) for c in (r, g, bl)) and p + 13 <= len(b):
                cols.add((int(r) << 16) | (int(g) << 8) | int(bl))
        except Exception:
            pass
    return cols


def rotate(w, h, rot, x, y):
    return {0x10: (x, y), 0x20: (y, w - 1 - x), 0x40: (w - 1 - x, h - 1 - y), 0x80: (h - 1 - y, x)}[rot]


def coverage(records, shape, tiles):
    H, W = shape
    cov = np.zeros(shape, bool)
    missing = set()
    for loc, x0, y0, rot in records:
        t = tiles.get(loc)
        if t is None:
            missing.add(loc)
            continue
        w, h, mask = t
        for row in range(h):
            for col in range(w):
                if mask and (len(mask) != w * h or mask[row * w + col] != "1"):
                    continue
                rx, ry = rotate(w, h, rot, col, h - row - 1)
                x, y = x0 + rx, y0 + ry
                if 0 <= x < W and 0 <= y < H:
                    cov[y, x] = True
    return cov, missing


def read_tile_list(p):
    b = open(p, "rb").read()
    o = 12
    lists = []
    for _ in range(2):
        n = struct.unpack_from("<I", b, o)[0]
        o += 4
        items = []
        for _ in range(n):
            s, o = read_str(b, o)
            items.append(s)
        lists.append(items)
    paths = lists[0]
    o += 24 + 44 + 1
    cnt = struct.unpack_from("<I", b, o)[0]
    o += 4
    recs = []
    for i in range(cnt):
        _, pi, _, x, y, ori, _ = struct.unpack_from("<HIBHHBB", b, o + i * 21)
        recs.append((paths[pi].lower().rstrip(BS), x, y, ori & 0xF0))
    return recs


def main():
    img = np.asarray(Image.open(sys.argv[1]).convert("RGB")).astype(np.int64)
    code = (img[..., 0] << 16) | (img[..., 1] << 8) | img[..., 2]
    code = code[::-1]                                   # internal y = 0 at the south (bottom image row)
    valid = np.isin(code, list(set_colours()))
    tiles = tiles_by_location()
    cov, missing = coverage(read_tile_list(sys.argv[2]), code.shape, tiles)
    holes = valid & ~cov
    print(f"tile list: {int(holes.sum())} uncovered tile-set points; unknown tile paths: {len(missing)}")
    if len(sys.argv) > 3:
        recs = []
        for line in open(sys.argv[3]):
            loc, x, y, r, _, _ = line.strip().rsplit(",", 5)
            recs.append((loc.lower().rstrip(BS), int(x), int(y), int(r)))
        scov, _ = coverage(recs, code.shape, tiles)
        sholes = valid & ~scov
        both = holes & sholes
        print(f"simulation: {int(sholes.sum())} uncovered; both {int(both.sum())}, only tile list {int((holes & ~sholes).sum())}, "
              f"only simulation {int((sholes & ~holes).sum())}")


main()
