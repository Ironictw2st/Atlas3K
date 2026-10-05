"""Readers for the campaign tile database, tile_list.bin and tile hf_height_map files (research helpers)."""
import glob
import os
import struct
import sys

import numpy as np

sys.path.insert(0, r"Z:\Claude\TerryClone\research")
import compressed_map as cmap

VAN = r"Z:\Claude\TerryClone\Vanilla"
DB = VAN + r"\terrain\tiles\campaign\_tile_database\tiles"


def read_db():
    """{tile folder path (lower, backslashes, trailing slash) -> dict(name, category, mask, w, h)}"""
    tiles = {}
    for f in glob.glob(DB + r"\*.bin"):
        b = open(f, 'rb').read()
        o = 10
        def s():
            nonlocal o
            n, = struct.unpack_from('<H', b, o)
            v = b[o + 2:o + 2 + n].decode('ascii', 'replace')
            o += 2 + n
            return v
        name, cat, mask = s(), s(), s()
        w, h = struct.unpack_from("<II", b, o + 2)
        i = b.find(b'terrain\\tiles\\')
        path = None
        if i >= 2:
            n, = struct.unpack_from('<H', b, i - 2)
            path = b[i:i + n].decode('ascii', 'replace').lower()
        tiles[path or f] = dict(name=name, category=cat, mask=mask, w=w, h=h, file=f)
    return tiles


def read_tile_list(path):
    b = open(path, 'rb').read()
    o = 12
    def strings():
        nonlocal o
        n, = struct.unpack_from('<I', b, o); o += 4
        out = []
        for _ in range(n):
            l, = struct.unpack_from('<H', b, o); out.append(b[o + 2:o + 2 + l].decode()); o += 2 + l
        return out
    paths = strings(); climates = strings()
    floats = struct.unpack_from('<6f', b, o); o += 24
    ints = struct.unpack_from('<11i', b, o); o += 44
    o += 1
    n, = struct.unpack_from('<I', b, o); o += 4
    rec = np.frombuffer(b, dtype=np.dtype([('ver', '<u2'), ('path', '<u4'), ('climate', 'u1'), ('x', '<u2'), ('y', '<u2'),
                                           ('orient', 'u1'), ('flag', 'u1'), ('lo', '<f4'), ('hi', '<f4')]), count=n, offset=o)
    return paths, climates, floats, ints, rec


_hf_cache = {}


def hf_map(tile_path):
    """Decoded hf_height_map of a tile folder (raster, header) or None."""
    key = tile_path.lower()
    if key not in _hf_cache:
        f = os.path.join(VAN, key.rstrip('\\'), 'hf_height_map.compressed_map')
        _hf_cache[key] = cmap.decode(f) if os.path.exists(f) else None
    return _hf_cache[key]
