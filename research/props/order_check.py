"""Test: are BOB prop records in each body sorted by entity id (u64)? usage: order_check.py <layers dir> <bob_cells.csv>"""
import csv, sys, collections
sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
from order_study import entities, f32
E = entities(sys.argv[1])
bodies = collections.defaultdict(list)
miss = 0
for r in csv.DictReader(open(sys.argv[2], encoding="utf-8")):
    e = E.get((r["path"].lower(), f32(r["x"]), f32(r["z"])))
    if not e: miss += 1; bodies[r["bmd"]].append(None); continue
    bodies[r["bmd"]].append({int(x[2], 16) for x in e})
ok = bad = amb = 0; ex = []
for b, seq in bodies.items():
    if any(s is None for s in seq) or any(len(s) > 1 for s in seq): amb += 1; continue
    ids = [next(iter(s)) for s in seq]
    if ids == sorted(ids): ok += 1
    else:
        bad += 1
        if len(ex) < 5: ex.append((b.split("bmd_objects.")[-1], [hex(i) for i in ids][:12]))
print("records unmatched", miss, "bodies sorted", ok, "unsorted", bad, "ambiguous", amb)
for e in ex: print(e)
