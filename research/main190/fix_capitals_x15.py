#!/usr/bin/env python3
"""User (2026-10-01): every 190E capital stays the capital of its own 190E province ("cities should be their own capital,
instead of being together"). For each 190E province whose capital the x15 export merged into another province:
restore the province with its capital plus the 190E members that border the capital (not capitals elsewhere);
EXTRA adds named regions (Xiangyang gets Fangling). Rewrites regions_new.json (all_provinces / province_moves)."""
import collections, json, sys, shutil, time
from pathlib import Path
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
import town_fix as T
from hexgrid import neighbour_arrays
EXTRA = {"3k_main_province_xiangyang": ["ironic_central_nan_resource_1"]}      # Fangling
MAXP = 4

J = HERE / "regions_new.json"
shutil.copy(J, HERE / f"regions_new_before_capitals_{time.strftime('%Y%m%d_%H%M%S')}.json")
nj = json.load(open(J, encoding="utf-8"))
_, _, w, h, _, f, names = T.load(str(HERE / "hex" / "map.hex"))
reg = f["region"]; land = f["terr"] != 1
cnt = collections.Counter()
for nr, nc, v in neighbour_arrays(h, w):
    m = v & land & land[nr, nc] & (reg != reg[nr, nc])
    cnt.update(zip(reg[m].tolist(), reg[nr, nc][m].tolist()))
A = collections.defaultdict(set)
for (x, y), n in cnt.items():
    if n >= 2: A[names[x]].add(names[y])
junc = {}
for line in open(HERE / "source" / "db" / "region_to_province_junctions_tables" / "data__.tsv", encoding="utf-8"):
    a = line.rstrip("\n").split("\t")
    if len(a) >= 3 and not a[0].startswith(("#", "province")): junc[a[1]] = (a[0], a[2] == "true")
P = nj["all_provinces"]
def where(r): return next((pv for pv in P if r in pv["members"]), None)
caps = lambda: {pv["capital"] for pv in P}
for pk, cap in sorted((pk, r) for r, (pk, c) in junc.items() if c):
    pv = where(cap)
    if pv is None or pv["capital"] == cap: continue                     # not on the map / already its own capital
    if any(q["key"] == pk for q in P): raise SystemExit(f"{pk} key already used")
    mem = [cap] + [r for r, (p, c) in junc.items() if p == pk and r != cap and where(r) and r not in caps() and cap in A[r]]
    mem += [r for r in EXTRA.get(pk, []) if r not in mem and r not in caps()]
    mem = mem[:MAXP]
    for r in mem:
        src = where(r); src["members"].remove(r)
        nj["province_moves"].pop(r, None)
        if junc.get(r, ("",))[0] != pk: nj["province_moves"][r] = pk
    P.append(dict(key=pk, capital=cap, members=mem, label=pk.split("province_")[-1].title(), zhou=pv.get("zhou")))
    print(f"restored {pk}: {mem}  (capital taken from {pv['key']}, now {pv['members']})")
for pv in P:
    assert pv["members"] and pv["capital"] in pv["members"], pv
    assert len(pv["members"]) <= MAXP, pv
c = collections.Counter(m for pv in P for m in pv["members"]); assert max(c.values()) == 1
json.dump(nj, open(J, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print(len(P), "provinces; regions_new.json updated")
