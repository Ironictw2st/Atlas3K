"""Where does vanilla's camera heightmap exceed ours? Relate the residual to tree and prop density per tile-map cell."""
import csv
import numpy as np
from PIL import Image

HERE = r"Z:\Claude\TerryClone\research\derived_maps"
OURS = r"Z:\Claude\TerryClone\output\native_build_test\campaign_maps\3k_dlc07_main_map\camera_heightmap.png"
W, H = 1784, 1405
PX, PZ = 595.1 / 1784, 541.78619 / 1405


def load(p):
    im = Image.open(p)
    return np.array(im).astype(np.float64) * float(im.info['height_scale'])


van = load(HERE + r"\campaign_maps__3k_dlc07_main_map__camera_heightmap.png")
ours = load(OURS)
gap = van - ours

trees = np.zeros((H, W))
tree_y = np.full((H, W), -9.0)
by_type = {}
props = np.zeros((H, W))
for row in csv.DictReader(open(r"Z:\Claude\TerryClone\output\props_dump.csv")):
    c = int(float(row['x']) / PX)
    r = int(H - float(row['z']) / PZ)
    if not (0 <= c < W and 0 <= r < H):
        continue
    if row['kind'] == 'tree':
        trees[r, c] += 1
        tree_y[r, c] = max(tree_y[r, c], float(row['y']))
        by_type.setdefault(row['path'], []).append((r, c, float(row['y'])))
    elif row['kind'] == 'prop':
        props[r, c] += 1

for name, mask in [('cells with trees', trees > 0), ('cells without trees', trees == 0)]:
    g = gap[mask]
    print(f'{name}: n={mask.sum()} gap mean {g.mean():+.3f} median {np.median(g):+.3f} frac gap>0.5 {(g > 0.5).mean():.3f}')
big = gap > 1
print(f'cells vanilla > ours by >1: {big.sum()}, of which have trees {(trees[big] > 0).mean():.3f}, props {(props[big] > 0).mean():.3f}')
# per tree type: vanilla height above the tree base (y) where that type stands
print('per tree type: vanilla camera height minus tree base y (median), count')
rows = []
for name, pts in by_type.items():
    r = np.array([p[0] for p in pts]); c = np.array([p[1] for p in pts]); y = np.array([p[2] for p in pts])
    rows.append((np.median(van[r, c] - y), np.median(ours[r, c] - y), len(pts), name))
for v, o, n, name in sorted(rows, reverse=True)[:40]:
    print(f'  {v:6.2f}  ours {o:6.2f}  {n:6d}  {name}')

print('=== nearest props to the largest gaps')
allp = [(float(r['x']), float(r['z']), float(r['y']), float(r['sx']), r['path'], r['kind']) for r in csv.DictReader(open(r"Z:\Claude\TerryClone\output\props_dump.csv")) if r['kind'] != 'tree']
P = np.array([(p[0], p[1]) for p in allp])
order = np.argsort(gap.ravel())[::-1]
seen = []
for k in order[:200000:4000]:
    r, c = divmod(k, W)
    x, z = (c + 0.5) * PX, (H - r - 0.5) * PZ
    if any(abs(x - sx) < 5 and abs(z - sz) < 5 for sx, sz in seen):
        continue
    seen.append((x, z))
    d = np.hypot(P[:, 0] - x, P[:, 1] - z)
    near = np.argsort(d)[:4]
    print(f'cell ({c},{r}) world ({x:.1f},{z:.1f}) vanilla {van[r, c]:.2f} ours {ours[r, c]:.2f}')
    for i in near:
        print(f'    {d[i]:5.2f}  y {allp[i][2]:.2f} s {allp[i][3]:.2f}  {allp[i][5]} {allp[i][4]}')
    if len(seen) >= 8:
        break
