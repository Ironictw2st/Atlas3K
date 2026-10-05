"""Compare two lf_height_map.dds rasters (L16) and their compressed_map headers. usage: cmp_lf.py <dir a> <dir b>"""
import struct, sys
from pathlib import Path
import numpy as np


def dds(p):
    d = p.read_bytes(); h, w = struct.unpack_from("<II", d, 12)
    return np.frombuffer(d, np.uint16, w * h, 128).reshape(h, w)


a, b = Path(sys.argv[1]), Path(sys.argv[2])
A, B = dds(a / "lf_height_map.dds"), dds(b / "lf_height_map.dds")
d = A.astype(np.int64) - B
print("shape", A.shape, B.shape, "differing px", int((d != 0).sum()))
ys, xs = np.nonzero(d)
if len(ys): print("bbox rows", ys.min(), ys.max(), "cols", xs.min(), xs.max(), "max |d|", int(np.abs(d).max()))
for p in (a, b):
    h = (p / "lf_height_map.compressed_map").read_bytes()[:60]
    print(p, "header", struct.unpack_from("<6f", h, 26))
