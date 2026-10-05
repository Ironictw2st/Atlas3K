"""Work out BOB's global_props cell (quadtree node) and bucket (sub index 16..31) rules from vanilla."""
import collections
import csv
import re

rows = list(csv.DictReader(open(r"Z:\Claude\TerryClone\output\props_cells.csv")))
print('props', len(rows))
key = re.compile(r'bmd_objects\.(.+?)\.(\d+)\.(\d+)\.bin$')

# bucket vs attributes
tab = collections.defaultdict(collections.Counter)
for r in rows:
    m = key.search(r['bmd'])
    if not m:
        tab['no-sub'][r['seasons']] += 1
        continue
    sub = int(m.group(3))
    attrs = (r['seasons'] or '-', r['tags'][:40] or '-')
    tab[sub][attrs] += 1
for sub in sorted(tab, key=str):
    print(sub, tab[sub].most_common(6))

# cells: bounding box of prop positions per cell id
cells = collections.defaultdict(list)
for r in rows:
    m = key.search(r['bmd'])
    if m:
        cells[int(m.group(2))].append((float(r['x']), float(r['z'])))
print()
for c in sorted(cells)[:12] + sorted(cells)[-6:]:
    xs = [p[0] for p in cells[c]]; zs = [p[1] for p in cells[c]]
    level = 0; first = 0
    while first + 4 ** level <= c:
        first += 4 ** level; level += 1
    print(f'cell {c:5d} level {level} idx {c - first:5d} n {len(xs):5d} x {min(xs):7.2f}..{max(xs):7.2f} z {min(zs):7.2f}..{max(zs):7.2f}')
