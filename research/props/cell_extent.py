"""Infer BOB's object extent rule from its quadtree cells (props-cells CSV of a BOB global_props.bin).
For a prop in cell (level L, row, col): its x/z half-extent fits inside that cell (<= distance from the position to the
cell's edges) and, if L < 6, it crosses an edge of the level L+1 cell under its position (>= distance to the nearest
edge of that child). Per model, intersect those bounds in units of (extent / scale) and report whether one constant
per model is consistent. usage: cell_extent.py <bob_cells.csv> <worldW> <worldH>"""
import csv, collections, math, re, sys

rows = list(csv.DictReader(open(sys.argv[1], encoding="utf-8")))
W, H = float(sys.argv[2]), float(sys.argv[3])
first = [sum(4 ** k for k in range(L)) for L in range(8)]


def decode(cell):
    L = max(l for l in range(7) if first[l] <= cell)
    i = cell - first[L]; n = 1 << L
    return L, i // n, i % n


def edges(L, r, c):
    n = 1 << L; cw, ch = W / n, H / n
    x0, x1 = c * cw, (c + 1) * cw
    zt = H - r * ch; zb = H - (r + 1) * ch                      # row 0 = north (high z)
    return x0, x1, zb, zt


lo = collections.defaultdict(float); hi = collections.defaultdict(lambda: math.inf); cnt = collections.Counter()
consistent_pos_only = 0; total = 0
for row in rows:
    m = re.search(r"\.(\d+)\.(\d+)\.bin$", row["bmd"])
    if not m: continue
    cell = int(m.group(1)); L, r, c = decode(cell)
    x, z, s = float(row["x"]), float(row["z"]), abs(float(row["sx"])) or 1.0
    model = row["path"].lower(); cnt[model] += 1; total += 1
    x0, x1, zb, zt = edges(L, r, c)
    inside = min(x - x0, x1 - x, z - zb, zt - z)                 # extent must be <= this
    hi[model] = min(hi[model], inside / s)
    if L < 6:
        n = 1 << (L + 1); cc = int(x / (W / n)); rr = int((H - z) / (H / n))
        a0, a1, b0, b1 = edges(L + 1, rr, cc)
        need = min(x - a0, a1 - x, z - b0, b1 - z)               # crossing the child: extent >= nearest edge distance
        lo[model] = max(lo[model], need / s)
    else:
        consistent_pos_only += 1
bad = [(m, lo[m], hi[m], cnt[m]) for m in cnt if lo[m] > hi[m] + 1e-6]
ok = [(m, lo[m], hi[m], cnt[m]) for m in cnt if lo[m] <= hi[m] + 1e-6]
print(f"props {total}, at level 6 {consistent_pos_only}; models {len(cnt)}: consistent single extent/scale {len(ok)}, inconsistent {len(bad)}")
for m, a, b, n in sorted(ok, key=lambda t: -t[3])[:15]: print(f"  ok  {n:6d} {m.split('/')[-1]:45s} extent/scale in [{a:.4f}, {b:.4f}]")
for m, a, b, n in sorted(bad, key=lambda t: -t[3])[:10]: print(f"  BAD {n:6d} {m.split('/')[-1]:45s} lo {a:.4f} > hi {b:.4f}")
