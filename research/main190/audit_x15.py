#!/usr/bin/env python3
"""Audit of the x15 master map (hex/map.hex) and its regions / provinces (regions_new.json) - 2026-10-02.
Read-only. Prints one section per check; writes audit_x15.json with every finding."""
import collections, glob, json, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
import town_fix as T
from hexgrid import neighbour_arrays
import hexmap

_, _, w, h, _, f, names = T.load(str(HERE / "hex" / "map.hex"))
lists = hexmap.load(str(HERE / "hex" / "map.hex"))["lists"]
LAND = lists["land_regions"]; SEA = lists["sea_regions"]; NL = len(LAND)
NA = neighbour_arrays(h, w)
reg, terr, imp, slot, sprawl, road, river = (f[k] for k in ("region", "terr", "imp", "slot", "sprawl", "road", "river"))
nj = json.load(open(HERE / "regions_new.json", encoding="utf-8"))
F = {}                                                     # findings
def out(sec, items, show=12):
    F[sec] = items
    print(f"\n== {sec}: {len(items)}")
    for x in items[:show]: print("   ", x)
    if len(items) > show: print(f"    ... +{len(items) - show}")

# display names
disp = {}
for line in open(HERE / "source" / "text" / "db" / "regions.loc.tsv", encoding="utf-8"):
    a = line.rstrip("\n").split("\t")
    if a[0].startswith("regions_onscreen_"): disp[a[0][17:]] = a[1]
for p in nj["provinces"].values(): disp.update(p.get("names", {}))
for k, v in nj.get("renames", {}).items():
    if isinstance(v, str): disp[k] = v
def nm(k): return f"{disp.get(k, '?')} ({k})"
SKIP = lambda k: "non_playable" in k or k.startswith("3k_dlc06_") and k.endswith("_pass")

# ---------------- map.hex
def comps(mask):
    lab = -np.ones((h, w), np.int32); n = 0; sizes = []
    for r0, c0 in zip(*np.nonzero(mask)):
        if lab[r0, c0] >= 0: continue
        st = [(r0, c0)]; lab[r0, c0] = n; s = 0
        while st:
            r, c = st.pop(); s += 1
            for nr, nc, v in NA:
                if v[r, c]:
                    a, b = nr[r, c], nc[r, c]
                    if mask[a, b] and lab[a, b] < 0: lab[a, b] = n; st.append((a, b))
        sizes.append(s); n += 1
    return lab, sizes

land = terr != 1
size = collections.Counter(reg[land].tolist())
split, empty, tiny = [], [], []
for i, k in enumerate(LAND):
    if SKIP(k): continue
    if size.get(i, 0) == 0: empty.append(nm(k)); continue
    _, s = comps((reg == i) & land)
    if len(s) > 1: split.append(f"{nm(k)}: {len(s)} pieces {sorted(s, reverse=True)[:5]}")
    if size[i] < 250: tiny.append((size[i], nm(k)))
out("land regions split into pieces", split)
out("land regions in the header with no hexes", empty)
out("smallest land regions (< 250 hexes)", [f"{n} hexes  {k}" for n, k in sorted(tiny)])
wrong = [(int(r), int(c)) for r, c in zip(*np.nonzero((terr == 1) & (reg < NL) & (reg >= 0)))]
out("sea hexes owned by a land region", wrong[:50])
wrong2 = [(int(c), int(r), names[reg[r, c]]) for r, c in zip(*np.nonzero((terr != 1) & (reg >= NL)))]
out("land hexes owned by a sea region", wrong2[:50])

# towns
town = (slot >= 0) | (sprawl > 0)
tl, tsz = comps(town)
blobs = collections.defaultdict(list)
for r, c in zip(*np.nonzero(town)): blobs[int(tl[r, c])].append((int(c), int(r)))
per_reg = collections.defaultdict(list); mixed = []
for b, hexes in blobs.items():
    rs = collections.Counter(int(reg[r, c]) for c, r in hexes if terr[r, c] != 1)
    main = rs.most_common(1)[0][0] if rs else -1
    per_reg[main].append(len(hexes))
    if len(rs) > 1: mixed.append(f"town near hex {hexes[0]} spans regions {[names[x] for x in rs]}")
notown = [nm(k) for i, k in enumerate(LAND) if not SKIP(k) and size.get(i, 0) and i not in per_reg]
multi = [f"{nm(LAND[i])}: {len(v)} town blobs {v}" for i, v in per_reg.items() if 0 <= i < NL and len(v) > 1]
noslot0 = [nm(LAND[i]) for i in per_reg if 0 <= i < NL and not ((slot == 0) & (reg == i)).any()]
out("land regions without a town", notown)
out("regions with more than one town blob", multi)
out("town footprints spanning two land regions", mixed)
out("towns without a slot-0 hex", noslot0)

# capital / resource footprint vs province role
cap_of = {pv["capital"] for pv in nj["all_provinces"]}
role = []
for i, v in per_reg.items():
    if not (0 <= i < NL) or SKIP(LAND[i]): continue
    n0 = int(((slot == 0) & (reg == i)).sum()); k = LAND[i]
    if k in cap_of and n0 < 19: role.append(f"capital with a resource-size town ({n0} slot-0 hexes): {nm(k)}")
    if k not in cap_of and n0 >= 19: role.append(f"non-capital with a city-size town ({n0} slot-0 hexes): {nm(k)}")
out("town size vs province role (capital = 19 slot-0 city footprint)", role, 30)

# pinches / sprawl hazard rule
src = open(HERE / "town_pinch_fix.py").read(); src = src[:src.index("args = [a for a")].replace("if not DRY: shutil.copy2", "if False: shutil.copy2")
g = {"__file__": str(HERE / "town_pinch_fix.py"), "__name__": "tpf"}; sys.argv = ["x", "--dry"]; exec(src, g)
pin, haz = [], []
for i in sorted(per_reg):
    if not (0 <= i < NL): continue
    Fp = g["footprint"](i)
    if not Fp: continue
    p = g["town_pinches"](Fp)
    if p: pin.append(f"{nm(LAND[i])}: {len(p)} pinched hexes")
    if not g["hazard_ok"](Fp): haz.append(nm(LAND[i]))
out("towns with pinched hexes within 2 (missing city bar risk)", pin, 40)
out("towns breaking CAIME's sprawl hazard rule", haz, 40)

# roads: every town on the road network, network pieces
rd = road > 0
rl, rsz = comps(rd | town)
main_net = int(np.argmax(rsz)) if rsz else -1
offnet = []
for i, v in per_reg.items():
    if not (0 <= i < NL) or SKIP(LAND[i]): continue
    hexes = [(r, c) for r, c in zip(*np.nonzero(town & (reg == i)))]
    if hexes and all(rl[r, c] != main_net for r, c in hexes):
        touches = any(road[r, c] for r, c in hexes) or any(v_[r, c] and road[nr_[r, c], nc_[r, c]] for r, c in hexes for nr_, nc_, v_ in NA)
        offnet.append(f"{nm(LAND[i])}: {'no road at all' if not touches else 'on a road piece cut off from the main network'}")
out("towns not on the main road network (islands excepted by eye)", offnet, 40)
half = 0
for d, (nr, nc, v) in enumerate(NA):
    bit = (road >> d) & 1
    back = np.zeros_like(bit); m = v & (bit > 0)
    back[m] = (road[nr[m], nc[m]] >> ((d + 3) % 6)) & 1
    half += int((m & (back == 0)).sum())
out("one-sided road edges (bit set on one hex only)", [half] if half else [])

# passable land of a region cut off from its town (unreachable pockets)
pockets = []
for i, v in per_reg.items():
    if not (0 <= i < NL) or SKIP(LAND[i]): continue
    m = (reg == i) & (terr == 0) & (imp == 0)
    lab, s = comps(m)
    tt = {int(lab[r, c]) for r, c in zip(*np.nonzero(town & (reg == i))) if lab[r, c] >= 0}
    lost = sum(x for j, x in enumerate(s) if j not in tt and x >= 30)
    if lost: pockets.append((lost, f"{nm(LAND[i])}: {lost} passable hexes in pockets >= 30 not connected (inside the region) to the town"))
out("passable pockets cut off from their own town", [x for _, x in sorted(pockets, reverse=True)], 25)

# coast ring
nsea = np.zeros((h, w), bool); nland = np.zeros((h, w), bool)
for nr, nc, v in NA: nsea |= v & (terr[nr, nc] == 1); nland |= v & (terr[nr, nc] == 0)
out("plain land touching sea (coast-ring rule)", [(int(c), int(r)) for r, c in zip(*np.nonzero((terr == 0) & nsea))][:40])
out("beach/cliff not touching plain land", [(int(c), int(r)) for r, c in zip(*np.nonzero(np.isin(terr, [2, 3]) & ~nland))][:40])

# ---------------- regions / provinces
P = nj["all_provinces"]
mem = collections.Counter(m for pv in P for m in pv["members"])
out("regions in two provinces", [nm(k) for k, n in mem.items() if n > 1])
out("land regions on the map in no province", [nm(k) for i, k in enumerate(LAND) if not SKIP(k) and size.get(i, 0) and k not in mem])
out("province members not on the map", [f"{pv['key']}: {m}" for pv in P for m in pv["members"] if m not in LAND])
out("provinces whose capital is not a member / no capital", [pv["key"] for pv in P if pv.get("capital") not in pv["members"]])
out("provinces with more than 4 regions", [f"{pv['key']} ({len(pv['members'])})" for pv in P if len(pv["members"]) > 4])
junc = {}
for line in open(HERE / "source" / "db" / "region_to_province_junctions_tables" / "data__.tsv", encoding="utf-8"):
    a = line.rstrip("\n").split("\t")
    if len(a) >= 3 and not a[0].startswith(("#", "province")): junc[a[1]] = (a[0], a[2] == "true")
where = {m: pv for pv in P for m in pv["members"]}
out("190E capitals that are not a capital now", [f"{nm(r)} in {where[r]['key']}" for r, (pk, c) in junc.items() if c and r in where and where[r]["capital"] != r])
out("190E capitals heading a province under another key", [f"{nm(r)}: {pk} -> {where[r]['key']}" for r, (pk, c) in junc.items() if c and r in where and where[r]["capital"] == r and where[r]["key"] != pk])
# province contiguity
adj = collections.defaultdict(set)
for nr, nc, v in NA:
    m = v & land & land[nr, nc] & (reg != reg[nr, nc])
    for a, b in zip(reg[m].tolist(), reg[nr, nc][m].tolist()): adj[names[a]].add(names[b])
noncontig = []
for pv in P:
    ms = [m for m in pv["members"] if m in LAND]
    if len(ms) < 2: continue
    seen = {ms[0]}; st = [ms[0]]
    while st:
        a = st.pop()
        for b in adj[a]:
            if b in ms and b not in seen: seen.add(b); st.append(b)
    if len(seen) < len(ms): noncontig.append(f"{pv['key']} ({pv.get('label')}): {[disp.get(m, m) for m in ms if m not in seen]} not touching {disp.get(ms[0], ms[0])}'s group")
out("provinces whose regions do not touch each other", noncontig, 30)
out("single-region provinces", [f"{pv['key']} ({disp.get(pv['capital'], pv['capital'])})" for pv in P if len(pv["members"]) == 1 and not SKIP(pv["capital"])], 30)
# names
onmap = [k for i, k in enumerate(LAND) if not SKIP(k) and size.get(i, 0)]
dn = collections.defaultdict(list)
for k in onmap: dn[disp.get(k, "?").strip().lower()].append(k)
out("duplicate region display names", [f"{n!r}: {ks}" for n, ks in dn.items() if len(ks) > 1 and n != "?"])
out("regions without a display name", [k for k in onmap if k not in disp])
labels = collections.Counter((pv.get("label") or "").lower() for pv in P)
out("duplicate province labels", [l for l, n in labels.items() if n > 1 and l])
# DB coverage
dbreg = set()
for p in glob.glob(str(HERE / "db_out" / "db" / "regions_tables" / "*.tsv")):
    for line in open(p, encoding="utf-8"): dbreg.add(line.split("\t")[0])
out("map regions missing from the regions DB table", [k for k in onmap if k not in dbreg])
json.dump(F, open(HERE / "audit_x15.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=str)
print("\nwrote audit_x15.json")
