#!/usr/bin/env python3
"""Carve the new main190 regions into map.hex. Input hex/map_korea.hex (korea_fix.py), output hex/map.hex +
regions_new.json (the region/province list for the DB step, regions_db.py).

Provinces (seat lat/lon -> hex via regions_plan.py's georef + warp + local correction):
  ironic_central_*: Central Plains commanderies carved out of the stretched 190E regions
  ironic_hexi_*:    Hexi corridor west of 190E's Hanyang (= Zhangye) on the new DEM land
  ironic_nomad_*:   the steppe north of 190E's playable edge (190E's non-playable frame + the new north land)
Each province: a capital (190E capital footprint: 19-hex slot 0 + sprawl) + resource towns (7-hex slot 0 + sprawl).

1. placement: best centre within SEARCH hexes of the seat: footprint on plain land of an eligible donor, no
   existing town within MIN_GAP, fewest rough hexes (impassable / river / coast / mountain) within 2 of it
2. territory: multi-source Dijkstra from every town; a hex goes to a new region if its nearest town is new and
   it is eligible (central: playable land outside towns; hexi/nomad: non-playable land inside ZONES)
3. clean-up: every region is one piece holding its town; stray pieces go to the neighbour sharing the most
   border (old pieces back to old regions where possible)
4. new land (hexi/nomad): impassable = DEM mountains (class_fill blend 4-7), ground type from the blend class,
   climate copied from the nearest playable hex; passable pockets cut off from the town are made impassable
5. roads: each new town is routed (terrain-aware Dijkstra, as korea_fix.py) to the existing road network, and
   resources also to their capital; road hexes are passable
6. region lists: new land regions appended (sea indices shift up); region edges recomputed; crc32 trailer
"""
import sys, json, heapq, struct, zlib
from collections import deque
from pathlib import Path
import numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent, HERE.parent.parent / "output" / "pylibs"): sys.path.insert(0, str(p))
import tifffile
import crop_scale_map_hex as C, hexmap
from rebuild_hex import unpack, pack, replace_region_lists
from hexgrid import neighbour, neighbour_arrays, centre, to_cube, from_cube
from regions_plan import predict, plan as seat_plan
from terrain_main import FULL, NWW, NWH

SRC = HERE / "hex" / "map_korea.hex"; OUT = HERE / "hex" / "map.hex"
# key: (group, seat, lat, lon, resources)
PROVINCES = {
    "chenliu": ("central", "Chenliu", 34.80, 114.35, 1), "liang": ("central", "Suiyang", 34.43, 115.63, 1),
    "pei": ("central", "Xiang", 33.93, 116.77, 1), "jiyin": ("central", "Dingtao", 35.07, 115.57, 1),
    "shanyang": ("central", "Changyi", 35.10, 116.28, 1), "lu": ("central", "Lu", 35.60, 116.99, 1),
    "dongping": ("central", "Wuyan", 35.93, 116.47, 1), "hongnong": ("central", "Hongnong", 34.52, 110.87, 1),
    "juyan": ("hexi", "Juyan", 41.90, 101.10, 1), "jiuquan": ("hexi", "Lufu", 39.73, 98.50, 1),
    "dunhuang": ("hexi", "Dunhuang", 40.14, 94.66, 1),
    "yunzhong": ("nomad", "Yunzhong", 40.28, 111.20, 2), "dingxiang": ("nomad", "Shanwu", 40.20, 112.50, 2),
    "danhan": ("nomad", "Danhan", 41.55, 113.50, 2), "shanggu": ("nomad", "Juyong", 40.43, 115.97, 2),
    "liaoxi": ("nomad", "Yangle", 41.52, 121.25, 2),
    # Hebei plain around Ye (user, 2026-09-29): Han commanderies missing from 190E's large Jizhou regions
    "zhao": ("central", "Handan", 36.61, 114.49, 1), "julu": ("central", "Yingtao", 37.45, 115.10, 1),
    "changshan": ("central", "Yuanshi", 37.77, 114.52, 1), "hejian": ("central", "Lecheng", 38.18, 116.10, 1),
    "qinghe": ("central", "Ganling", 36.85, 115.80, 1),
}
TEMPLATES = {"capital": "3k_main_xihe_capital", "resource": "3k_main_anding_resource_3"}
SEARCH = {"central": 14, "hexi": 24, "nomad": 30}
# spacing: no new town within one army turn of another (user, 2026-09-29: 20 walking steps; straight hex distance
# bounds the walk from below, so a straight gap of 20 guarantees it)
MIN_GAP = {"capital": 20, "resource": 20}
RES_DIST = {"central": (20, 30), "hexi": (20, 45), "nomad": (20, 45)}   # resource town distance from its capital
GAP_WEIGHT = {"central": (0.5, 40), "hexi": (1.5, 60), "nomad": (1.5, 60)}  # (weight, cap): spread towns over open land
# hexi/nomad territory: all non-playable land in these boxes (hex cols c0..c1, rows r0..r1) is shared out among
# the new towns (Voronoi); a frame of non-playable land stays along the map edges
ZONES = {"band": (3, 960, 640, 815), "yinshan": (400, 960, 600, 815)}
NON_PLAYABLE = "3k_main_reg_non_playable"
MOUNTAIN_BLEND = (4, 5, 6, 7)
GROUND_BY_BLEND = {0: "desert", 3: "desert", 19: "grassland", 20: "grassland", 21: "grassland", 22: "grassland",
                   27: "light_forest", 4: "mountain", 5: "mountain", 6: "mountain", 7: "mountain"}


def hdist(a, b):
    aq, ar, as_ = to_cube(*a); bq, br, bs = to_cube(*b); return max(abs(aq - bq), abs(ar - br), abs(as_ - bs))


def template(f, names, key):
    """Footprint of a 190E town as cube offsets from its slot-0 centre: [(dq, dr, slot, sprawl)]."""
    m = f["region"] == names.index(key)
    s0 = np.argwhere(m & (f["slot"] == 0)); r, c = s0[np.argmin(((s0 - s0.mean(0)) ** 2).sum(1))]
    cq, cr, _ = to_cube(int(c), int(r))
    out = []
    for rr, cc in np.argwhere(m & ((f["slot"] >= 0) | (f["sprawl"] == 1))):
        q, r_, _ = to_cube(int(cc), int(rr)); out.append((q - cq, r_ - cr, int(f["slot"][rr, cc]), int(f["sprawl"][rr, cc])))
    return out


def place_fp(tpl, c, r):
    cq, cr, _ = to_cube(c, r)
    return [(*from_cube(cq + dq, cr + dr), s, sp) for dq, dr, s, sp in tpl]


def dijkstra(sources, cost, allowed, w, h, limit=None):
    """Multi-source Dijkstra over the hex grid. sources: {(c, r): label}; cost[r, c] = cost of stepping into (c, r).
    Returns (dist, label) arrays; unreached = inf / -1."""
    dist = np.full((h, w), np.inf); lab = np.full((h, w), -1, np.int64); pq = []
    for (c, r), l in sources.items():
        dist[r, c] = 0; lab[r, c] = l; pq.append((0.0, c, r))
    heapq.heapify(pq)
    while pq:
        d, c, r = heapq.heappop(pq)
        if d > dist[r, c]: continue
        for k in range(6):
            nc, nr = neighbour(c, r, k)
            if not (0 <= nc < w and 0 <= nr < h) or not allowed[nr, nc]: continue
            nd = d + cost[nr, nc]
            if limit is not None and nd > limit: continue
            if nd < dist[nr, nc]:
                dist[nr, nc] = nd; lab[nr, nc] = lab[r, c]; heapq.heappush(pq, (nd, nc, nr))
    return dist, lab


def components(mask):
    h, w = mask.shape; seen = np.zeros_like(mask); out = []
    for r0, c0 in zip(*np.nonzero(mask)):
        if seen[r0, c0]: continue
        comp, q = [], deque([(c0, r0)]); seen[r0, c0] = True
        while q:
            c, r = q.popleft(); comp.append((c, r))
            for k in range(6):
                nc, nr = neighbour(c, r, k)
                if 0 <= nc < w and 0 <= nr < h and mask[nr, nc] and not seen[nr, nc]:
                    seen[nr, nc] = True; q.append((nc, nr))
        out.append(comp)
    return out


def hex_blend_and_height(w, h):
    """Per hex: majority blend class of 9 samples around the centre, and the height at the centre."""
    blend = np.array(Image.open(HERE / "terrain" / "3k_dlc07_main_map.blend.191fd8068da8020.tif"))
    H = tifffile.imread(str(HERE / "terrain" / "3k_dlc07_main_map.height.191fd803c1a801d.tif"))
    rr, cc = np.mgrid[0:h, 0:w]; x, z = centre(cc, rr)
    px = np.clip((x / NWW * FULL[0]).astype(int), 0, FULL[0] - 1); py = np.clip(((1 - z / NWH) * FULL[1]).astype(int), 0, FULL[1] - 1)
    votes = np.zeros((h, w, 32), np.int16)
    for dy in (-3, 0, 3):
        for dx in (-3, 0, 3):
            b = blend[np.clip(py + dy, 0, FULL[1] - 1), np.clip(px + dx, 0, FULL[0] - 1)].astype(np.int64)
            votes[rr, cc, np.clip(b, 0, 31)] += 1
    return votes.argmax(-1), H[py, px].astype(np.float32)


def cube_arr(pts):
    a = np.array(pts, np.int64); q = a[:, 0]; r = -a[:, 1] - (a[:, 0] + (a[:, 0] & 1)) // 2
    return np.stack([q, r, -q - r], 1)


def route(start, tgt, ok, road, base_cost, hh, w, h):
    """Cheapest path from start to any tgt hex (korea_fix-style costs; existing road is cheap). None if unreachable."""
    sc, sr = start; dist = {start: 0.0}; prev = {}; pq = [(0.0, sc, sr)]
    while pq:
        d, c, r = heapq.heappop(pq)
        if d > dist.get((c, r), 1e18): continue
        if tgt[r, c]:
            path = [(c, r)]
            while path[-1] != start: path.append(prev[path[-1]])
            return path
        for k in range(6):
            nc, nr = neighbour(c, r, k)
            if not (0 <= nc < w and 0 <= nr < h) or not ok[nr, nc]: continue
            step = (0.35 if road[nr, nc] else base_cost[nr, nc]) + abs(hh[nr, nc] - hh[r, c]) / 600.0
            if d + step < dist.get((nc, nr), 1e18):
                dist[(nc, nr)] = d + step; prev[(nc, nr)] = (c, r); heapq.heappush(pq, (d + step, nc, nr))
    return None


def main(log=print, drop=(), out_hex=None, out_json=None, preview=None):
    """drop: new region names to leave out (towns that found no site in a previous pass). Returns the names of
    towns that found no site in this pass (a province whose capital has no site loses all its towns)."""
    unplaced = []
    src = SRC.read_bytes(); P, w, h = C.locate_dims(src)
    g = np.frombuffer(src, np.uint8, 16 * w * h, P + 8).reshape(h, w, 16).copy()
    f = unpack(g); f["redge"] = (g[..., 15].astype(np.int32) >> 2) & 63
    L = hexmap.load(str(SRC))["lists"]; land, sea_names = L["land_regions"], L["sea_regions"]; NL = len(land)
    names = land + sea_names; NP = names.index(NON_PLAYABLE)
    hb, hh = hex_blend_and_height(w, h)
    mountain = np.isin(hb, MOUNTAIN_BLEND)
    terr, reg = f["terr"], f["region"]
    tpl = {k: template(f, names, v) for k, v in TEMPLATES.items()}
    import regions_plan
    regions_plan.NEW = {k: v[:4] for k, v in PROVINCES.items()}
    seats, _, _ = seat_plan(f, names, w, h)

    # new region ids: land regions appended, sea indices shifted up
    new_regions, provinces = [], {}
    for key, (grp, seat, lat, lon, nres) in PROVINCES.items():
        rs = [f"ironic_{grp}_{key}_capital"] + [f"ironic_{grp}_{key}_resource_{i}" for i in range(1, nres + 1)]
        rs = [n for n in rs if n not in drop]
        if not rs or rs[0] != f"ironic_{grp}_{key}_capital": continue          # capital dropped: whole province
        provinces[key] = dict(group=grp, seat=seat, lat=lat, lon=lon, province=f"3k_ironic_province_{key}", regions=rs)
        new_regions += rs
    NN = len(new_regions)
    reg[reg >= NL] += NN
    rid = {n: NL + i for i, n in enumerate(new_regions)}
    grp_of = {rid[n]: provinces[k]["group"] for k in provinces for n in provinces[k]["regions"]}
    new_ids = set(rid.values())

    excluded = [i for i, n in enumerate(land) if n.endswith("_pass") or n.startswith("ironic_region_")]
    def town_mask(): return (f["slot"] >= 0) | (f["sprawl"] == 1)
    def eligible(grp):
        base = (terr == 0) & ~town_mask()
        if grp == "central":
            return base & (reg >= 0) & (reg < NL) & (reg != NP) & ~np.isin(reg, excluded)
        m = base & (reg == NP); m[:3, :] = False; m[-3:, :] = False; m[:, :3] = False; m[:, -3:] = False
        return m
    rough = {"central": (f["imp"] == 1) | (f["river"] > 0) | (terr == 2) | (terr == 3),
             "north": mountain | (f["river"] > 0) | (terr == 2) | (terr == 3)}

    centres = {}
    for i in range(NL):
        m = (reg == i) & (f["slot"] == 0)
        if m.any():
            pts = np.argwhere(m); r, c = pts[np.argmin(((pts - pts.mean(0)) ** 2).sum(1))]; centres[i] = (int(c), int(r))

    def sprawl_ok(fp):
        """CAIME town-sprawl rule: obstacles (impassable / beach / cliff / river) around the footprint form at most one
        area touching it, and none comes within 2 hexes without touching. (Clearing impassable around a town instead
        split mountain massifs into several areas touching it - CAIME rejects that too.)"""
        fps = {(x, y) for x, y, _, _ in fp}
        def ring(src, excl):
            out = set()
            for x, y in src:
                for k1 in range(6):
                    n = neighbour(x, y, k1)
                    if n not in excl and 0 <= n[0] < w and 0 <= n[1] < h: out.add(n)
            return out
        r1 = ring(fps, fps); r2 = ring(r1, fps | r1); r3 = ring(r2, fps | r1 | r2)
        def obst(x, y, ring1):
            return f["river"][y, x] > 0 or terr[y, x] in (2, 3) or f["imp"][y, x] == 1
        ob = {n for n in r1 if obst(*n, True)} | {n for n in r2 | r3 if obst(*n, False)}
        if not ob: return True
        comps, seen = [], set()
        for n in ob:
            if n in seen: continue
            comp, st = set(), [n]; seen.add(n)
            while st:
                a = st.pop(); comp.add(a)
                for k1 in range(6):
                    b = neighbour(*a, k1)
                    if b in ob and b not in seen: seen.add(b); st.append(b)
            comps.append(comp)
        touching = [c_ for c_ in comps if c_ & r1]
        if len(touching) > 1: return False
        return not any((c_ & r2) and not (c_ & r1) for c_ in comps)

    def best_site(grp, kind, anchor, lo, hi, max_rough=None):
        el = eligible(grp); rg = rough["central" if grp == "central" else "north"]
        cen = cube_arr(list(centres.values())); best = None; ac, ar = anchor
        for r in range(max(0, ar - hi - 1), min(h, ar + hi + 2)):
            for c in range(max(0, ac - hi - 1), min(w, ac + hi + 2)):
                dd = hdist((c, r), anchor)
                if dd < lo or dd > hi or not el[r, c]: continue
                gap = int(np.abs(cen - cube_arr([(c, r)])).max(1).min())
                if gap < MIN_GAP[kind]: continue
                fp = place_fp(tpl[kind], c, r)
                if any(not (0 <= x < w and 0 <= y < h) or not el[y, x] or (s >= 0 and f["river"][y, x]) for x, y, s, _ in fp):
                    continue
                if not sprawl_ok(fp): continue
                ring = set()
                for x, y, _, _ in fp:
                    for k1 in range(6):
                        a1 = neighbour(x, y, k1); ring.add(a1)
                        for k2 in range(6): ring.add(neighbour(*a1, k2))
                nr_ = sum(1 for x, y in ring if 0 <= x < w and 0 <= y < h and rg[y, x])
                if max_rough is not None and nr_ > max_rough: continue
                gw, gcap = GAP_WEIGHT[grp]
                score = -3.0 * nr_ + gw * min(gap, gcap) - (0.4 * dd if kind == "capital" else 0)
                if best is None or score > best[0]: best = (score, c, r, nr_, gap)
        return best

    placed = {}
    for key, pinfo in provinces.items():
        grp = pinfo["group"]; _, _, sc, sr = seats[key]; towns = []
        for j, rname in enumerate(pinfo["regions"]):
            kind = "capital" if j == 0 else "resource"
            if kind == "capital":
                b = (best_site(grp, kind, (sc, sr), 0, SEARCH[grp], 0) or best_site(grp, kind, (sc, sr), 0, SEARCH[grp])
                     or best_site(grp, kind, (sc, sr), 0, SEARCH[grp] + 14))
            else:
                lo, hi = RES_DIST[grp]
                b = (best_site(grp, kind, towns[0], lo, hi, 0) or best_site(grp, kind, towns[0], lo, hi)
                     or best_site(grp, kind, towns[0], lo - 3, hi + 6))
            if b is None:
                log(f"  ! no site for {rname}")
                if kind == "capital": unplaced += pinfo["regions"]; break
                unplaced.append(rname); continue
            _, c, r, nr_, gap = b
            for x, y, s, sp in place_fp(tpl[kind], c, r):
                reg[y, x] = rid[rname]; f["slot"][y, x] = s; f["sprawl"][y, x] = sp; f["imp"][y, x] = 0
            centres[rid[rname]] = (c, r); towns.append((c, r)); placed[rname] = (c, r)
            if False:                      # (old: clear impassable within 2 hexes - sprawl_ok now rejects such sites)
                fp = {(x, y) for x, y, _, _ in place_fp(tpl[kind], c, r)}
                adj = {neighbour(x, y, k1) for x, y in fp for k1 in range(6)} - fp
                ring2 = {neighbour(x, y, k1) for x, y in adj for k1 in range(6)} - fp - adj
                cleared = [(x, y) for x, y in ring2 if 0 <= x < w and 0 <= y < h and f["imp"][y, x] == 1]
                for x, y in cleared: f["imp"][y, x] = 0
                if cleared: log(f"    cleared {len(cleared)} impassable hexes 2 out from {rname}")
            log(f"  {rname:36s} at ({c},{r}) seat-dist {hdist((c, r), (sc, sr)):3d} rough-near {nr_:3d} gap {gap}")
        pinfo["towns"] = {n: placed[n] for n in pinfo["regions"] if n in placed}
    if unplaced:
        return unplaced                     # caller re-runs with these dropped (clean region lists, no empty regions)

    # --- territory ---
    land_ok = terr != 1
    reg0 = reg.copy()
    src_c = {}
    for i in centres:
        if i in new_ids and grp_of[i] != "central": continue
        for y, x in np.argwhere((reg == i) & (f["slot"] == 0)): src_c[(int(x), int(y))] = i
    _, lab = dijkstra(src_c, np.where(f["imp"] == 1, 2.5, 1.0), land_ok & (reg != NP), w, h)
    take = eligible("central") & np.isin(lab, [i for i in new_ids if grp_of[i] == "central"])
    reg[take] = lab[take]; log(f"central territory: {int(take.sum())} hexes")
    src_n = {}
    for i in new_ids:
        if grp_of[i] == "central" or i not in centres: continue
        for y, x in np.argwhere((reg == i) & (f["slot"] == 0)): src_n[(int(x), int(y))] = i
    zone = np.zeros((h, w), bool)
    for c0, c1, r0, r1 in ZONES.values(): zone[r0:r1 + 1, c0:c1 + 1] = True
    _, lab = dijkstra(src_n, np.where(mountain, 2.5, 1.0), land_ok & zone & ((reg == NP) | np.isin(reg, list(src_n.values()))), w, h)
    take_n = eligible("nomad") & zone & (lab >= 0)
    reg[take_n] = lab[take_n]; log(f"hexi/nomad territory: {int(take_n.sum())} hexes")
    converted = take_n.copy()

    # --- clean-up: pieces cut off by the carve go to a neighbour. Only regions the carve touched, and never a piece
    # that was already separate before it (islands of Kuaiji, Tongan, ...) ---
    touched = set(new_ids) | set(np.unique(reg0[reg0 != reg]).tolist())
    orig_stray = np.zeros((h, w), bool)
    for i in touched - set(new_ids) - {NP, -1}:
        for comp in components((reg0 == i) & land_ok):
            if not any(f["slot"][r, c] >= 0 for c, r in comp):
                for c, r in comp: orig_stray[r, c] = True
    for it in range(8):
        moved = 0
        for i in touched - {NP, -1}:
            comps = components((reg == i) & land_ok)
            if len(comps) <= 1: continue
            for comp in comps:
                if any(f["slot"][r, c] >= 0 for c, r in comp): continue
                if all(orig_stray[r, c] for c, r in comp): continue
                cnt = {}
                for c, r in comp:
                    for k in range(6):
                        nc, nr = neighbour(c, r, k)
                        if 0 <= nc < w and 0 <= nr < h and land_ok[nr, nc] and reg[nr, nc] != i:
                            cnt[int(reg[nr, nc])] = cnt.get(int(reg[nr, nc]), 0) + 1
                tgt = max(cnt, key=cnt.get) if cnt else NP
                for c, r in comp: reg[r, c] = tgt
                moved += len(comp)
        if not moved: break
        log(f"  clean-up pass {it}: {moved} stray hexes reassigned")
    north_ids = [i for i in new_ids if grp_of[i] != "central"]
    converted &= np.isin(reg, north_ids)

    # --- new land fields ---
    town = town_mask()
    gidx = {n: i for i, n in enumerate(L["ground_types"])}
    f["imp"][converted] = (mountain & ~town)[converted].astype(f["imp"].dtype)
    gr = np.array([gidx.get(GROUND_BY_BLEND.get(b, "plains"), gidx["plains"]) for b in range(32)])
    f["ground"][converted] = gr[hb[converted]]
    play_pass = land_ok & (reg != NP) & ~converted & (f["imp"] == 0) & (reg >= 0)
    srcs = {(int(x), int(y)): int(y) * w + int(x) for y, x in np.argwhere(play_pass)}
    _, near = dijkstra(srcs, np.ones((h, w)), land_ok, w, h)
    ny, nx = np.divmod(near[converted], w)
    for k in ("climate", "attr", "aoi", "restr", "b9"): f[k][converted] = f[k][ny, nx]

    # --- roads ---
    road = f["road"]
    base_cost = 1.0 + np.where(f["imp"] == 1, 6.0, 0) + np.where(f["river"] > 0, 3.0, 0)
    for key, pinfo in provinces.items():
        towns = pinfo["towns"]; cap = pinfo["regions"][0]
        for rname, start in towns.items():
            own = (reg == rid[rname]) & (f["slot"] >= 0)
            if rname == cap:
                sibs = [rid[n] for n in towns if n != cap]
                tgt = ((road > 0) | (f["slot"] == 0)) & (reg != rid[rname]) & ~np.isin(reg, sibs) & (reg != NP) & (terr == 0)
            else:
                tgt = (reg == rid[cap]) & (f["slot"] == 0)
            ok = ((terr == 0) | own) & ~(town & ~own & ~tgt)
            path = route(start, tgt, ok, road, base_cost, hh, w, h)
            if rname != cap and (path is None or len(path) > 3 * hdist(start, towns[cap]) + 10):
                # the capital is only reachable the long way round (a river between them): join the road network
                tgt = (road > 0) & (reg != rid[rname]) & (reg != NP) & (terr == 0)
                ok = ((terr == 0) | own) & ~(town & ~own & ~tgt)
                p2 = route(start, tgt, ok, road, base_cost, hh, w, h)
                if p2 is not None and (path is None or len(p2) < len(path)): path = p2
            if path is None: log(f"  ! no road for {rname}"); continue
            for (c0, r0), (c1, r1) in zip(path, path[1:]):
                for k in range(6):
                    if neighbour(c0, r0, k) == (c1, r1): road[r0, c0] |= 1 << k; road[r1, c1] |= 1 << ((k + 3) % 6)
                f["imp"][r0, c0] = 0; f["imp"][r1, c1] = 0
            log(f"  road {rname}: {len(path)} hexes to {'the network' if rname == cap else 'its capital'}")
    # passable pockets of new land cut off from the region's town (and road) become impassable
    cut = 0
    for i in north_ids:
        for comp in components((reg == i) & land_ok & (f["imp"] == 0)):
            if not any(f["slot"][r, c] >= 0 for c, r in comp):
                for c, r in comp:
                    if f["road"][r, c] == 0: f["imp"][r, c] = 1; cut += 1     # roads stay passable (CAIME roads rule)
    log(f"new land: {int(converted.sum())} hexes, {int((converted & (f['imp'] == 1)).sum())} impassable ({cut} cut-off pocket hexes)")

    # --- write ---
    NA = neighbour_arrays(h, w)
    redge = np.zeros((h, w), np.int32)
    for k, (nr, nc, v) in enumerate(NA): redge |= ((v & (reg[nr, nc] != reg)).astype(np.int32) << k)
    f["redge"] = redge
    out = pack(f); out[..., 10:15] = g[..., 10:15]
    prefix = replace_region_lists(src[:P], land + new_regions, sea_names)
    body = prefix + struct.pack("<II", w, h) + out.tobytes()
    (out_hex or OUT).write_bytes(body + struct.pack("<I", zlib.crc32(body) & 0xFFFFFFFF))
    for k in provinces:
        provinces[k]["hexes"] = {n: int((reg == rid[n]).sum()) for n in provinces[k]["regions"]}
        provinces[k]["towns"] = {n: list(v) for n, v in provinces[k]["towns"].items()}
    provinces = {k: p for k, p in provinces.items() if p["towns"]}
    json.dump(provinces, open(out_json or HERE / "regions_new.json", "w"), indent=1)
    log(f"wrote {out_hex or OUT}: {NL + NN} land regions (+{NN}), {len(sea_names)} sea")
    if preview: draw_preview(reg, f, new_ids, centres, w, h, preview)
    for k, p in provinces.items(): log(f"  {p['province']:32s} {p['hexes']}")


def draw_preview(reg, f, new_ids, centres, w, h, path, box=(300, 900, 380, 760)):
    """Regions in muted colours, new regions bright, town centres as dots, region edges dark; north up.
    box = hex cols c0..c1, rows r0..r1 (Central Plains + Hebei by default)."""
    from PIL import ImageDraw
    c0, c1, r0, r1 = box; S = 3
    rng = np.random.default_rng(7); pal = rng.integers(60, 200, (reg.max() + 2, 3)).astype(np.uint8)
    for i in new_ids: pal[i] = rng.integers(0, 256, 3).astype(np.uint8) | np.array([128, 0, 0], np.uint8)
    sub = reg[r0:r1, c0:c1]; img = pal[np.clip(sub, 0, None)]
    img[f["terr"][r0:r1, c0:c1] == 1] = (40, 70, 120); img[sub < 0] = 0
    edge = np.zeros(sub.shape, bool); edge[:, 1:] |= sub[:, 1:] != sub[:, :-1]; edge[1:] |= sub[1:] != sub[:-1]
    img[edge] = (20, 20, 20)
    im = Image.fromarray(img[::-1]).resize(((c1 - c0) * S, (r1 - r0) * S), Image.NEAREST); d = ImageDraw.Draw(im)
    for i, (c, r) in centres.items():
        if not (c0 <= c < c1 and r0 <= r < r1): continue
        x, y = (c - c0) * S, (r1 - 1 - r) * S; rad = 6 if i in new_ids else 4
        d.ellipse([x - rad, y - rad, x + rad, y + rad], fill=(255, 255, 255) if i in new_ids else (0, 0, 0), outline=(0, 0, 0))
    im.save(path)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    kw = dict(out_hex=HERE / "hex" / "map_dryrun.hex", out_json=HERE / "regions_new_dryrun.json",
              preview=HERE / "previews" / "carve_preview.png") if a.dry_run else dict(preview=HERE / "previews" / "carve_final.png")
    (HERE / "previews").mkdir(exist_ok=True)
    drop = []
    while True:
        miss = main(drop=tuple(drop), **kw)
        if not miss: break
        print("no site for:", miss, "- re-running without them"); drop += miss
    if drop: print("DROPPED (no room at the 20-step spacing):", drop)
