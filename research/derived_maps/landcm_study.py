"""land_mesh_N.compressed_map (224x224) vs the lf height grid and the land mesh vertices."""
import struct, sys
import numpy as np
sys.path.insert(0, r"Z:\Claude\TerryClone\research")
import compressed_map as cmap

V = r"Z:\Claude\TerryClone\Vanilla\Map\terrain\campaigns\3k_dlc07_main_map"
n = int(sys.argv[1]) if len(sys.argv) > 1 else 0
raster, header = None, None
dec = cmap.decode(fr"{V}\global_meshes\land_mesh_{n}.compressed_map")
print(type(dec), [type(x) for x in dec] if isinstance(dec, tuple) else '')
raster, header = dec
print('header', header, 'shape', raster.shape)
hmax = header[4]
lo = header[1]
H = lambda v: lo + v.astype(float) / 65535 * (hmax - lo)
holes = raster == 0
print('holes', holes.sum())
# lf grid for tile n
b = open(fr"{V}\lf_height_map.dds", 'rb').read()
L = np.frombuffer(b, '<u2', offset=128, count=7136 * 5620).reshape(5620, 7136).astype(float) * 0.000218712 - 3.12725
cols = 16
tc, tr = n % cols, n // cols  # tile index assumes all tiles present (true for the first rows only)
# mesh vertex grid (i,j): world x = tc*37.19375 + i*cell, z = tr*37.19375 + j*cell; lf pixel col = 2*(223*tc + i), row = H-1-2*(223*tr + j)
ii = np.arange(224)
cx = np.clip(2 * (223 * tc + ii), 0, 7135)
for flip in (False, True):
    rows = np.clip(5619 - 2 * (223 * tr + ii), 0, 5619)
    S = L[np.ix_(rows, cx)]            # S[j, i]
    R = H(raster)
    if flip: R = R[::-1]
    m = ~(raster[::-1] if flip else raster).astype(bool) == False
    e = np.abs(R - S)[m]
    print('flip' if flip else 'noflip', 'median', np.median(e), 'max', e.max(), 'exact frac', (e < 1e-4).mean())
