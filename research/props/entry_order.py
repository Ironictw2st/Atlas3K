"""BOB global_props entry order: cells ascending? region order within a cell consistent with one global order?"""
import sys, re, collections
sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
from gp_entries import parse
nb, bb, _ = parse(sys.argv[1])
cells = []
for n in nb:
    m = re.search(r"bmd_objects\.(.+)\.(\d+)\.bin$", n)
    if m and not re.search(r"\.\d+\.\d+\.bin$", n): cells.append((m.group(1), int(m.group(2))))
cs = [c for _, c in cells]
print("cell entries", len(cells), "cells non-decreasing:", all(a <= b for a, b in zip(cs, cs[1:])))
# region order: pairwise precedence across cells
first = collections.defaultdict(list)
for i, (r, c) in enumerate(cells): first[c].append(r)
prec = collections.Counter(); conflicts = 0
for c, rs in first.items():
    for i in range(len(rs)):
        for j in range(i + 1, len(rs)): prec[(rs[i], rs[j])] += 1
for (a, b), v in prec.items():
    if (b, a) in prec: conflicts += 1
print("region pair conflicts", conflicts // 2, "of", len(prec))
print("buckets order within cell:", [n.split("bmd_objects.")[-1] for n in nb[:9]])
print(first[0][:20])
