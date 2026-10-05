"""Per-hex field decode for 3K map.hex (16-byte records), per CAIME MapHexFile.ReadHexData."""
import sys, numpy as np
sys.path.insert(0, r"Z:/Claude/CAIME"); sys.path.insert(0, r"Z:/Claude/TerryClone/research")
from scale_map_hex import locate_dims
import hexmap

def fields(path):
    mh = open(path, "rb").read(); P, w, h = locate_dims(mh)
    g = np.frombuffer(mh, np.uint8, 16 * w * h, P + 8).reshape(h, w, 16).astype(np.int32)
    m = hexmap.load(path)
    names = m["lists"]["land_regions"] + m["lists"]["sea_regions"]
    return dict(region=((g[..., 1] << 5) | (g[..., 0] >> 3)) - 1, slot=(g[..., 2] >> 4) - 1,
                passable=(g[..., 2] & 8) == 0, sea=(g[..., 0] & 3) == 1, names=names, nland=len(m["lists"]["land_regions"]), w=w, h=h)
