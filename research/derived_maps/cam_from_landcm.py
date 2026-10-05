"""Hypothesis: BOB's camera height map samples the terrain INCLUDING prop height patches, i.e. the same heights as the
land_mesh_N.compressed_map tiles. Assemble those tiles into one grid and compare with vanilla's camera map."""
import glob, re, struct, sys
import numpy as np
from PIL import Image
sys.path.insert(0, r"Z:\Claude\TerryClone\research")
import compressed_map as cmap

V = r"Z:\Claude\TerryClone\Vanilla\Map\terrain\campaigns\3k_dlc07_main_map"
HERE = r"Z:\Claude\TerryClone\research\derived_maps"
TILE = 37.19375
CELL = TILE / 223
W, H = 16 * 223 + 1, 13 * 223 + 1          # vertex grid over the whole map
grid = np.full((H, W), np.nan)
for f in glob.glob(V + r"\global_meshes\land_mesh_*.compressed_map"):
    n = int(re.search(r'_(\d+)\.compressed', f).group(1))
    rm = open(f.replace('.compressed_map', '.rigid_model_v2'), 'rb').read()
    minx, _, minz = struct.unpack_from('<3f', rm, 0xC0)
    tc, tr = int(round(minx / TILE)), int(round(minz / TILE))
    r, hdr = cmap.decode(f)
    h = hdr[1] + r.astype(float) / 65535 * (hdr[4] - hdr[1])
    h[r == 0] = np.nan
    sub = grid[tr * 223:tr * 223 + 224, tc * 223:tc * 223 + 224]
    sub[:] = np.where(np.isnan(h), sub, h[:sub.shape[0], :sub.shape[1]])   # rows = z index
print('assembled; nan frac', np.isnan(grid).mean())

b = open(V + r"\lf_height_map.dds", 'rb').read()
L = np.frombuffer(b, '<u2', offset=128, count=7136 * 5620).reshape(5620, 7136).astype(float) * 0.000218712 - 3.12725
# lf sampled on the same vertex grid (rows = z index = south up)
jj = np.clip(5619 - 2 * np.arange(H), 0, 5619); ii = np.clip(2 * np.arange(W), 0, 7135)
Lg = L[np.ix_(jj, ii)]
d = grid - Lg
m = ~np.isnan(d)
print('landcm - lf: median %.4f  mean %.4f  p99 %.3f  max %.3f  frac |d|>0.5 %.4f' % (np.median(np.abs(d[m])), d[m].mean(), np.percentile(np.abs(d[m]), 99), np.nanmax(d), (np.abs(d[m]) > 0.5).mean()))

im = Image.open(HERE + r"\campaign_maps__3k_dlc07_main_map__camera_heightmap.png")
van = np.array(im).astype(float) * float(im.info['height_scale'])
ch, cw = van.shape
cellW, cellH = 595.1 / cw, 541.78619 / ch
T = np.where(np.isnan(grid), Lg, grid)
T = np.maximum(T, 0)
# camera cell (x, y): max over world rect [x*cellW -+ cellW/2] x [y*cellH -+ cellH/2]; image row 0 = north
out = np.zeros_like(van)
zs = np.arange(ch)
for y in range(ch):
    z0, z1 = (ch - 1 - y) * cellH - cellH / 2, (ch - 1 - y) * cellH + cellH / 2
    r0, r1 = max(0, int(np.floor(z0 / CELL))), min(H - 1, int(np.ceil(z1 / CELL)))
    band = T[r0:r1 + 1].max(0)
    for x in range(cw):
        c0, c1 = max(0, int(np.floor((x * cellW - cellW / 2) / CELL))), min(W - 1, int(np.ceil((x * cellW + cellW / 2) / CELL)))
        out[y, x] = band[c0:c1 + 1].max()
e = np.abs(out - van)
print('camera from land cmaps: median %.4f  frac<0.05 %.3f  frac<0.25 %.3f  frac<1 %.3f  corr %.4f' % (np.median(e), (e < 0.05).mean(), (e < 0.25).mean(), (e < 1).mean(), np.corrcoef(out.ravel(), van.ravel())[0, 1]))
np.save(HERE + r"\cam_from_landcm.npy", out)
