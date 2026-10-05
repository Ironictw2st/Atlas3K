#!/usr/bin/env python3
"""x1.5 + Hexi / steppe pads: carve the approved region proposal (user 2026-10-01: "implement it end to end").

Input  hex/map_precarve.hex (1478x1133: CAIME x1.5 upscale + town_fix + west 140 / north 80 pads, non-playable)
       proposal_x15/build_export.json + build_masks.npz (the proposal session's consolidated export, padded grid)
Output hex/map.hex, regions_new.json (regions_db.py format + renames / province moves / owners), previews/carve_x15.png

Steps (reusing the round-6/7 carve, regions_carve6.py):
 1. new land from the masks: lakes -> 3k_main_sea_lake water; Qilian / Xiping ring / steppe ranges -> impassable;
    Hexi / Xiping / steppe playable land opened (passable, region decided by the territory step); desert ->
    non-playable. Only non-playable land and the old land of the moved regions change; other regions keep theirs.
 2. sites: every new / moved town at its exported hex, or the nearest hex within NUDGE that passes the footprint rules
    (plain land, no props, no river under a slot, CAIME sprawl rule incl. the city-bar contact rule).
 3. territory: noisy multi-source Dijkstra (ridges / rivers expensive, 3-octave noise, domain warp on open land);
    new / moved regions take existing land they win; opened land goes only to new / moved regions; donor protection;
    majority smoothing; stray clean-up; unclaimed opened land back to non-playable.
 4. valley bridges for towns cut off from the main land; roads from every new / moved town to the network; opened-land
    fields (ground from the blend raster, climate / attrition from the nearest playable hex); bridge banks; write.
"""
import collections, json, os, struct, sys, zlib
from pathlib import Path
import numpy as np
from PIL import Image
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent, HERE.parent.parent / "output" / "pylibs"): sys.path.insert(0, str(p))
import crop_scale_map_hex as C, hexmap
from rebuild_hex import unpack, pack, replace_region_lists
from hexgrid import neighbour, neighbour_arrays
from regions_carve import template, place_fp, dijkstra, components, hex_blend_and_height, route, hdist, MOUNTAIN_BLEND, GROUND_BY_BLEND
from regions_carve6 import dijkstra_hs, walk_mask, fix_bridge_banks, multi_bfs, prop_mask
from class_fill import smooth_noise

SRC = HERE / "hex" / "map_precarve.hex"; OUT = HERE / "hex" / "map.hex"
EXPORT = HERE / "proposal_x15" / "build_export.json"; MASKS = HERE / "proposal_x15" / "build_masks.npz"
TEMPLATES = {"capital": "3k_main_xihe_capital", "resource": "3k_main_anding_resource_3"}
NON_PLAYABLE = "3k_main_reg_non_playable"; LAKE = "3k_main_sea_lake"
NUDGE = 8                    # hexes: search radius when the exported site fails the footprint / sprawl rules
NOISE_AMP = 1.6; RIVER_COST = 8.0; IMP_COST = 3.0; SLOPE_COST = 6.0
HEAD_START = 10.0            # existing towns start this far behind (new regions take a vanilla-size share)
MIN_AREA = 550; MIN_NEW = 420
OPEN_MAX = 4800              # a region's share of opened land (Hexi / steppe frontier) is capped at this many hexes


def grow(m_, NA, k):
    for _ in range(k):
        g_ = m_.copy()
        for nr, nc, v in NA: g_ |= v & m_[nr, nc]
        m_ = g_
    return m_


def main(log=print, preview=HERE / "previews" / "carve_x15.png"):
    src = SRC.read_bytes(); P, w, h = C.locate_dims(src)
    g = np.frombuffer(src, np.uint8, 16 * w * h, P + 8).reshape(h, w, 16).copy()
    f = unpack(g); f["redge"] = (g[..., 15].astype(np.int32) >> 2) & 63
    L = hexmap.load(str(SRC))["lists"]; land, sea_names = L["land_regions"], L["sea_regions"]; NL = len(land)
    names = land + sea_names; NP = names.index(NON_PLAYABLE); lake_id = names.index(LAKE)
    NA = neighbour_arrays(h, w); terr, reg = f["terr"], f["region"]
    ex = json.load(open(EXPORT, encoding="utf-8")); M = np.load(MASKS)
    for t in ex["towns"]:                                    # export schema -> carve fields (user: all 95 towns, incl. the 7 landmarks)
        t["key"] = t["new_key"]; t["moved"] = bool(t.get("moved") or t.get("hex_old_padded"))
    # user: all 7 steppe landmarks are built (the export flags them include=false and leaves them out of the provinces):
    # each joins its steppe group's province; Daihai goes to Tuoba (Kebineng would exceed the user's 4-region limit)
    LANDMARK_PROV = {"ironic_nomad_budugen_resource_2": "3k_ironic_province_nomad_budugen",
                     "ironic_nomad_kebineng_resource_3": "3k_ironic_province_nomad_tuoba",
                     "ironic_nomad_kebineng_resource_4": "3k_ironic_province_nomad_kebineng",
                     "ironic_nomad_wuhuan_liaoxi_resource_2": "3k_ironic_province_nomad_wuhuan_liaoxi",
                     "ironic_nomad_wuhuan_liaoxi_resource_3": "3k_ironic_province_nomad_wuhuan_liaoxi",
                     "ironic_nomad_wuhuan_shanggu_resource_1": "3k_ironic_province_nomad_wuhuan_shanggu",
                     "ironic_nomad_suli_resource_3": "3k_ironic_province_nomad_suli"}
    listed_ = {m for pv in ex["provinces"] for m in pv["members"]}
    for pv in ex["provinces"]:
        for k_, pk_ in LANDMARK_PROV.items():
            if pk_ == pv["key"] and k_ not in listed_: pv["members"].append(k_)
    for t in ex["towns"]:
        if t["key"] in LANDMARK_PROV and t["key"] not in listed_: t["province_key"] = LANDMARK_PROV[t["key"]]
    assert max(len(pv["members"]) for pv in ex["provinces"]) <= 4
    ex["renames"] = {r["region"]: r["new_name"] for r in ex.get("renames", [])}
    ex["existing_province_changes"] = {r["region"]: r["to_province"] for r in ex.get("existing_province_changes", [])}
    for k in M.files: assert M[k].shape == (h, w), (k, M[k].shape, (h, w))
    assert tuple(ex["grid"]) == (w, h), (ex["grid"], (w, h))
    hb, hh = hex_blend_and_height(w, h); mountain = np.isin(hb, MOUNTAIN_BLEND)
    slope = np.zeros((h, w), np.float32)
    for nr, nc, v in NA: slope = np.maximum(slope, np.where(v, np.abs(hh[nr, nc] - hh), 0))
    slope = np.clip(slope / max(1.0, float(np.percentile(slope[terr != 1], 95))), 0, 1)
    props, nprops = prop_mask(w, h)
    tpl = {k: template(f, names, v) for k, v in TEMPLATES.items()}
    town = lambda: (f["slot"] >= 0) | (f["sprawl"] == 1)
    passes = [i for i, n in enumerate(land) if n.endswith("_pass")]
    log(f"grid {w}x{h}; {NL} land regions; props {nprops}; towns in the export {len(ex['towns'])}")

    # ---------------- 1. new land ---------------------------------------------------------------------------------
    moved_keys = [t["key"] for t in ex["towns"] if t.get("moved")]
    moved_ids = {names.index(k) for k in moved_keys}
    free = np.isin(reg, list(moved_ids)) & (terr != 1)
    old_site = {}
    for i in moved_ids:
        sl = np.argwhere((reg == i) & (f["slot"] == 0)); old_site[names[i]] = [int(sl[0][1]), int(sl[0][0])] if len(sl) else None
        m_ = reg == i; f["slot"][m_] = -1; f["sprawl"][m_] = 0
    opened = (M["hexi_play"] | M["steppe_play"]) & (terr != 1) & ~town()
    mtn_new = (M["hexi_mountain"] | M["steppe_mountain"]) & (terr != 1) & ~town() & ~opened
    desert = M["hexi_desert"] & (terr != 1) & ~town() & ~opened & ~mtn_new
    lakes = M["lakes"] & ~town()
    np_or_free = (reg == NP) | free
    lakes &= np_or_free | (reg == lake_id)
    terr[lakes] = 1; reg[lakes] = lake_id; f["imp"][lakes] = 1; f["ground"][lakes] = 18
    for k_ in ("road", "river", "bridge", "trade", "restr", "b9", "slot", "sprawl"): f[k_][lakes] = -1 if k_ == "slot" else 0
    f["attr"][lakes] = -1; f["aoi"][lakes] = -1
    cleared = M["hexi_cleared"] & free & ~opened                # old land of the moved Hexi / Xiping regions -> desert / plateau
    shut = ((mtn_new | desert) & np_or_free | cleared) & ~lakes
    reg[shut] = NP; f["imp"][shut] = 1
    for k_ in ("road", "river", "bridge"): f[k_][shut] = 0
    op = opened & np_or_free & ~lakes
    f["imp"][op] = 0           # the proposal's masks decide: playable land passable (Xiping basins sit at 3000-3300 m,
                               # which the DEM class rules call mountain), its ranges impassable (mtn_new above)
    for k_ in ("road", "river", "bridge"): f[k_][op & (reg == NP)] = 0
    free_rest = free & ~op & ~shut & ~lakes
    free = free & ~shut & ~lakes                              # shut (desert / ranges / cleared) land is never handed out again                   # freed land outside the new land (e.g. Xiping's old plateau)
    log(f"new land: opened {int(op.sum())}, ranges {int((mtn_new & np_or_free).sum())}, desert {int((desert & np_or_free).sum())}, "
        f"lakes {int(lakes.sum())}; freed by moved regions {int(free.sum())} ({int(free_rest.sum())} outside the new land)")

    # ---------------- 2. sites ------------------------------------------------------------------------------------
    def sprawl_ok(fp):
        fps = {(x, y) for x, y, _, _ in fp}
        def ring_(src_, excl):
            out = set()
            for x, y in src_:
                for k1 in range(6):
                    q = neighbour(x, y, k1)
                    if q not in excl and 0 <= q[0] < w and 0 <= q[1] < h: out.add(q)
            return out
        r1 = ring_(fps, fps); r2 = ring_(r1, fps | r1); r3 = ring_(r2, fps | r1 | r2)
        rv = river_edge
        ob = {q for q in r1 | r2 | r3 if rv[q[1], q[0]] or terr[q[1], q[0]] in (2, 3) or f["imp"][q[1], q[0]] == 1}
        if not ob: return True
        comps, seen = [], set()
        for q in ob:
            if q in seen: continue
            comp, st = set(), [q]; seen.add(q)
            while st:
                a = st.pop(); comp.add(a)
                for k1 in range(6):
                    b = neighbour(*a, k1)
                    if b in ob and b not in seen: seen.add(b); st.append(b)
            comps.append(comp)
        if len([c_ for c_ in comps if c_ & r1]) > 1: return False
        return not any((c_ & r2) and not (c_ & r1) for c_ in comps)

    # river runs on hex edges: the hex across a river edge counts as river terrain too (CAIME sprawl validator)
    river_edge = f["river"] > 0
    for r_, c_ in zip(*np.nonzero(f["river"] > 0)):
        for k1 in range(6):
            if (f["river"][r_, c_] >> k1) & 1:
                q = neighbour(int(c_), int(r_), k1)
                if 0 <= q[0] < w and 0 <= q[1] < h: river_edge[q[1], q[0]] = True
    occ = town().copy()                                       # hexes taken by towns (incl. those placed below)
    ok_site = (terr == 0) & ~props & ~np.isin(reg, passes) & ~shut

    def fits(c, r, kind):
        fp = place_fp(tpl[kind], c, r)
        for x, y, s_, _ in fp:
            if not (0 <= x < w and 0 <= y < h) or not ok_site[y, x] or occ[y, x]: return None
            if s_ >= 0 and river_edge[y, x]: return None
        return fp if sprawl_ok(fp) else None

    def site(c0, r0, kind):
        fp = fits(c0, r0, kind)
        if fp: return c0, r0, fp, 0
        best = []
        for r in range(max(0, r0 - NUDGE), min(h, r0 + NUDGE + 1)):
            for c in range(max(0, c0 - NUDGE), min(w, c0 + NUDGE + 1)):
                d = hdist((c, r), (c0, r0))
                if 0 < d <= NUDGE: best.append((d + 4.0 * slope[r, c], c, r))
        for _, c, r in sorted(best):
            fp = fits(c, r, kind)
            if fp: return c, r, fp, hdist((c, r), (c0, r0))
        return None

    sites, dropped = [], []
    for t in sorted(ex["towns"], key=lambda t: (not t.get("moved"), t["kind"] != "capital")):
        kind = "capital" if t["kind"] == "capital" else "resource"
        res = site(*t["hex"], kind)
        if res is None:                                       # wider search before giving up
            global NUDGE
            n0 = NUDGE; NUDGE = 16; res = site(*t["hex"], kind); NUDGE = n0
            if res: log(f"  {t['key']}: site found in the wider search")
        if res is None:
            dropped.append(t["key"]); log(f"  ! no valid site within {NUDGE} of {tuple(t['hex'])} for {t['key']} ({t['name']})"); continue
        c, r, fp, off = res
        for x, y, _, _ in fp: occ[y, x] = True
        sites.append((t, kind, c, r, fp, off))
    new_list = [s for s in sites if not s[0].get("moved")]
    NN = len(new_list)
    reg[reg >= NL] += NN                                       # sea ids (incl. the lake) shift up past the new land ids
    lake_id += NN
    rid = {s[0]["key"]: NL + k for k, s in enumerate(new_list)}
    for t, kind, c, r, fp, off in sites:
        i = names.index(t["key"]) if t.get("moved") else rid[t["key"]]
        for x, y, s_, sp in fp:
            reg[y, x] = i; f["slot"][y, x] = s_; f["sprawl"][y, x] = sp; f["imp"][y, x] = 0
        log(f"  {'moved' if t.get('moved') else 'new  '} {t['key']:44s} {t['name']:18s} ({c},{r}){f'  nudged {off}' if off else ''}")
    names_all = land + [s[0]["key"] for s in new_list] + sea_names
    new_ids = set(rid.values())
    changed = new_ids | moved_ids
    placed = {t["key"]: (c, r) for t, kind, c, r, fp, off in sites}
    log(f"placed {len(sites)} towns ({NN} new regions, {len(moved_ids)} moved); dropped {dropped or 'none'}")

    # ---------------- 3. territory --------------------------------------------------------------------------------
    reg0 = reg.copy()
    noise = 0.4 * smooth_noise((h, w), 30, 26) + 0.35 * smooth_noise((h, w), 10, 21) + 0.25 * smooth_noise((h, w), 3, 22)
    noise = (noise - noise.min()) / (np.ptp(noise) + 1e-9)
    small_river = (f["river"] > 0) & (terr != 1)
    cost = 1.0 + NOISE_AMP * noise + RIVER_COST * small_river + IMP_COST * (f["imp"] == 1) + SLOPE_COST * slope
    land_ok = terr != 1
    playable = land_ok & (reg >= 0) & (reg != NP) & ~np.isin(reg, passes) & ~free
    srcs = {}
    for i in set(np.unique(reg[f["slot"] == 0]).tolist()):
        if i < 0 or i >= NL + NN or i == NP: continue
        for y, x in np.argwhere((reg == i) & (f["slot"] == 0)): srcs[(int(x), int(y))] = int(i)
    area = playable | op | (free & land_ok)
    head = {i: HEAD_START for i in set(srcs.values()) if i not in changed}
    dlab, lab = dijkstra_hs(srcs, head, cost, area, w, h)
    # domain warp on open land (flat desert / steppe: a cost split alone gives near-straight bisectors)
    yy_, xx_ = np.mgrid[0:h, 0:w]
    dx_ = 20 * smooth_noise((h, w), 30, 41) + 4 * smooth_noise((h, w), 8, 43)
    dy_ = 20 * smooth_noise((h, w), 30, 42) + 4 * smooth_noise((h, w), 8, 44)
    sy_ = np.clip(np.rint(yy_ + dy_).astype(int), 0, h - 1); sx_ = np.clip(np.rint(xx_ + dx_).astype(int), 0, w - 1)
    lw_ = lab[sy_, sx_]
    warp_ok = (op | free) & (lab >= 0) & (lw_ >= 0) & np.isin(lw_, list(changed)) & np.isin(lab, list(changed))
    lab = np.where(warp_ok, lw_, lab)
    # new regions carve existing land (donors) and new land; moved Hexi / Xiping regions only take the new land
    # (proposal: existing regions keep their borders; the moved ones live in the corridor / valleys)
    win_new = np.isin(lab, list(new_ids)); win_mov = np.isin(lab, list(moved_ids))
    take = (lab >= 0) & ~town() & (win_new & (playable | op | free) | win_mov & (op | free))
    reg[take] = lab[take]
    # opened land nobody new claimed, and freed land left over: non-playable
    left = (op | free_rest) & ~np.isin(reg, list(changed)) & ~town() & land_ok & (np.isin(reg0, [NP]) | free)
    reg[left] = NP; f["imp"][left] = 1
    # frontier cap: a region keeps at most OPEN_MAX opened hexes, the cheapest (nearest) ones
    for i in changed:
        mine = np.argwhere((reg == i) & op & ~town())
        if len(mine) > OPEN_MAX:
            far = mine[np.argsort(-dlab[mine[:, 0], mine[:, 1]])][:len(mine) - OPEN_MAX]
            reg[far[:, 0], far[:, 1]] = NP; f["imp"][far[:, 0], far[:, 1]] = 1
    log(f"territory: {int(take.sum())} hexes to new / moved regions; {int(left.sum())} unclaimed opened / freed -> non-playable")
    # donor protection: an existing region cut below MIN_AREA gets back its own hexes nearest its town
    for i in set(int(x) for x in np.unique(reg0[take])) - changed - {NP, -1}:
        a0, a1 = int(((reg0 == i) & land_ok).sum()), int(((reg == i) & land_ok).sum())
        if a1 >= MIN_AREA or a0 < MIN_AREA: continue
        tw = [(int(x), int(y)) for y, x in np.argwhere((reg == i) & (f["slot"] == 0))]
        if not tw: continue
        dd, _ = dijkstra({t_: 0 for t_ in tw}, cost, (reg0 == i) & land_ok, w, h)
        lost = np.argwhere((reg0 == i) & (reg != i) & land_ok & ~town() & np.isfinite(dd))
        lost = lost[np.argsort(dd[lost[:, 0], lost[:, 1]])][:MIN_AREA - a1]
        reg[lost[:, 0], lost[:, 1]] = i
        log(f"  donor protection: {names_all[i]} {a1} -> {int(((reg == i) & land_ok).sum())} hexes")
    # majority smoothing on borders of changed regions
    for it in range(3):
        n_sw = 0; cnt = {}
        for nr, nc, v in NA:
            nb = np.where(v, reg[nr, nc], -9)
            for lbl in changed: cnt[lbl] = cnt.get(lbl, 0) + (nb == lbl)
        for lbl, c_ in cnt.items():
            sw = (c_ >= 4) & (reg != lbl) & land_ok & ~town() & ~np.isin(reg, passes) & (reg != NP) & (reg >= 0) & (reg < NL + NN)
            reg[sw] = lbl; n_sw += int(sw.sum())
        if not n_sw: break
    # stray pieces cut off by the carve: to the neighbour sharing most border (pieces that were separate before stay)
    touched = changed | set(int(x) for x in np.unique(reg0[reg0 != reg]))
    orig_stray = np.zeros((h, w), bool)
    for i in touched - changed - {NP, -1}:
        for comp in components((reg0 == i) & land_ok):
            if not any(f["slot"][r_, c_] >= 0 for c_, r_ in comp):
                for c_, r_ in comp: orig_stray[r_, c_] = True
    for it in range(8):
        mv = 0
        for i in touched - {NP, -1}:
            comps = components((reg == i) & land_ok)
            if len(comps) <= 1: continue
            for comp in comps:
                if any(f["slot"][r_, c_] >= 0 for c_, r_ in comp) or all(orig_stray[r_, c_] for c_, r_ in comp): continue
                cntn = collections.Counter()
                for c_, r_ in comp:
                    for k in range(6):
                        nc_, nr_ = neighbour(c_, r_, k)
                        if 0 <= nc_ < w and 0 <= nr_ < h and land_ok[nr_, nc_] and reg[nr_, nc_] != i: cntn[int(reg[nr_, nc_])] += 1
                tgt = cntn.most_common(1)[0][0] if cntn else NP
                for c_, r_ in comp: reg[r_, c_] = tgt
                if tgt == NP:
                    for c_, r_ in comp: f["imp"][r_, c_] = 1
                mv += len(comp)
        if not mv: break
    for i in sorted(changed):
        a_ = int(((reg == i) & land_ok).sum())
        if a_ < MIN_NEW: log(f"  size: {names_all[i]} only {a_} hexes")

    # ---------------- 4. valley bridges: every changed town on the main passable land ------------------------------
    mean_ = smooth_noise((h, w), 6, 24); mean_ = (mean_ - mean_.min()) / (np.ptp(mean_) + 1e-9)
    ccost2 = 1.0 + SLOPE_COST * slope + 4.0 * mountain + 1.5 * mean_
    for it_ in range(30):
        passable = walk_mask(f) & (reg != NP) & (reg >= 0)
        comps_ = components(passable); main_ = max(comps_, key=len); mm = np.zeros((h, w), bool)
        for c_, r_ in main_: mm[r_, c_] = True
        cut_ = [(k, st_) for k, st_ in placed.items() if not mm[st_[1], st_[0]] and (k in rid or names.index(k) in moved_ids)]
        cut_ = [(k, st_) for k, st_ in cut_ if not any(terr[st_[1] + dy, st_[0]] == 1 for dy in (0,))]
        if not cut_: break
        cands_ = []
        for k, st_ in cut_:
            path_ = route(st_, mm, (terr == 0), np.zeros((h, w), np.int64), ccost2, hh, w, h)   # mountains cost, not forbidden
            if path_ and len(path_) <= 120: cands_.append((len(path_), k, path_))
        if not cands_:
            for k, _ in cut_: log(f"  ! no valley bridge (<= 120 hexes) for {k}")
            break
        _, k, path_ = min(cands_)
        i = rid.get(k, names.index(k) if k in names else None)
        pm = np.zeros((h, w), bool)
        for x, y in path_: pm[y, x] = True
        pm = grow(pm, NA, 2) & (terr == 0) & ~town()
        newland = pm & ((reg == NP) | (reg < 0))
        reg[newland] = i; f["imp"][pm & (np.isin(reg, list(changed)) | newland)] = 0
        log(f"  valley bridge {k}: {len(path_)} hexes, {int(newland.sum())} new hexes")

    # ---------------- 5. roads -------------------------------------------------------------------------------------
    road = f["road"]; tm = town()
    base_cost = 1.0 + np.where(f["imp"] == 1, 6.0, 0) + np.where(f["river"] > 0, 3.0, 0) + 3.0 * slope + 2.5 * noise
    net = np.zeros((h, w), bool)
    for comp in components(((road > 0) | (f["bridge"] > 0) | tm) & (terr != 1) | (f["bridge"] > 0)):
        ids_ = {int(reg[r_, c_]) for c_, r_ in comp if f["slot"][r_, c_] == 0}
        if ids_ - changed:
            for c_, r_ in comp: net[r_, c_] = True
    prov_cap = {pv["key"]: pv["capital"] for pv in ex["provinces"]}
    town_prov = {t["key"]: t["province_key"] for t in ex["towns"]}
    order = sorted(sites, key=lambda s: s[1] != "capital")
    for t, kind, c, r, fp, off in order:
        key = t["key"]; i = rid.get(key, names.index(key) if key in names else None)
        own = (reg == i) & (f["slot"] >= 0)
        cap_key = prov_cap.get(town_prov.get(key))
        cap_id = None
        if kind != "capital" and cap_key and cap_key != key:
            cap_id = rid.get(cap_key, names.index(cap_key) if cap_key in names else None)
        tgt = net & (reg != i) if cap_id is None else ((reg == cap_id) & (f["slot"] == 0))
        okm = ((terr == 0) | own | tgt) & ~(tm & ~own & ~tgt) & (reg != NP)
        path = route((c, r), tgt, okm, road, base_cost, hh, w, h)
        if cap_id is not None and (path is None or len(path) > 3 * max(1, hdist((c, r), placed.get(cap_key, (c, r)))) + 10):
            tgt2 = net & (reg != i); ok2 = ((terr == 0) | own | tgt2) & ~(tm & ~own & ~tgt2) & (reg != NP)
            p2 = route((c, r), tgt2, ok2, road, base_cost, hh, w, h)
            if p2 is not None and (path is None or len(p2) < len(path)): path = p2
        if path is None: log(f"  ! no road for {key}"); continue
        for (x0, y0), (x1, y1) in zip(path, path[1:]):
            for k in range(6):
                if neighbour(x0, y0, k) == (x1, y1): road[y0, x0] |= 1 << k; road[y1, x1] |= 1 << ((k + 3) % 6)
            f["imp"][y0, x0] = 0; f["imp"][y1, x1] = 0
        for x, y in path: net[y, x] = True
        net |= own | ((reg == i) & (f["sprawl"] == 1))
    # dead-end spurs at the vacated sites of moved towns
    front = set()
    for k_, s_ in old_site.items():
        if not s_: continue
        for yy in range(max(0, s_[1] - 4), min(h, s_[1] + 5)):
            for xx in range(max(0, s_[0] - 4), min(w, s_[0] + 5)):
                if road[yy, xx]: front.add((xx, yy))
    pruned = 0
    while front:
        x, y = front.pop()
        if not road[y, x] or f["slot"][y, x] >= 0 or f["sprawl"][y, x] or f["bridge"][y, x]: continue
        live = []
        for k in range(6):
            if not (road[y, x] >> k) & 1: continue
            nx_, ny_ = neighbour(x, y, k)
            if 0 <= nx_ < w and 0 <= ny_ < h and (road[ny_, nx_] >> ((k + 3) % 6)) & 1: live.append((k, nx_, ny_))
        if len(live) <= 1:
            road[y, x] = 0; pruned += 1
            for k, nx_, ny_ in live: road[ny_, nx_] &= ~(1 << ((k + 3) % 6)); front.add((nx_, ny_))
    # roads on non-playable land (desert / ranges / opened land left unclaimed) are removed
    dead = (reg == NP) & (road > 0) & (reg0 != NP); road[dead] = 0
    log(f"roads: {len(order)} towns routed; {pruned} dead-end hexes pruned at vacated sites")

    # ---------------- 6. opened-land fields; cut-off pockets impassable ---------------------------------------------
    conv = (op | free) & np.isin(reg, list(changed))
    gidx = {n: k for k, n in enumerate(L["ground_types"])}
    gr = np.array([gidx.get(GROUND_BY_BLEND.get(b, "plains"), gidx["plains"]) for b in range(32)])
    f["ground"][conv] = gr[hb[conv]]
    play_pass = land_ok & (reg != NP) & ~conv & (f["imp"] == 0) & (reg >= 0)
    srcp = {(int(x), int(y)): int(y) * w + int(x) for y, x in np.argwhere(play_pass)}
    _, near = dijkstra(srcp, np.ones((h, w)), land_ok, w, h)
    ny_, nx_ = np.divmod(near[conv], w)
    for k in ("climate", "attr", "aoi", "restr", "b9"): f[k][conv] = f[k][ny_, nx_]
    cut = 0
    for i in changed:
        for comp in components((reg == i) & land_ok & (f["imp"] == 0)):
            if not any(f["slot"][r_, c_] >= 0 for c_, r_ in comp):
                for c_, r_ in comp:
                    if road[r_, c_] == 0: f["imp"][r_, c_] = 1; cut += 1
    log(f"opened land fields {int(conv.sum())} hexes; {cut} cut-off pocket hexes impassable")

    # ---------------- 7. write -------------------------------------------------------------------------------------
    redge = np.zeros((h, w), np.int32)
    for k, (nr, nc, v) in enumerate(NA): redge |= ((v & (reg[nr, nc] != reg)).astype(np.int32) << k)
    f["redge"] = redge
    fix_bridge_banks(f, names_all, NL + NN, w, h, log)
    out = pack(f); out[..., 10:15] = g[..., 10:15]
    prefix = replace_region_lists(src[:P], land + [s[0]["key"] for s in new_list], sea_names)
    body = prefix + struct.pack("<II", w, h) + out.tobytes()
    OUT.write_bytes(body + struct.pack("<I", zlib.crc32(body) & 0xFFFFFFFF))
    # regions_new.json for regions_db.py: provinces with their NEW regions; renames / province moves / owners
    provinces = {}
    keyset = {s[0]["key"] for s in new_list}
    for pv in ex["provinces"]:
        newr = [k for k in pv["members"] if k in keyset]
        if not newr: continue
        is_new = pv.get("is_new", False)
        regs = ([pv["capital"]] if pv["capital"] in newr else []) + [k for k in newr if k != pv["capital"]]
        tmap = {s[0]["key"]: s for s in new_list}
        provinces[pv["key"]] = dict(group=tmap[regs[0]][0].get("group", "central"), label=pv["label"], zhou=pv.get("zhou"),
                                   province=pv["key"], attach=not (is_new and pv["capital"] in newr),
                                   regions=regs, names={k: tmap[k][0]["name"] for k in regs},
                                   towns={k: [tmap[k][2], tmap[k][3]] for k in regs},
                                   hexes={k: int((reg == rid[k]).sum()) for k in regs},
                                   owners={k: tmap[k][0].get("owner") for k in regs}, capital=pv["capital"],
                                   importance={k: tmap[k][0].get("importance") for k in regs})
    json.dump(dict(provinces=provinces, moved={k: dict(site=list(placed[k]), old_site=old_site.get(k)) for k in moved_keys if k in placed},
                   dropped=dropped, renames=ex.get("renames", {}), province_moves=ex.get("existing_province_changes", {}),
                   province_renames=ex.get("province_renames", {}),
                   all_provinces=[dict(key=pv["key"], capital=pv["capital"], members=pv["members"], label=pv["label"], zhou=pv.get("zhou"))
                                  for pv in ex["provinces"]],
                   new_provinces=[dict(key=pv["key"], label=pv["label"], zhou=pv.get("zhou")) for pv in ex["provinces"] if pv.get("is_new")]),
              open(HERE / "regions_new.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    log(f"wrote {OUT}: {NL + NN} land regions (+{NN}), {len(sea_names)} sea; regions_new.json {len(provinces)} provinces")
    if preview:
        from regions_carve import draw_preview
        centres = {}
        for i in range(NL + NN):
            m_ = (reg == i) & (f["slot"] == 0)
            if m_.any():
                pts = np.argwhere(m_); r_, c_ = pts[np.argmin(((pts - pts.mean(0)) ** 2).sum(1))]; centres[i] = (int(c_), int(r_))
        draw_preview(reg, f, changed, centres, w, h, preview, box=(0, w, 0, h))
    return dropped


if __name__ == "__main__":
    main()
