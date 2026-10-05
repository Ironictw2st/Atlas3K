#!/usr/bin/env python3
"""Stage B of korea_x15.py: writes hex/map.hex (new regions + header, carved territory, opened north, SilverCat's rivers,
re-stamped towns, roads to the new towns) and regions_new.json (provinces / re-keys / renames / unowned new provinces /
Guknae-seong retemplated to a city). Backups: hex/map_pre_korea_<ts>.hex, regions_new_before_korea_<ts>.json."""
import heapq, json, shutil, struct, sys, time, zlib
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent
for p in (HERE / "korea_ref", HERE, HERE.parent / "guandu", HERE.parent, Path(r"Z:/Claude/CAIME/webpainter")): sys.path.insert(0, str(p))
import town_fix as T, hexmap
from hexgrid import neighbour_arrays, direction_between

ZHOU = {"NorthBuyeo": "KoreaNorth", "NorthOkjeo": "KoreaNorth", "Goguryeo": "KoreaNorth", "EastOkjeo": "KoreaNorth",
        "Xuantu": "KoreaNorth", "Liaodong": "Youzhou", "Lelang": "KoreaNorth", "Dongye": "KoreaNE", "Daifang": "KoreaNorth",
        "Hanseong": "KoreaSouth", "Ye": "KoreaNE", "Mahan": "KoreaSouth", "Jinhan": "KoreaSouth", "Byeonhan": "KoreaSouth",
        "ChimmiDarye": "KoreaSouth", "Tamna": "KoreaSouth"}
NEW_PROVINCES = {"NorthBuyeo", "NorthOkjeo", "Goguryeo", "Tamna"}
PROVINCE_RENAMES = {"3k_ironic_province_hyunto": "Xuantu", "3k_ironic_province_dongokjeo": "East Okjeo"}


def apply(ctx, P, OLD_PROVINCES):
    import town_restamp as TR
    from rebuild_hex import pack, unpack, replace_region_lists
    from class_fill import smooth_noise
    ts = time.strftime("%Y%m%d_%H%M%S")
    HEX = HERE / "hex" / "map.hex"; J = HERE / "regions_new.json"
    shutil.copy2(HEX, HERE / "hex" / f"map_pre_korea_{ts}.hex"); shutil.copy2(J, HERE / f"regions_new_before_korea_{ts}.json")
    b, Pp, w, h, g, f, names = T.load(str(HEX))
    L = hexmap.load(str(HEX))["lists"]; LAND, SEA = L["land_regions"], L["sea_regions"]; NL = len(LAND)
    owner, elig, opened, seeds, rhex = (ctx[k] for k in ("owner", "elig", "opened", "seeds", "rhex"))
    new_keys = [s[1] for s in seeds if s[2]]
    assert not set(new_keys) & set(names), set(new_keys) & set(names)
    NN = len(new_keys)
    orig = f["region"].copy()
    reg = f["region"].copy(); reg[reg >= NL] += NN                       # sea ids shift past the new land ids
    rid = {k: names.index(k) for k in names[:NL]}; rid.update({k: NL + i for i, k in enumerate(new_keys)})
    seed_rid = np.array([rid[s[1]] for s in seeds])
    m = owner >= 0
    reg[m] = seed_rid[owner[m]]
    f["region"] = reg
    f["imp"][opened & (f["terr"] == 0)] = 0                             # the north opens (mountain tiles removed in the tile map)
    NA = neighbour_arrays(h, w)
    # rivers: SilverCat's replace ours inside the carve
    for d, (nr, nc, v) in enumerate(NA):
        hit = v & elig[nr, nc] & elig
        f["river"][hit] &= ~(1 << d)
    for (c, r, d) in rhex:
        if elig[r, c]: f["river"][r, c] |= (1 << d)
    # towns: new and moved ones get one slot-0 hex at the target, then town_restamp grows the footprint
    slot, spr = f["slot"], f["sprawl"]
    # towns that stay keep their whole footprint (the carve could hand an edge hex to a neighbour)
    moving = {rid[s[1]] for s in seeds if s[2] or s[6]}
    tz0 = (slot >= 0) | (spr > 0)
    NPk = names.index("3k_main_reg_non_playable")
    for k in np.unique(orig[tz0 & (orig < NL)]).tolist():
        if k in moving or k == NPk: continue
        reg[tz0 & (orig == k)] = k
    f["region"] = reg
    stamped, kept = [], []
    todo = []
    for sd in seeds:                                              # 1. clear every moving town's old footprint
        (pk, rk, new, nm, cap, (c, r), move) = sd; k = rid[rk]
        if not (new or move): continue
        if not new and ((slot > 0) & (orig == k)).any(): kept.append(rk); continue
        if not new:
            oldfp = ((slot >= 0) | (spr > 0)) & (orig == k)
            slot[oldfp] = -1; spr[oldfp] = 0
        todo.append(sd)
    # the north provinces open completely (user: mountains there go, to be replaced by hand)
    northk = [rid[s_[1]] for s_ in seeds if s_[0] in ("NorthBuyeo", "NorthOkjeo")]
    f["imp"][np.isin(reg, northk) & (f["terr"] == 0)] = 0
    for (pk, rk, new, nm, cap, (c, r), move) in todo:            # 2. one slot-0 hex at each target
        k = rid[rk]
        if reg[r, c] != k or f["terr"][r, c] != 0:                   # the seed hex must be in its own region
            rr_, cc_ = np.nonzero((reg == k) & (f["terr"] == 0) & (f["imp"] == 0))
            j = int(np.argmin((cc_ - c) ** 2 + (rr_ - r) ** 2)); c, r = int(cc_[j]), int(rr_[j])
        slot[r, c] = 0; spr[r, c] = 1
        stamped.append((rk, k, cap, (c, r)))
    redge = np.zeros((h, w), np.int32)
    for d, (nr, nc, v) in enumerate(NA): redge |= ((v & (reg[nr, nc] != reg)).astype(np.int32) << d)
    f["redge"] = redge
    G = pack(f); G[..., 10:15] = g[..., 10:15]
    reports = []
    for rk, k, cap, (c, r) in stamped:
        _, rep = TR.restamp(G, k, "city" if cap else "resource")
        reports.append((rk, rep.get("total"), rep.get("shift"), rep.get("warnings") or rep.get("error")))
    f = unpack(G); f["redge"] = redge
    # roads: each stamped town joins the road network (winding Dijkstra, prebuild_fix's cost)
    noise = 0.5 * smooth_noise((h, w), 20, 61) + 0.3 * smooth_noise((h, w), 6, 62) + 0.2 * smooth_noise((h, w), 2, 63)
    noise = (noise - noise.min()) / (np.ptp(noise) + 1e-9)
    road = f["road"].copy(); town = (f["slot"] >= 0) | (f["sprawl"] > 0)
    roads = []
    for rk, k, cap, _ in stamped:
        mine = town & (f["region"] == k)
        net = ((road > 0) | town) & ~mine
        src = [(int(r), int(c)) for r, c in zip(*np.nonzero(mine))]
        if not src: roads.append((rk, "no town")); continue
        dist = {p_: 0.0 for p_ in src}; prev = {p_: None for p_ in src}; q = [(0.0, p_) for p_ in src]; heapq.heapify(q); hit = None
        while q:
            dd, a = heapq.heappop(q)
            if dd > dist.get(a, 1e18): continue
            if net[a] and prev[a] is not None: hit = a; break
            for d, (nr, nc, v) in enumerate(NA):
                if not v[a]: continue
                bq = (int(nr[a]), int(nc[a]))
                if f["terr"][bq] != 0 or f["imp"][bq] or abs(bq[0] - src[0][0]) > 220 or abs(bq[1] - src[0][1]) > 220: continue
                nd = dd + 1.0 + 3.0 * float(noise[bq]) + (6.0 if (f["river"][a] >> d) & 1 else 0.0)
                if nd < dist.get(bq, 1e18): dist[bq] = nd; prev[bq] = a; heapq.heappush(q, (nd, bq))
        if hit is None: roads.append((rk, None)); continue
        path = [hit]
        while prev[path[-1]] is not None: path.append(prev[path[-1]])
        for a, bq in zip(path, path[1:]):
            d = direction_between((a[1], a[0]), (bq[1], bq[0]))
            if d < 0: continue
            road[a] |= 1 << d; road[bq] |= 1 << ((d + 3) % 6)
        roads.append((rk, len(path)))
    f["road"] = road
    G = pack(f); G[..., 10:15] = g[..., 10:15]
    src_b = HEX.read_bytes()
    prefix = replace_region_lists(src_b[:Pp], LAND + new_keys, SEA)
    body = prefix + struct.pack("<II", w, h) + G.tobytes()
    HEX.write_bytes(body + struct.pack("<I", zlib.crc32(body) & 0xFFFFFFFF))
    north = opened | np.isin(reg, northk)
    np.save(HERE / "korea_ref" / "north_open.npy", north)
    # regions_new.json
    nj = json.load(open(J, encoding="utf-8"))
    ours = {s[1] for s in seeds}
    drop_keys = {v[0] for v in P.values()} | set(OLD_PROVINCES)
    for pv in nj["all_provinces"]:
        pv["members"] = [x for x in pv["members"] if x not in ours]
    nj["all_provinces"] = [pv for pv in nj["all_provinces"] if pv["key"] not in drop_keys and pv["members"]]
    nj["new_provinces"] = [p_ for p_ in nj["new_provinces"] if p_["key"] not in OLD_PROVINCES]
    for k_ in list(nj["provinces"]):
        if nj["provinces"][k_]["province"] in OLD_PROVINCES: del nj["provinces"][k_]
    for pk, (key, label, zhou, mem) in P.items():
        cap = next(x[0] for x in mem if x[4])
        nj["all_provinces"].append(dict(key=key, capital=cap, members=[x[0] for x in mem], label=label, zhou=ZHOU[pk]))
        if pk in NEW_PROVINCES: nj["new_provinces"].append(dict(key=key, label=label, zhou=ZHOU[pk]))
        newr = [x for x in mem if x[1]]
        if not newr: continue
        towns_ = {}
        for x in newr:
            rr_, cc_ = np.nonzero((f["slot"] == 0) & (reg == rid[x[0]]))
            towns_[x[0]] = [int(cc_.mean()), int(rr_.mean())] if len(rr_) else [0, 0]
        regs = [x[0] for x in newr]
        nj["provinces"][key] = dict(group="korea", label=label, zhou=ZHOU[pk], province=key,
                                    attach=not (pk in NEW_PROVINCES and cap in regs),
                                    regions=([cap] if cap in regs else []) + [r_ for r_ in regs if r_ != cap],
                                    names={x[0]: x[2] for x in newr}, towns=towns_,
                                    hexes={x[0]: int((reg == rid[x[0]]).sum()) for x in newr},
                                    owners={x[0]: None for x in newr}, capital=cap, importance={x[0]: "medium" for x in newr})
    for pk, (key, label, zhou, mem) in P.items():
        for (rk, new, nm, ic, cap) in mem:
            if not new and nm: nj["renames"][rk] = nm
    nj["province_renames"] = {**nj.get("province_renames", {}), **PROVINCE_RENAMES}
    nj.setdefault("retemplate", {})["ironic_region_dongokjeo_resource_2"] = {"type": "city"}
    json.dump(nj, open(J, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"applied: +{NN} land regions ({', '.join(new_keys)}); opened {int((opened & (f['terr'] == 0)).sum())} hexes; "
          f"river edge records {len(rhex)}; towns stamped {len(stamped)} (ports kept in place: {kept})")
    for x in reports: print("  town", x)
    for x in roads: print("  road", x)
