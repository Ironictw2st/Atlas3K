"""Print size, mask length and variation folders of campaign tiles whose file name matches a glob.
usage: tile_db_dump.py <glob, e.g. generic_sea*>"""
import glob
import os
import struct
import sys

DB = r"Z:/Claude/TerryClone/Vanilla/terrain/tiles/campaign/_tile_database/tiles"
for f in sorted(glob.glob(os.path.join(DB, sys.argv[1] + ".bin"))):
    b = open(f, "rb").read()
    o = 8
    v = struct.unpack_from("<H", b, o)[0]
    o += 2

    def s():
        global o
        n = struct.unpack_from("<H", b, o)[0]
        r = b[o + 2:o + 2 + n].decode("latin1")
        o += 2 + n
        return r

    name, tile_set, mask = s(), s(), s()
    if v > 5:
        s()
    w, h = struct.unpack_from("<ii", b, o)
    locs = []
    i = b.find(b"terrain\\tiles")
    while i >= 0:
        n = struct.unpack_from("<H", b, i - 2)[0]
        locs.append(b[i:i + n].decode())
        i = b.find(b"terrain\\tiles", i + 1)
    print(os.path.basename(f), name, tile_set, f"{w}x{h}", "mask", len(mask), locs)
