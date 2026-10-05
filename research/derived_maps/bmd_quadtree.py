"""Check the quadtree hypothesis for global_props cells: BFS numbering, children NW, NE, SW, SE, 7 levels."""
import collections
import csv
import re

rows = list(csv.DictReader(open(r"Z:\Claude\TerryClone\output\props_cells.csv")))
key = re.compile(r'bmd_objects\.(.+?)\.(\d+)\.(\d+)\.bin$')


def node_rect(c, W, H, order):
    level, first = 0, 0
    while first + 4 ** level <= c:
        first += 4 ** level
        level += 1
    idx = c - first
    digits = []
    for _ in range(level):
        digits.append(idx % 4)
        idx //= 4
    x0, x1, z0, z1 = 0.0, W, 0.0, H
    for d in reversed(digits):
        q = order[d]
        mx, mz = (x0 + x1) / 2, (z0 + z1) / 2
        x0, x1 = (x0, mx) if q[1] == 'W' else (mx, x1)
        z0, z1 = (mz, z1) if q[0] == 'N' else (z0, mz)
    return level, x0, x1, z0, z1


for (W, H) in [(595.1, 541.78619), (595.1, 595.1), (541.78619, 541.78619), (600, 600), (640, 640)]:
    for order in (('NW', 'NE', 'SW', 'SE'), ('SW', 'SE', 'NW', 'NE')):
        inside = total = 0
        for r in rows:
            m = key.search(r['bmd'])
            if not m:
                continue
            c = int(m.group(2))
            if c == 0:
                continue
            lv, x0, x1, z0, z1 = node_rect(c, W, H, order)
            x, z = float(r['x']), float(r['z'])
            total += 1
            inside += x0 - 1e-3 <= x <= x1 + 1e-3 and z0 - 1e-3 <= z <= z1 + 1e-3
        print(f'{W}x{H} {order}: {inside}/{total} inside ({inside / total:.4f})')

print('--- row-major per level')
def grid_rect(c, W, H, north_first=True):
    level, first = 0, 0
    while first + 4 ** level <= c:
        first += 4 ** level; level += 1
    idx = c - first; n = 2 ** level
    row, col = divmod(idx, n)
    cw, ch = W / n, H / n
    x0 = col * cw
    z0 = H - (row + 1) * ch if north_first else row * ch
    return level, x0, x0 + cw, z0, z0 + ch
for (W, H) in [(595.1, 541.78619), (595.1, 595.1), (541.78619, 541.78619), (600, 600), (1024, 1024)]:
    for nf in (True, False):
        inside = total = 0
        for r in rows:
            m = key.search(r['bmd'])
            if not m: continue
            c = int(m.group(2))
            if c == 0: continue
            lv, x0, x1, z0, z1 = grid_rect(c, W, H, nf)
            x, z = float(r['x']), float(r['z']); total += 1
            inside += x0 - 1e-3 <= x <= x1 + 1e-3 and z0 - 1e-3 <= z <= z1 + 1e-3
        print(f'{W}x{H} north_first={nf}: {inside}/{total} ({inside / total:.4f})')
