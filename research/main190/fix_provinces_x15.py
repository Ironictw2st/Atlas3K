#!/usr/bin/env python3
"""Province sanity for the x15 export (regions_new.json from carve_x15.py), before regions_db.py:
 * a new province whose key clashes with an existing 190E province (3k_ironic_province_hanyang = 190E's Dunhuang
   province; the export's Han Hanyang/Tianshui commandery got the same key) is re-keyed <key>_han;
 * a region listed in two provinces stays in the one that is not new;
 * every province on the map has exactly one capital: when membership by identity moved a province's capital away
   (Dongou -> Kuaiji, Lujiang -> Yangzhou, Xiping/Xidu -> Jincheng), its largest remaining region becomes the capital.
Rewrites regions_new.json (all_provinces / new_provinces / provinces) and logs every change."""
import collections, json, re, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
import town_fix as T

nj = json.load(open(HERE / "regions_new.json", encoding="utf-8"))
_, _, w, h, _, f, names = T.load(str(HERE / "hex" / "map.hex"))
size = collections.Counter(f["region"][f["terr"] != 1].tolist())
# 190E province keys (pack junctions of the region test pack)
junc = {}
for line in open(HERE / "source" / "db" / "region_to_province_junctions_tables" / "data__.tsv", encoding="utf-8"):
    a = line.rstrip("\n").split("\t")
    if len(a) >= 3 and not a[0].startswith(("#", "province")): junc[a[1]] = (a[0], a[2] == "true")
old_keys = {p for p, _ in junc.values()}

# 1. clashing new keys
seen = collections.Counter(pv["key"] for pv in nj["all_provinces"])
rekey = {}
for pv in nj["all_provinces"]:
    if seen[pv["key"]] > 1 and pv["key"] in old_keys and pv["capital"] not in [r for r, (pk, _) in junc.items() if pk == pv["key"]]:
        new = pv["key"] + "_han"; rekey[id(pv)] = (pv["key"], new); print(f"re-key clashing new province {pv['key']} ({pv['label']}) -> {new}")
        pv["key"] = new
for np_ in nj["new_provinces"]:
    if np_["key"] in old_keys:
        cand = [pv for pv in nj["all_provinces"] if pv["label"] == np_["label"] and pv["key"].endswith("_han")]
        if cand: np_["key"] = cand[0]["key"]
for k, pv in nj["provinces"].items():
    for pv2 in nj["all_provinces"]:
        if pv2["key"].endswith("_han") and pv["province"] == pv2["key"][:-4] and pv.get("capital") == pv2["capital"]:
            pv["province"] = pv2["key"]
# 2. a region in two provinces: keep the existing one
where = collections.defaultdict(list)
for pv in nj["all_provinces"]:
    for m in pv["members"]: where[m].append(pv)
for r, pvs in where.items():
    if len(pvs) < 2: continue
    keep = next((pv for pv in pvs if pv["key"] in old_keys), pvs[0])
    for pv in pvs:
        if pv is not keep:
            pv["members"].remove(r); print(f"{r}: dropped from {pv['key']} (kept in {keep['key']})")
            if pv["capital"] == r and pv["members"]: pv["capital"] = max(pv["members"], key=lambda m: size.get(names.index(m), 0) if m in names else 0)
# 3. one capital per province on the map: leftovers of provinces whose capital moved away
listed = {m for pv in nj["all_provinces"] for m in pv["members"]}
by_prov = collections.defaultdict(list)
for r, (pk, cap) in junc.items():
    if r in names and r not in listed: by_prov[pk].append((r, cap))
for pk, regs in by_prov.items():
    if any(c for _, c in regs) or any(pv["key"] == pk for pv in nj["all_provinces"]): continue
    cap = max((r for r, _ in regs), key=lambda m: size.get(names.index(m), 0))
    nj["all_provinces"].append(dict(key=pk, capital=cap, members=[r for r, _ in regs], label=pk, zhou=None))
    print(f"{pk}: capital moved away - {cap} promoted (members {[r for r, _ in regs]})")
c = collections.Counter(pv["key"] for pv in nj["all_provinces"])
assert not [k for k, v in c.items() if v > 1], [k for k, v in c.items() if v > 1]
json.dump(nj, open(HERE / "regions_new.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("regions_new.json updated")
