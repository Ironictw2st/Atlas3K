"""Per-prop comparison of two props-cells CSVs (Atlas3K.Cli props-cells): match props by (path, x, y, z) and compare
region, cell, bucket and flags. usage: cells_compare.py <bob.csv> <native.csv>"""
import csv, collections, re, sys


def load(p):
    rows = list(csv.DictReader(open(p, encoding="utf-8")))
    for r in rows:
        m = re.search(r"bmd_objects\.(.+)\.(\d+)\.(\d+)\.bin$", r["bmd"])
        r["cell"], r["bucket"] = (int(m.group(2)), int(m.group(3))) if m else (-1, -1)
        r["key"] = (r["path"].lower(), r["x"], r["y"], r["z"])
    return rows


A, B = load(sys.argv[1]), load(sys.argv[2])
ia = collections.defaultdict(list); ib = collections.defaultdict(list)
for r in A: ia[r["key"]].append(r)
for r in B: ib[r["key"]].append(r)
common = set(ia) & set(ib)
print(f"props bob {len(A)} native {len(B)}; keys bob {len(ia)} native {len(ib)} common {len(common)}")
print("only bob (first):", [k[0].split('/')[-1] for k in list(set(ia) - set(ib))[:5]], len(set(ia) - set(ib)))
print("only native (first):", [k[0].split('/')[-1] for k in list(set(ib) - set(ia))[:5]], len(set(ib) - set(ia)))
c = collections.Counter()
lvl = lambda cell: next(L for L in range(8) if cell < sum(4 ** k for k in range(L + 1)))
cell_diff = collections.Counter()
for k in common:
    a, b = ia[k][0], ib[k][0]
    for f in ("region", "cell", "bucket", "decal", "snow_in", "snow_out", "destr_in", "destr_out", "seasons", "tags", "unseen", "seen"):
        if a[f] != b[f]: c[f] += 1
    if a["cell"] != b["cell"]: cell_diff[(lvl(a["cell"]), lvl(b["cell"]))] += 1
print("field differences over common props:", dict(c))
print("cell level (bob, native) for differing cells:", cell_diff.most_common(10))
