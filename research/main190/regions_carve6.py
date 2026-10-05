#!/usr/bin/env python3
"""Round 6 region placement on the north x1.4 map (user's rules, 2026-09-30). Input hex/map_korea.hex (korea_fix),
output hex/map.hex + regions_new.json + previews/carve6.png.

Rules (user):
  * no town within 20 walking steps (BFS over passable land / bridges) of another town
  * capital and resource of a province form one connected area (islands exempt, cf. Hepu)
  * towns not in mountains or props (impassable, mountain blend classes 4-7, within ~2 hexes x scale of mountain /
    rock props from the AK layers), CAIME sprawl rule
  * natural borders: territory grows by Dijkstra over a cost field with smooth noise (no straight bisectors); small
    rivers are expensive to cross so borders settle on them; big rivers are sea hexes (not crossed); boundary
    majority smoothing afterwards
  * gate passes never carved; every new / moved town gets a road to the network (resource: to its capital, or the
    network when the capital is only reachable the long way round)
  * Hexi: 190E's squeezed Hexi towns move to their real seats (research_r6: Dunhuang was 503 km off, Jiuquan 289, ...);
    their territory is new corridor land; the Liang zone (DEM terrain since dem_fill round 6) gets DEM passability
Candidates: research_r6/candidates.json (core first, then optional; capital before resources). A town that finds
no site is dropped (its province too if it is the capital) and listed in the log.
"""
import os, sys, json, heapq, struct, zlib, collections, glob, re
from pathlib import Path
import numpy as np
from PIL import Image
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent, HERE.parent.parent / "output" / "pylibs"): sys.path.insert(0, str(p))
import crop_scale_map_hex as C, hexmap
from rebuild_hex import unpack, pack, replace_region_lists
from hexgrid import neighbour, neighbour_arrays, centre, nearest_hex, to_cube, from_cube
from regions_carve import template, place_fp, dijkstra, components, hex_blend_and_height, route, hdist, MOUNTAIN_BLEND, GROUND_BY_BLEND
from warp import current, WarpMapping
from class_fill import smooth_noise
import rubber
from dem_fill import liang_weight

SRC = HERE / "hex" / "map_korea.hex"; OUT = HERE / "hex" / "map.hex"
CAND = HERE / "research_r6" / "candidates.json"
TEMPLATES = {"capital": "3k_main_xihe_capital", "resource": "3k_main_anding_resource_3"}
NON_PLAYABLE = "3k_main_reg_non_playable"
BLOCK_MAX = 0.2              # user: max share of prop / impassable hexes around a site (radius ~4); water is fine
GAP = 20                     # walking steps from a new / moved town to any town (user); region size is enforced separately
SEARCH = 30                  # hexes around the geographic position
RES_RANGE = (24, 60)         # resource town walking steps from its capital (vanilla p10..p90, research_r6)
RES_TARGET = 37              # vanilla median
HEXI_BOX = (0, 440, 560, 890)            # round 8 (east-lean warp): new-hex cols c0..c1, rows r0..r1: corridor land for the moved Hexi regions
HEXI_REACH = 42.0                        # (unused since the corridor mask)
LINKS = [("ironic_region_xi_capital", "ironic_region_xi_resource_1")]   # Zhangye -> Juyan along the Ruoshui
# territory cost (vanilla rules, research_r6/vanilla_regions.py): borders run on ridges (46% of vanilla border
# length) and rivers (26%), regions stretch along valleys; light noise only breaks ties (no straight bisectors)
NOISE_AMP = 1.6; RIVER_COST = 8.0; IMP_COST = 3.0; SLOPE_COST = 6.0
MIN_AREA, MAX_AREA = 550, 1850                          # vanilla p10..p90 region size (hexes)
NOMAD_MAX = 2800                                        # tribal regions: vanilla's largest
MIN_NEW = 420                                           # size-rule floor for new regions (vanilla p5 444; 12 vanilla regions < 450)
MAX_FRONTIER = 4800        # moved Hexi regions: northern regions are ~2x vanilla after the x1.4 scale (Wuwei ~4000 hexes)
HEAD_START = 10.0            # territory: existing towns start this much cost behind new / moved ones - the northern
                             # regions are ~2x vanilla area after the x1.4 scale, so new regions take a vanilla-size share                                     # vanilla's largest regions (Anding, Nanhai ...): moved Hexi regions
KEY_GROUP = {"Southern Xiongnu": "nomad", "Yunzhong": "nomad", "Yunzhong Xianbei": "nomad", "Danhan Xianbei": "nomad", "Wuhuan": "nomad", "Yuanquan": "hexi", "Yumen": "hexi", "Jianshui": "hexi", "Huishui": "hexi"}


def dijkstra_hs(sources, head, cost, allowed, w, h):
    """multi-source Dijkstra with a start cost per label (additively weighted territories)."""
    dist = np.full((h, w), np.inf); lab = np.full((h, w), -1, np.int64); pq = []
    for (c, r), l in sources.items():
        d0 = head.get(l, 0.0)
        if d0 < dist[r, c]: dist[r, c] = d0; lab[r, c] = l; pq.append((d0, c, r))
    heapq.heapify(pq)
    while pq:
        d, c, r = heapq.heappop(pq)
        if d > dist[r, c]: continue
        for k in range(6):
            nc, nr = neighbour(c, r, k)
            if not (0 <= nc < w and 0 <= nr < h) or not allowed[nr, nc]: continue
            nd = d + cost[nr, nc]
            if nd < dist[nr, nc]:
                dist[nr, nc] = nd; lab[nr, nc] = lab[r, c]; heapq.heappush(pq, (nd, nc, nr))
    return dist, lab


def walk_mask(f):
    return ((f["terr"] != 1) | (f["bridge"] > 0)) & (f["imp"] == 0)


def fix_bridge_banks(f, names, n_land, w, h, log=print):
    terr, reg = f["terr"], f["region"]
    br = (f["bridge"] > 0) & (terr == 1); seen = np.zeros_like(br); fixed = bad = 0
    def nbrs(c, r):
        for k in range(6):
            q = neighbour(c, r, k)
            if 0 <= q[0] < w and 0 <= q[1] < h: yield q
    for r0, c0 in zip(*np.nonzero(br)):
        if seen[r0, c0]: continue
        comp = [(int(c0), int(r0))]; seen[r0, c0] = True; i = 0
        while i < len(comp):
            for q in nbrs(*comp[i]):
                if br[q[1], q[0]] and not seen[q[1], q[0]]: seen[q[1], q[0]] = True; comp.append(q)
            i += 1
        for _ in range(3):
            shore = {q for c, r in comp for q in nbrs(c, r) if terr[q[1], q[0]] != 1}
            groups, left = [], set(shore)
            while left:
                g_ = {left.pop()}; st = list(g_)
                while st:
                    for q in nbrs(*st.pop()):
                        if q in left: left.discard(q); g_.add(q); st.append(q)
                groups.append(g_)
            if len(groups) <= 2: break
            gid = {q: k for k, g_ in enumerate(groups) for q in g_}
            # water (non-bridge) hexes next to the bridge touching 2+ shore groups: joining them merges those groups
            cands = [q for c, r in comp for q in nbrs(c, r) if terr[q[1], q[0]] == 1 and not br[q[1], q[0]]
                     and len({gid[n] for n in nbrs(*q) if n in gid}) >= 2]
            if not cands: break
            c, r = cands[0]
            land_n = [n for n in nbrs(c, r) if terr[n[1], n[0]] != 1 and 0 <= reg[n[1], n[0]] < n_land]
            if not land_n: break
            src = land_n[0]
            terr[r, c] = 2; reg[r, c] = collections.Counter(int(reg[n[1], n[0]]) for n in land_n).most_common(1)[0][0]
            for k in ("ground", "climate", "attr", "aoi", "restr"): f[k][r, c] = f[k][src[1], src[0]]
            f["imp"][r, c] = 0; f["river"][r, c] = 0; fixed += 1
            log(f"  bridge bank fix: water hex ({c},{r}) -> beach of {names[reg[r, c]]} (bridge at {comp[0]})")
        if len(groups) > 2: bad += 1; log(f"  ! bridge at {comp[0]} still has {len(groups)} shores")
    log(f"bridge banks: {fixed} hexes joined, {bad} bridges still not 2-banked")


def multi_bfs(sources, walk, NA, maxd=70):
    h, w = walk.shape; dist = np.full((h, w), np.inf); q = collections.deque()
    for r, c in sources:
        dist[r, c] = 0; q.append((r, c))
    while q:
        r, c = q.popleft(); d = dist[r, c]
        if d >= maxd: continue
        for nr, nc, v in NA:
            if not v[r, c]: continue
            a, b = int(nr[r, c]), int(nc[r, c])
            if dist[a, b] <= d + 1 or not walk[a, b]: continue
            dist[a, b] = d + 1; q.append((a, b))
    return dist


def prop_mask(w, h):
    """hexes within ~2 x scale of mountain / rock props (AK layers written by ak_main.py, new-map positions)."""
    m = np.zeros((h, w), bool); ENT = re.compile(r"<entity [^>]*>.*?</entity>", re.S); n = 0
    for lp in glob.glob(str(HERE / "ak" / "3k_dlc07_main_map" / "*.layer")):
        t = open(lp, encoding="utf-8", errors="ignore").read()
        if "/mountains/" not in t and "rocks/general" not in t: continue
        for e in ENT.findall(t):
            if "/mountains/" not in e and "rocks/general" not in e: continue
            mm = re.search(r'<ECTransform position="([^ "]+) [^ "]+ ([^ "]+)"[^>]*scale="([^ "]+)', e)
            if not mm: continue
            x, z, sc = float(mm.group(1)), float(mm.group(2)), abs(float(mm.group(3)))
            c, r = nearest_hex(np.array([x]), np.array([z]), w, h); c, r = int(c[0]), int(r[0]); rad = int(round(2 * max(1.0, sc)))
            m[max(0, r - rad):r + rad + 1, max(0, c - rad):c + rad + 1] = True; n += 1
    return m, n


def main(log=print, preview=HERE / "previews" / "carve6.png", res_override=None, search_override=None, no_res=None, skip=None):
    res_override = res_override or {}; search_override = search_override or {}; no_res = no_res or set(); skip = skip or set()
    src = SRC.read_bytes(); P, w, h = C.locate_dims(src)
    g = np.frombuffer(src, np.uint8, 16 * w * h, P + 8).reshape(h, w, 16).copy()
    f = unpack(g); f["redge"] = (g[..., 15].astype(np.int32) >> 2) & 63
    L = hexmap.load(str(SRC))["lists"]; land, sea_names = L["land_regions"], L["sea_regions"]; NL = len(land)
    names = land + sea_names; NP = names.index(NON_PLAYABLE)
    NA = neighbour_arrays(h, w); W = WarpMapping(current())
    terr, reg = f["terr"], f["region"]
    hb, hh = hex_blend_and_height(w, h); mountain = np.isin(hb, MOUNTAIN_BLEND)
    # local slope per hex (max height step to a neighbour), 0..1 at the 95th percentile
    slope = np.zeros((h, w), np.float32)
    for nr, nc, v in NA: slope = np.maximum(slope, np.where(v, np.abs(hh[nr, nc] - hh), 0))
    slope = np.clip(slope / max(1.0, float(np.percentile(slope[terr != 1], 95))), 0, 1)
    props, nprops = prop_mask(w, h)
    tpl = {k: template(f, names, v) for k, v in TEMPLATES.items()}
    cand = json.load(open(CAND, encoding="utf-8"))
    if os.environ.get("TERRAIN_ONLY"):          # round 8: terrain check - lakes / north cull / Liang passability only
        cand = dict(cand, provinces=[], relocate=[], move_r7=[])
    passes = [i for i, n in enumerate(land) if n.endswith("_pass")]
    rr, cc = np.mgrid[0:h, 0:w]; X, Z = centre(cc, rr); OX, OZ = W.inv_world(X, Z)
    liang = (liang_weight(OX, OZ) > 0.5) & (reg >= 0) & (reg < NL) & (reg != NP)
    town = lambda: (f["slot"] >= 0) | (f["sprawl"] == 1)
    # ---- Hexi lakes (user's Liang map): Dunhuang, Yuanquan and the Juyan lakes become lake hexes of 3k_main_sea_lake
    from PIL import ImageDraw
    lake_id = names.index("3k_main_sea_lake"); n_lake = 0; lake_all = np.zeros((h, w), bool)
    for nm_, poly in json.load(open(HERE / "research_r6" / "hexi_lakes.json", encoding="utf-8")).items():
        if nm_.startswith("_"): continue
        vs = []
        for la_, lo_ in poly:
            ox_, oz_ = rubber.to_world(la_, lo_); nx_, nz_ = W.fwd_world(float(ox_), float(oz_))
            c_, r_ = nearest_hex(np.array([nx_]), np.array([nz_]), w, h); vs.append((int(c_[0]), int(r_[0])))
        im_ = Image.new("1", (w, h), 0); ImageDraw.Draw(im_).polygon(vs, fill=1, outline=1)
        inside = np.array(im_, bool)
        lk_ = inside & (f["slot"] < 0) & (f["sprawl"] == 0)
        terr[lk_] = 1; reg[lk_] = lake_id; f["imp"][lk_] = 1; f["ground"][lk_] = 18
        for k_ in ("road", "river", "bridge", "trade", "restr", "b9"): f[k_][lk_] = 0
        f["attr"][lk_] = -1; f["aoi"][lk_] = -1; n_lake += int(lk_.sum()); lake_all |= lk_
        log(f"  lake {nm_}: {int(lk_.sum())} hexes")
    log(f"grid {w}x{h}; {NL} land regions; props {nprops} ({props.mean():.1%} hexes); mountains {mountain.mean():.1%}; Liang zone {liang.sum()} hexes")

    def geo_hex(lat, lon):
        ox, oz = rubber.to_world(lat, lon); nx, nz = W.fwd_world(float(ox), float(oz))
        c, r = nearest_hex(np.array([nx]), np.array([nz]), w, h); return int(c[0]), int(r[0])

    def sprawl_ok(fp):
        fps = {(x, y) for x, y, _, _ in fp}
        def ring(src_, excl):
            out = set()
            for x, y in src_:
                for k1 in range(6):
                    q = neighbour(x, y, k1)
                    if q not in excl and 0 <= q[0] < w and 0 <= q[1] < h: out.add(q)
            return out
        r1 = ring(fps, fps); r2 = ring(r1, fps | r1); r3 = ring(r2, fps | r1 | r2)
        ob = {q for q in r1 | r2 | r3 if f["river"][q[1], q[0]] > 0 or terr[q[1], q[0]] in (2, 3) or f["imp"][q[1], q[0]] == 1}
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

    # ---------------- 1. Hexi: DEM passability in the Liang zone, move 190E's Hexi towns to their real seats ----------
    f["imp"][liang & ~town() & (f["road"] == 0)] = mountain[liang & ~town() & (f["road"] == 0)].astype(f["imp"].dtype)
    log(f"Liang zone passability from the DEM: {int((liang & mountain).sum())} impassable of {int(liang.sum())}")
    # ---- north cull (user, core tribes): mountains on real lowland become passable; land opened for the tribes
    import north_cull; NCM = north_cull.apply_hex(f, names, reg, terr, NA, log, mountain=mountain); mountain = NCM["mountain_after"]
    moved = {}
    free = np.zeros((h, w), bool)                                # hexes to hand out again (old territory of moved regions)
    for rel in cand.get("relocate", []):
        for k, (lat, lon) in rel["regions"].items():
            key = k.split(" ")[0]; i = names.index(key); kind = "capital" if key.endswith("_capital") else "resource"
            old = reg == i; free |= old; sl_ = np.argwhere(old & (f["slot"] == 0))
            f["slot"][old] = -1; f["sprawl"][old] = 0
            moved[i] = dict(key=key, kind=kind, geo=geo_hex(lat, lon), lat=lat, lon=lon, old_site=[int(sl_[0][1]), int(sl_[0][0])] if len(sl_) else None)
    gen_moved = {}                                               # round 7: existing towns moved onto their real seats
    for mv_ in cand.get("move_r7", []):
        key = mv_["key"]; i = names.index(key); kind = "capital" if key.endswith("_capital") else "resource"
        old = reg == i; sl_ = np.argwhere(old & (f["slot"] == 0))
        gen_moved[i] = dict(key=key, kind=kind, geo=geo_hex(mv_["lat"], mv_["lon"]), lat=mv_["lat"], lon=mv_["lon"],
                            river_clear=mv_.get("river_clear", 0), old_site=[int(sl_[0][1]), int(sl_[0][0])] if len(sl_) else None,
                            old_fp=[(int(x), int(y), int(f["slot"][y, x]), int(f["sprawl"][y, x])) for y, x in np.argwhere(old & ((f["slot"] >= 0) | (f["sprawl"] == 1)))])
        free |= old; f["slot"][old] = -1; f["sprawl"][old] = 0
    # the freed territory becomes plain playable land again (region decided by the territory step)
    c0, c1, r0_, r1_ = HEXI_BOX
    hexi_zone = np.zeros((h, w), bool); hexi_zone[r0_:r1_ + 1, c0:c1 + 1] = True
    padland = (reg == NP) & (terr == 0) & hexi_zone
    # DEM passability for the corridor land (non-playable padding) the moved towns will take
    f["imp"][padland] = mountain[padland].astype(f["imp"].dtype)

    # ---------------- 2. sites -----------------------------------------------------------------------------------
    walk = walk_mask(f)
    ok_site = (terr == 0) & ~mountain & ~props & (f["imp"] == 0) & ~np.isin(reg, passes) & ~town()
    # user: no blocks of props or impassable tiles around a new / moved town - share of blocked hexes within ~4 hexes
    blk = (props | ((f["imp"] == 1) & (terr != 1))).astype(np.float32)
    for _ in range(4):
        acc = blk.copy(); cnt = np.ones_like(blk)
        for nr, nc, v in NA: acc += np.where(v, blk[nr, nc], 0); cnt += v
        blk = acc / cnt
    ok_site &= blk < BLOCK_MAX
    big_river = (terr == 1) & np.isin(reg, [i for i, n in enumerate(names) if "riv_sea" in n])
    river_d = multi_bfs([tuple(x) for x in np.argwhere(big_river)], np.ones((h, w), bool), NA, maxd=12)
    towns_now = [(int(r), int(c)) for r, c in zip(*np.nonzero((f["slot"] == 0) & (reg >= 0) & (reg < NL) & ~free))]
    dist = multi_bfs(towns_now, walk, NA)
    placed = {}                                                 # region name -> (c, r)
    new_regions, provinces, dropped = [], {}, []

    def find_site(kind, c0_, r0_, allowed, capd=None, search=SEARCH, rrange=RES_RANGE, cap_at=None, cap_geo=None):
        best = []
        # a resource keeps its real side of the capital (within 90 degrees): Zou stays south of Qufu, ...
        want = None
        if cap_at is not None and cap_geo is not None and (c0_, r0_) != cap_geo:
            # the REAL bearing capital seat -> resource seat (not from the capital's placed site, which may have drifted)
            want = np.array([(c0_ - cap_geo[0]) * 0.668, (r0_ - cap_geo[1]) * 0.772]); want /= np.linalg.norm(want)
        for r in range(max(0, r0_ - search), min(h, r0_ + search + 1)):
            for c in range(max(0, c0_ - search), min(w, c0_ + search + 1)):
                if not allowed[r, c] or dist[r, c] < GAP: continue
                if capd is not None and not (rrange[0] <= capd[r, c] <= rrange[1]): continue
                if want is not None:
                    v_ = np.array([(c - cap_at[0]) * 0.668, (r - cap_at[1]) * 0.772]); nv = np.linalg.norm(v_)
                    if nv > 0 and float(v_ @ want) / nv < 0.0: continue     # the correct half-plane
                g_ = np.hypot((c - c0_) * 0.668, (r - r0_) * 0.772) / 0.72          # hexes from the real seat
                sc_ = g_ + 12.0 * slope[r, c]                                       # flat ground (vanilla towns sit in valleys / plains)
                if capd is not None: sc_ += 0.5 * abs(capd[r, c] - RES_TARGET)      # capital-resource ~ vanilla median
                best.append((sc_, c, r))
        for _, c, r in sorted(best):
            fp = place_fp(tpl[kind], c, r)
            if any(not (0 <= x < w and 0 <= y < h) or not allowed[y, x] or (s_ >= 0 and f["river"][y, x]) for x, y, s_, _ in fp): continue
            if not sprawl_ok(fp): continue
            if np.hypot((c - c0_) * 0.668, (r - r0_) * 0.772) / 0.72 > 6: why_far(c0_, r0_, allowed)
            return c, r, fp
        why_far(c0_, r0_, allowed)
        return None

    def why_far(c0_, r0_, allowed, rad=6):
        # diagnostics: why the hexes within rad of the real seat were rejected
        cnt = collections.Counter()
        for r in range(max(0, r0_ - rad), min(h, r0_ + rad + 1)):
            for c in range(max(0, c0_ - rad), min(w, c0_ + rad + 1)):
                if terr[r, c] == 1: cnt["water"] += 1
                elif town()[r, c]: cnt["town"] += 1
                elif dist[r, c] < GAP: cnt["gap<20"] += 1
                elif props[r, c]: cnt["prop"] += 1
                elif mountain[r, c]: cnt["mountain"] += 1
                elif f["imp"][r, c]: cnt["impassable"] += 1
                elif blk[r, c] >= BLOCK_MAX: cnt["block>20%"] += 1
                elif not allowed[r, c]: cnt["other region/zone"] += 1
                else: cnt["ok(fp/sprawl/range)"] += 1
        log(f"    near ({c0_},{r0_}): {dict(cnt)}")

    def stamp(i, kind, c, r, fp):
        for x, y, s_, sp in fp:
            reg[y, x] = i; f["slot"][y, x] = s_; f["sprawl"][y, x] = sp; f["imp"][y, x] = 0
        d2 = multi_bfs([(r, c)], walk_mask(f), NA)
        return d2

    # moved Hexi towns: sites in the corridor land (padding) or the freed land
    # ---- the Hexi corridor as playable land: the steppe / oasis band along the Qilian front (class_fill paints it),
    #      grown 3 hexes; the cheapest-terrain route Zhangye -> Juyan (the Ruoshui valley), widened; Juyan's own oasis.
    #      Everything else in the padding stays non-playable (round 6: no regions floating in the desert).
    def grow(m_, k):
        for _ in range(k):
            g_ = m_.copy()
            for nr, nc, v in NA: g_ |= v & m_[nr, nc]
            m_ = g_
        return m_
    steppe = np.isin(hb, (19, 20, 21, 22))
    corridor = padland & ~mountain & grow(steppe & padland, 3)
    geo_of = {m["key"]: m["geo"] for m in moved.values()}
    ccost = 1.0 + SLOPE_COST * slope + 4.0 * mountain
    band0 = corridor.copy()
    for a_, b_ in LINKS:
        if b_ in geo_of:                                        # the outpost (Juyan) -> nearest corridor land
            path_ = route(geo_of[b_], band0 | ((reg >= 0) & (reg != NP) & (terr == 0) & ~free), (terr == 0) & hexi_zone & ~mountain,
                          np.zeros((h, w), np.int64), ccost, hh, w, h)
            log(f"  link {b_}: {len(path_) if path_ else 'NO PATH'} hexes to the corridor")
            if path_:
                pm = np.zeros((h, w), bool)
                for x, y in path_: pm[y, x] = True
                corridor |= grow(pm, 3) & padland & ~mountain
    wob = smooth_noise((h, w), 4, 23)                              # natural (noisy) disk round each moved town
    for m in moved.values():
        c_, r_ = m["geo"]; d_ = np.hypot((cc - c_) * 0.668, (rr - r_) * 0.772) / 0.72
        rad_ = 12 if m["key"] == "ironic_region_xi_resource_1" else 8       # Juyan: the whole oasis / lake basin
        corridor |= (d_ < rad_ + 3 * wob) & padland & ~mountain
    # user's outline (2026-09-30): the Hexi playable land extends north to take in Juyan - a contiguous block from the
    # Jiuquan / Dunhuang border round Juyan to the land north of Rile (research_r6/hexi_extension_hexes.npy, traced from
    # the user's drawing). Mountains inside stay impassable but belong to the regions.
    ext = np.zeros((h, w), bool)
    EXT = HERE / "research_r6" / "hexi_extension_hexes.npy"
    if EXT.exists():
        e_ = np.load(EXT); ok_ = (e_[:, 0] >= 0) & (e_[:, 0] < w) & (e_[:, 1] >= 0) & (e_[:, 1] < h)
        ext[e_[ok_, 1], e_[ok_, 0]] = True
    # and the same for Dunhuang (user, 2026-09-30: "same for Dunhuang"): the Shule basin round Dunhuang / Yumen /
    # Yangguan, from the Qilian front north to the Beishan hills (~41.2N), west to ~93.6E, east to Jiuquan's land -
    # a noisy natural edge in real lat / lon
    lonh, lath = rubber.to_lonlat(OX, OZ)
    nz_ = smooth_noise((h, w), 8, 27)
    dun = (lath < 41.2 + 0.25 * nz_) & (lonh > 93.6 + 0.2 * nz_) & (lonh < 99.2) & (cc > 8 + 4 * nz_)   # off the map edge
    ext |= dun & hexi_zone
    ext |= grow(lake_all, 6) & (smooth_noise((h, w), 5, 29) > -0.4) & hexi_zone      # the lake shores are playable
    ext &= padland
    # mountains belong to the block only near its flat land (the border follows the range, not a latitude line)
    flat_ = ext & ~mountain
    ext &= ~mountain | (grow(flat_, 5) & (smooth_noise((h, w), 4, 28) > -0.3))
    corridor |= ext
    log(f"Hexi corridor land: {int(corridor.sum())} hexes (user outline {int(ext.sum())})")
    allowed_hexi = (corridor | (free & (terr == 0))) & ~props & hexi_zone
    for i, m in sorted(moved.items(), key=lambda kv: kv[1]["kind"] != "capital"):
        res = find_site(m["kind"], *m["geo"], allowed_hexi)
        if res is None: log(f"  ! no corridor site for {m['key']} (stays where it was)"); continue
        c, r, fp = res
        dist = np.minimum(dist, stamp(i, m["kind"], c, r, fp)); placed[m["key"]] = (c, r)
        log(f"  moved {m['key']:36s} -> ({c},{r}) {hdist((c, r), m['geo'])} hexes from its real seat")
    allowed_gen = ok_site & (((reg >= 0) & (reg < NL) & (reg != NP)) | (free & (terr == 0))) & ~padland
    for i, m in sorted(gen_moved.items(), key=lambda kv: kv[1]["kind"] != "capital"):
        al_ = allowed_gen & (river_d >= m["river_clear"]) if m["river_clear"] else allowed_gen
        res = find_site(m["kind"], *m["geo"], al_)
        if res is None:                                          # no site: the town stays where it was
            for x, y, s_, sp in m["old_fp"]: f["slot"][y, x] = s_; f["sprawl"][y, x] = sp
            log(f"  ! no site for {m['key']} near its real seat - stays"); continue
        c, r, fp = res
        dist = np.minimum(dist, stamp(i, m["kind"], c, r, fp)); placed[m["key"]] = (c, r); m["placed"] = True
        log(f"  moved {m['key']:36s} -> ({c},{r}) {hdist((c, r), m['geo'])} hexes from its real seat (was {m['old_site']})")
    gen_ids = {i for i, m in gen_moved.items() if m.get("placed")}
    walk = walk_mask(f)

    # new provinces
    order = sorted(cand["provinces"], key=lambda p: {"must": 0, "core": 1}.get(p["tier"], 2))
    junc = {}                                                   # region -> province (pack junctions, 190E + vanilla)
    for line in open(HERE / "source" / "db" / "region_to_province_junctions_tables" / "data__.tsv", encoding="utf-8"):
        a_ = line.rstrip(chr(10)).split(chr(9))
        if len(a_) >= 2 and not a_[0].startswith(("#", "province")): junc[a_[1]] = a_[0]
    for p in order:
        grp = KEY_GROUP.get(p["label"], "central"); key = p["key"]
        rs, seat_c, seat_geo = [], None, None
        for t in p["towns"]:
            kind = t[3]; c0_, r0_ = geo_hex(t[1], t[2])
            nm = (f"ironic_{grp}_{key}_capital" if kind == "capital" else f"ironic_{grp}_{key}_resource_{len(rs)}") if not p.get("attach") else f"ironic_{grp}_{key}"
            attach = p.get("attach", False)                      # a single region joining the province it lands in
            if kind != "capital" and seat_c is None and not attach: break
            if kind != "capital" and key in no_res: continue           # retries could not connect it: no resource
            if (p["label"], t[0]) in skip:                              # dropped by the size rule in an earlier attempt
                dropped.append(f"{p['label']}: {t[0]} ({kind}, size rule)")
                if kind == "capital": break
                continue
            allowed = ok_site & (((reg >= 0) & (reg < NL) & (reg != NP) & ~free) | (free & (terr == 0) & ~padland))   # r7: vacated sites reusable
            if grp == "nomad": allowed = ok_site & (NCM["open_nomad"] | ((reg >= 0) & (reg < NL) & (reg != NP)))
            if grp == "hexi": allowed = allowed_hexi & ok_site                # the corridor land of the moved Hexi regions
            capd = multi_bfs([seat_c[::-1]], walk, NA, maxd=RES_RANGE[1] + 2) if kind != "capital" and not attach else None
            if capd is not None: capd = np.where(np.isfinite(capd), capd, 1e9)
            res = find_site(kind, c0_, r0_, allowed, capd, search_override.get(key, SEARCH), res_override.get(key, tuple(p.get("res_range", RES_RANGE))),
                            cap_at=seat_c if kind != "capital" and not attach else None, cap_geo=seat_geo)
            if res is None:
                dropped.append(f"{p['label']}: {t[0]} ({kind})")
                if kind == "capital": break
                continue
            c, r, fp = res
            i = NL + len(new_regions) + len(rs)
            rs.append((nm, t[0], kind, c, r, fp, hdist((c, r), (c0_, r0_))))
            if kind == "capital": seat_c = (c, r); seat_geo = (c0_, r0_)
            dist = np.minimum(dist, multi_bfs([(r, c)], walk, NA))
            for x, y, _, _ in fp: dist[y, x] = 0
        if not rs: continue
        # vanilla: provinces have 2-4 regions, never 1. A core commandery whose resource has no site joins the
        # province it lands in as one region (like Guandu); an optional one is left out.
        if len(rs) == 1 and not p.get("attach") and not p.get("members"):
            if p["tier"] in ("must", "core"):
                nm0 = f"ironic_{grp}_{key}"; c_, r_ = rs[0][3], rs[0][4]
                rs[0] = (nm0, rs[0][1], "resource", c_, r_, place_fp(tpl["resource"], c_, r_), rs[0][6]); p = dict(p, attach=True)
                log(f"  {p['label']}: no resource site - {rs[0][1]} joins the province it lands in")
            else:
                dropped.append(f"{p['label']}: province (single region)"); log(f"  {p['label']}: single region - left out"); continue
        prov_key = f"3k_ironic_province_{key}"
        if p.get("attach"):  # region joins the province it lands in
            prov_key = p.get("province") or junc.get(names[reg[rs[0][4], rs[0][3]]], ""); log(f"  {rs[0][0]} joins existing province {prov_key}")
        provinces[key] = dict(group=grp, label=p["label"], zhou=p["zhou"], seat=rs[0][1], province=prov_key, attach=bool(p.get("attach")),
                              members=p.get("members", []),
                              regions=[x[0] for x in rs], names={x[0]: x[1] for x in rs}, why=p["why"], tier=p["tier"],
                              towns={x[0]: [x[3], x[4]] for x in rs}, geo_offset={x[0]: x[6] for x in rs})
        for x in rs: new_regions.append(x)
    NN = len(new_regions)
    reg[reg >= NL] += NN                                          # sea ids shift up
    rid = {x[0]: NL + k for k, x in enumerate(new_regions)}
    for nm, _, kind, c, r, fp, off in new_regions:
        stamp(rid[nm], kind, c, r, fp); log(f"  {nm:40s} at ({c},{r}) {off} hexes from its real seat")
    new_ids = set(rid.values()); moved_ids = set(moved)
    hexi_new = {rid[x[0]] for x in new_regions if x[0].startswith("ironic_hexi_")}   # new towns on the corridor land
    log(f"placed {NN} new towns in {len(provinces)} provinces; dropped: {dropped or 'none'}")

    reg0 = reg.copy()                                           # before territory: for the island rule in clean-up
    # ---------------- 3. territory: noisy Dijkstra from every town -------------------------------------------------
    # two octaves: broad wander (10 hexes) + fine jag (3 hexes) - vanilla borders are irregular at both scales
    # three octaves: 30-hex wander (long borders across flat desert / plain don't run straight), 10-hex bends, 3-hex jag
    noise = 0.4 * smooth_noise((h, w), 30, 26) + 0.35 * smooth_noise((h, w), 10, 21) + 0.25 * smooth_noise((h, w), 3, 22)
    noise = (noise - noise.min()) / (np.ptp(noise) + 1e-9)
    small_river = (f["river"] > 0) & (terr != 1)
    cost = 1.0 + NOISE_AMP * noise + RIVER_COST * small_river + IMP_COST * (f["imp"] == 1) + SLOPE_COST * slope
    land_ok = terr != 1
    playable = land_ok & (reg >= 0) & (reg != NP) & ~np.isin(reg, passes)
    srcs = {}
    for i in range(NL + NN):
        m = (reg == i) & (f["slot"] == 0)
        for y, x in np.argwhere(m): srcs[(int(x), int(y))] = i
    nomad_ids = {rid[x[0]] for x in new_regions if x[0].startswith("ironic_nomad_")}
    area = playable | padland | NCM["open_nomad"]
    head = {i: HEAD_START for i in set(srcs.values()) if i not in new_ids and i not in moved_ids and i not in gen_ids}
    dlab, lab = dijkstra_hs(srcs, head, cost, area, w, h)
    take = (lab >= 0) & ~town() & (np.isin(lab, list(new_ids | gen_ids)) & playable & ~free | free & land_ok
                                    | np.isin(lab, list(nomad_ids)) & NCM["open_nomad"])
    reg[take] = lab[take]
    # nomad size cap (vanilla max ~2800): trim opened land farthest from the town back to non-playable
    for i in nomad_ids:
        op = np.argwhere((reg == i) & NCM["open_nomad"] & ~town())
        extra = int(((reg == i) & land_ok).sum()) - NOMAD_MAX
        if extra > 0 and len(op):
            nz_ = 14.0 * smooth_noise((h, w), 12, 51) + 5.0 * smooth_noise((h, w), 4, 52)      # ragged edge, not a circle
            op = op[np.argsort(-(dlab[op[:, 0], op[:, 1]] + nz_[op[:, 0], op[:, 1]]))][:extra]; reg[op[:, 0], op[:, 1]] = NP
    rest = NCM["open_nomad"] & ~np.isin(reg, list(nomad_ids)) & (reg == NP); f["imp"][rest] = 1
    own_ = NCM["open_nomad"] & np.isin(reg, list(nomad_ids)) & ~town(); f["imp"][own_] = NCM["mountain_after"][own_].astype(f["imp"].dtype)
    log(f"nomad land: {int(own_.sum())} opened hexes to {len(nomad_ids)} tribal regions")
    # the corridor: moved Hexi regions divide the corridor land (terrain cost, no reach limit)
    hexi_ids = moved_ids | hexi_new
    hsrc = {k: v for k, v in srcs.items() if v in hexi_ids}
    if hsrc:
        n20 = smooth_noise((h, w), 20, 37); n20 = (n20 - n20.min()) / (np.ptp(n20) + 1e-9)
        hcost = cost + 6.0 * n20                                        # flat desert: strong wander, no straight bisectors
        dh, lh = dijkstra(hsrc, hcost, corridor | (np.isin(reg, list(hexi_ids)) & land_ok), w, h)
        sdist, _ = dijkstra({(int(x), int(y)): 0 for y, x in np.argwhere(steppe & corridor)}, np.ones((h, w)), land_ok, w, h)
        # domain warp: over flat desert the cost split is a near-straight bisector; sample each hex's label from a point
        # displaced by smooth noise (up to ~15 hexes, 30-hex wavelength) so borders meander like vanilla ones
        yy_, xx_ = np.mgrid[0:h, 0:w]
        dx_ = 20 * smooth_noise((h, w), 30, 41) + 4 * smooth_noise((h, w), 8, 43)
        dy_ = 20 * smooth_noise((h, w), 30, 42) + 4 * smooth_noise((h, w), 8, 44)
        sy_ = np.clip(np.rint(yy_ + dy_).astype(int), 0, h - 1); sx_ = np.clip(np.rint(xx_ + dx_).astype(int), 0, w - 1)
        lw_ = lh[sy_, sx_]; okw_ = (lh >= 0) & (lw_ >= 0) & corridor[sy_, sx_]
        lh = np.where(okw_, lw_, lh)
        th = (lh >= 0) & corridor & ~town(); reg[th] = lh[th]
        # vanilla size cap: each moved region keeps its cheapest (corridor floor) padding hexes up to MAX_AREA
        for i in moved_ids:
            mine = (reg == i) & land_ok; own_old = mine & ~padland
            room = MAX_FRONTIER - int(own_old.sum())
            pads = np.argwhere(mine & padland & ~ext)                     # never trim inside the user's outline
            if len(pads) > max(0, room):
                order_ = np.argsort(sdist[pads[:, 0], pads[:, 1]] + 0.01 * dh[pads[:, 0], pads[:, 1]])   # keep the band, trim the fringe
                for y, x in pads[order_[max(0, room):]]:
                    if f["slot"][y, x] < 0 and f["sprawl"][y, x] == 0: reg[y, x] = NP; f["imp"][y, x] = 1
        th = th & np.isin(reg, list(hexi_ids))
        f["imp"][th] = mountain[th].astype(f["imp"].dtype)                  # corridor land: passable but mountains
        rest = padland & ~np.isin(reg, list(hexi_ids)); f["imp"][rest] = 1   # the rest stays non-playable, impassable
        log(f"corridor land: {int(th.sum())} hexes to the moved Hexi regions")
        # the old 190E map edge runs straight through the corridor: re-divide a band along it with strongly noisy
        # cost (20-hex wander) so the border there meanders like a vanilla one
        old_edge = padland & grow(land_ok & ~padland, 1)            # includes land freed by the moved regions
        fixed_ = town() | np.isin(reg, passes) | (reg == NP) | (reg < 0) | ~land_ok
        band = (grow(old_edge, 10) | grow(free & land_ok, 2)) & ~fixed_       # + the freed land: 190E's old straight borders
        ring = grow(band, 1) & ~band & ~fixed_
        bcost = 1.0 + 6.0 * (smooth_noise((h, w), 20, 31) - smooth_noise((h, w), 20, 31).min()) + SLOPE_COST * slope
        tw_ = town() & grow(band, 1) & (reg >= 0) & (reg != NP)             # towns inside the band seed their own region
        _, lb = dijkstra({(int(x), int(y)): int(reg[y, x]) for y, x in np.argwhere(ring | tw_)}, bcost, band | ring | tw_, w, h)
        sw_ = band & (lb >= 0) & (lb != reg); reg[sw_] = lb[sw_]
        log(f"old-edge seam: {int(band.sum())} band hexes, {int(sw_.sum())} re-assigned")
    log(f"territory: {int(take.sum())} hexes to new / freed-land regions")
    # donor protection: an existing region cut below vanilla's p10 size gets back its own hexes nearest its town
    for i in set(int(x) for x in np.unique(reg0[take])) - new_ids - moved_ids - gen_ids - {NP, -1}:
        a0, a1 = int(((reg0 == i) & land_ok).sum()), int(((reg == i) & land_ok).sum())
        if a1 >= MIN_AREA or a0 < MIN_AREA: continue
        tw = [(int(x), int(y)) for y, x in np.argwhere((reg == i) & (f["slot"] == 0))]
        if not tw: continue
        dd, _ = dijkstra({t: 0 for t in tw}, cost, (reg0 == i) & land_ok, w, h)
        lost = np.argwhere((reg0 == i) & (reg != i) & land_ok & ~town() & np.isfinite(dd))
        lost = lost[np.argsort(dd[lost[:, 0], lost[:, 1]])][:MIN_AREA - a1]
        reg[lost[:, 0], lost[:, 1]] = i
        log(f"  donor protection: {names[i]} {a1} -> {int(((reg == i) & land_ok).sum())} hexes")
    # size check (vanilla p10..p90): new / moved regions and the donors they were carved from
    viol = []                                                   # (region name, reason) for the size rule
    for i in sorted(new_ids | moved_ids):
        a_ = int(((reg == i) & land_ok).sum()); nm_ = names[i] if i < NL else [x[0] for x in new_regions][i - NL]
        hi_ = MAX_FRONTIER if i in moved_ids else MAX_AREA
        if not (MIN_AREA <= a_ <= hi_): log(f"  size: {nm_} {a_} hexes (target {MIN_AREA}-{hi_})")
        if i in new_ids and a_ < MIN_NEW: viol.append((nm_, a_))
    for i in set(int(x) for x in np.unique(reg0[take])) - new_ids - moved_ids - gen_ids - {NP, -1}:
        a0, a1 = int(((reg0 == i) & land_ok).sum()), int(((reg == i) & land_ok).sum())
        if a1 < MIN_AREA <= a0:
            takers = collections.Counter(int(x) for x in reg[(reg0 == i) & (reg != i) & land_ok] if int(x) in new_ids)
            if takers:
                t_ = takers.most_common(1)[0][0]; nm_ = [x[0] for x in new_regions][t_ - NL]
                viol.append((nm_, -1)); log(f"  donor below {MIN_AREA}: {names[i]} {a0} -> {a1} hexes (mostly to {nm_})")

    # ---------------- 4. natural borders: majority smoothing on borders touching a changed region ------------------
    changed = new_ids | moved_ids | gen_ids
    for it in range(3):
        n_sw = 0
        cnt = {}
        for nr, nc, v in NA:
            nb = np.where(v, reg[nr, nc], -9)
            for lbl in changed:
                cnt[lbl] = cnt.get(lbl, 0) + (nb == lbl)
        for lbl, c_ in cnt.items():
            sw = (c_ >= 4) & (reg != lbl) & land_ok & ~town() & ~np.isin(reg, passes) & (reg != NP) & (reg >= 0) & (reg < NL + NN)
            reg[sw] = lbl; n_sw += int(sw.sum())
        if not n_sw: break
        log(f"  smoothing pass {it}: {n_sw} hexes")

    # ---------------- 5. clean-up: pieces cut off by the carve go to the neighbour sharing the most border; a piece
    #                     that was already separate before (islands of Kuaiji, Tongan, ...) stays ----------------------
    touched = changed | set(int(x) for x in np.unique(reg0[reg0 != reg]))
    orig_stray = np.zeros((h, w), bool)
    for i in touched - changed - {NP, -1}:
        for comp in components((reg0 == i) & land_ok):
            if not any(f["slot"][r, c] >= 0 for c, r in comp):
                for c, r in comp: orig_stray[r, c] = True
    for it in range(8):
        mv = 0
        for i in touched - {NP, -1}:
            comps = components((reg == i) & land_ok)
            if len(comps) <= 1: continue
            for comp in comps:
                if any(f["slot"][r, c] >= 0 for c, r in comp): continue
                if all(orig_stray[r, c] for c, r in comp): continue
                cntn = {}
                for c, r in comp:
                    for k in range(6):
                        nc_, nr_ = neighbour(c, r, k)
                        if 0 <= nc_ < w and 0 <= nr_ < h and land_ok[nr_, nc_] and reg[nr_, nc_] != i:
                            cntn[int(reg[nr_, nc_])] = cntn.get(int(reg[nr_, nc_]), 0) + 1
                tgt = max(cntn, key=cntn.get) if cntn else NP
                for c, r in comp: reg[r, c] = tgt
                mv += len(comp)
        if not mv: break
        log(f"  clean-up pass {it}: {mv} hexes")

    # ---------------- 6. province connectivity (capital + resource one area) -------------------------------------
    for key, pv in provinces.items():
        ids = [rid[n] for n in pv["regions"]]
        comps = components(np.isin(reg, ids) & land_ok)
        pv["connected"] = len(comps) == 1
        if len(comps) > 1: log(f"  ! province {key} is in {len(comps)} pieces")

    # ---------------- 6b. Hexi: every moved town on the main passable land (a valley bridge where the corridor breaks) --
    # meandering valley (flat desert would give a straight line): noisy cost, noisy width
    mean_ = smooth_noise((h, w), 6, 24); mean_ = (mean_ - mean_.min()) / (np.ptp(mean_) + 1e-9)
    # low ground first: a valley bridge follows the valley floor the way a river does (the Ruoshui from Zhangye down to
    # the Juyan basin), then noise for the last bit of meander
    hz = hh[hexi_zone & (terr == 0)]; lo_, hi_ = np.percentile(hz, 2), np.percentile(hz, 60)
    hn = np.clip((hh - lo_) / max(1.0, hi_ - lo_), 0, 1)
    ccost2 = 1.0 + SLOPE_COST * slope + 4.0 * mountain + 1.5 * mean_ + 10.0 * hn
    for it_ in range(24):
        passable = walk_mask(f) & (reg != NP) & (reg >= 0)          # bridges / fords count (the Yellow River is sea hexes)
        comps_ = components(passable); main_ = max(comps_, key=len); mm = np.zeros((h, w), bool)
        for c_, r_ in main_: mm[r_, c_] = True
        cut_ = [(i, placed[names[i]], mm) for i in moved_ids if placed.get(names[i]) and not mm[placed[names[i]][1], placed[names[i]][0]]]
        # tribal towns (north cull): each on the main land, and each tribal province in one piece (bridge to its capital)
        for i in nomad_ids:
            x_ = new_regions[i - NL]; st_ = (x_[3], x_[4])
            if not mm[st_[1], st_[0]]: cut_.append((i, st_, mm))
        if not cut_:
            for key, pv in provinces.items():
                ids_ = [rid[n] for n in pv["regions"]]
                if not set(ids_) & nomad_ids: continue
                cap_m = np.isin(reg, [ids_[0]]) & land_ok
                cc_ = components(np.isin(reg, ids_) & land_ok)
                if len(cc_) < 2: continue
                for comp in cc_:
                    if any(cap_m[r_, c_] for c_, r_ in comp[:1]) or any(cap_m[r_, c_] for c_, r_ in comp): continue
                    j_ = next((k for k in ids_[1:] if any(reg[r_, c_] == k for c_, r_ in comp)), None)
                    if j_ is None: continue
                    x_ = new_regions[j_ - NL]; cut_.append((j_, (x_[3], x_[4]), cap_m))
        if not cut_: break
        # one bridge per round, the shortest: the others may then join through it
        cands_ = []
        for i, st_, tgt_m in cut_:
            path_ = route(st_, tgt_m, (terr == 0) & ~mountain, np.zeros((h, w), np.int64), ccost2, hh, w, h)
            if path_ and not (i in nomad_ids and len(path_) > 60): cands_.append((len(path_), i, path_))
        if not cands_:
            for i, _, _ in cut_: log(f"  ! no valley bridge (<= 60 hexes) for {names[i] if i < NL else new_regions[i - NL][0]}")
            break
        for _, i, path_ in sorted(cands_, key=lambda t: t[0])[:1]:
            nm_i = names[i] if i < NL else new_regions[i - NL][0]
            pm = np.zeros((h, w), bool)
            for x, y in path_: pm[y, x] = True
            wid = smooth_noise((h, w), 5, 25)
            for k_ in range(4):                                  # 2..4 hexes wide, varying along the valley
                g_ = pm.copy()
                for nr, nc, v in NA: g_ |= v & pm[nr, nc]
                pm = g_ if k_ < 2 else (pm | (g_ & (wid > (k_ - 2) * 0.4 - 0.2)))
            pm &= (terr == 0) & ~mountain & ~town()
            newland = pm & ((reg == NP) | (reg < 0))
            reg[newland] = i; f["imp"][pm & (np.isin(reg, list(moved_ids | nomad_ids)) | newland)] = 0
            log(f"  valley bridge {nm_i}: {len(path_)} hexes, {int(newland.sum())} new corridor hexes")

    # stray pieces left by the bridges (no town, <= 20 hexes): to the neighbour sharing most border
    for i in new_ids | moved_ids | gen_ids:
        for comp in components((reg == i) & land_ok):
            if len(comp) > 20 or any(f["slot"][r_, c_] == 0 for c_, r_ in comp): continue
            cm = np.zeros((h, w), bool)
            for c_, r_ in comp: cm[r_, c_] = True
            nb = collections.Counter()
            for nr, nc, v in NA:
                q_ = v & cm; nb.update(int(x) for x in reg[nr[q_], nc[q_]] if int(x) != i and int(x) >= 0)
            if nb: reg[cm] = nb.most_common(1)[0][0]
    for key, pv in provinces.items():                            # re-check after the bridges
        n_ = len(components(np.isin(reg, [rid[n] for n in pv["regions"]]) & land_ok))
        if n_ > 1: log(f"  ! province {key} still in {n_} pieces after bridges")
    # ---------------- 7. roads: every new / moved town joins the main road network ---------------------------------
    # network = road / town hexes in components that contain towns which were not placed or moved here; capitals route
    # to it, resources to their capital (or the network when the capital is only reachable the long way round); every
    # finished route and town footprint is added to the network
    road = f["road"]; tm = town()
    base_cost = 1.0 + np.where(f["imp"] == 1, 6.0, 0) + np.where(f["river"] > 0, 3.0, 0) + 3.0 * slope + 2.5 * noise   # roads bend with the land
    # historic routes (user's Liang map): the Juyan road follows the Ruo river, not a straight line across the desert
    from PIL import ImageDraw
    gim = Image.new("1", (w, h), 0)
    for nm_, line_ in json.load(open(HERE / "research_r6" / "hexi_road_guides.json", encoding="utf-8")).items():
        if nm_.startswith("_"): continue
        vs = []
        for la_, lo_ in line_:
            ox_, oz_ = rubber.to_world(la_, lo_); nx_, nz_ = W.fwd_world(float(ox_), float(oz_))
            c_, r_ = nearest_hex(np.array([nx_]), np.array([nz_]), w, h); vs.append((int(c_[0]), int(r_[0])))
        ImageDraw.Draw(gim).line(vs, fill=1, width=2)
    guide = np.array(gim, bool) & (terr != 1)
    base_cost = np.where(guide, 0.4, base_cost)
    log(f"road guides: {int(guide.sum())} hexes")
    changed_ids = new_ids | moved_ids | gen_ids
    net = np.zeros((h, w), bool)
    for comp in components(((road > 0) | (f["bridge"] > 0) | tm) & (terr != 1) | (f["bridge"] > 0)):
        ids_ = {int(reg[r, c]) for c, r in comp if f["slot"][r, c] == 0}
        if ids_ - changed_ids:
            for c, r in comp: net[r, c] = True
    road_list = [(rid[x[0]], x[0], x[2], (x[3], x[4]), provinces[next(k for k, p in provinces.items() if x[0] in p["regions"])])
                 for x in new_regions] + [(i, m["key"], m["kind"], placed[m["key"]], None) for i, m in moved.items() if m["key"] in placed]                 + [(i, m["key"], m["kind"], placed[m["key"]], None) for i, m in gen_moved.items() if m.get("placed")]
    road_list.sort(key=lambda t: t[2] != "capital")                 # capitals first: resources then reach a connected capital
    for i, nm, kind, start, pv in road_list:
        own = (reg == i) & (f["slot"] >= 0)
        if pv and pv.get("attach"): cap_id = None
        elif pv and kind != "capital": cap_id = rid[pv["regions"][0]]
        elif pv is None and kind != "capital":                     # a moved resource: its moved capital, if it moved
            cap_key = m_key = names[i].rsplit("_resource", 1)[0] + "_capital"
            cap_id = names.index(cap_key) if cap_key in names and names.index(cap_key) in moved_ids else None
        else: cap_id = None
        tgt = net & (reg != i) if cap_id is None else ((reg == cap_id) & (f["slot"] == 0))
        ok = ((terr == 0) | own | tgt) & ~(tm & ~own & ~tgt) & (reg != NP)      # roads never cross non-playable land
        path = route(start, tgt, ok, road, base_cost, hh, w, h)
        if cap_id is not None:
            cs = np.argwhere((reg == cap_id) & (f["slot"] == 0))
            capc = (int(cs[0][1]), int(cs[0][0])) if len(cs) else start
            if path is None or len(path) > 3 * hdist(start, capc) + 10:
                tgt = net & (reg != i); ok = ((terr == 0) | own | tgt) & ~(tm & ~own & ~tgt) & (reg != NP)
                p2 = route(start, tgt, ok, road, base_cost, hh, w, h)
                if p2 is not None and (path is None or len(p2) < len(path)): path = p2
        if path is None: log(f"  ! no road for {nm}"); continue
        for (x0, y0), (x1, y1) in zip(path, path[1:]):
            for k in range(6):
                if neighbour(x0, y0, k) == (x1, y1): road[y0, x0] |= 1 << k; road[y1, x1] |= 1 << ((k + 3) % 6)
            f["imp"][y0, x0] = 0; f["imp"][y1, x1] = 0
        for x, y in path: net[y, x] = True
        net |= own | ((reg == i) & (f["sprawl"] == 1))
        log(f"  road {nm}: {len(path)} hexes")
    # dead-end spurs left at the vacated sites of moved towns: prune back to the next junction
    front = set()
    for m in gen_moved.values():
        if not m.get("placed"): continue
        for x, y, _, _ in m["old_fp"]:
            for yy in range(max(0, y - 2), min(h, y + 3)):
                for xx in range(max(0, x - 2), min(w, x + 3)):
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
    log(f"  pruned {pruned} dead-end road hexes at vacated town sites")

    # ---------------- 8. corridor land fields; pockets cut off from their town become impassable ------------------
    conv = padland & np.isin(reg, list(moved_ids)) | (NCM["open_nomad"] & np.isin(reg, list(nomad_ids)))
    gidx = {n: k for k, n in enumerate(L["ground_types"])}
    gr = np.array([gidx.get(GROUND_BY_BLEND.get(b, "plains"), gidx["plains"]) for b in range(32)])
    f["ground"][conv] = gr[hb[conv]]
    play_pass = land_ok & (reg != NP) & ~conv & (f["imp"] == 0) & (reg >= 0)
    srcp = {(int(x), int(y)): int(y) * w + int(x) for y, x in np.argwhere(play_pass)}
    _, near = dijkstra(srcp, np.ones((h, w)), land_ok, w, h)
    ny_, nx_ = np.divmod(near[conv], w)
    for k in ("climate", "attr", "aoi", "restr", "b9"): f[k][conv] = f[k][ny_, nx_]
    cut = 0
    for i in list(moved_ids) + list(new_ids):
        for comp in components((reg == i) & land_ok & (f["imp"] == 0)):
            if not any(f["slot"][r, c] >= 0 for c, r in comp):
                for c, r in comp:
                    if f["road"][r, c] == 0: f["imp"][r, c] = 1; cut += 1
    log(f"corridor land {int(conv.sum())} hexes; {cut} cut-off pocket hexes made impassable")

    # ---------------- 9. write ------------------------------------------------------------------------------------
    redge = np.zeros((h, w), np.int32)
    for k, (nr, nc, v) in enumerate(NA): redge |= ((v & (reg[nr, nc] != reg)).astype(np.int32) << k)
    f["redge"] = redge
    # ---------------- 9. bridge banks (CAIME pathfinding): each bridge's shore must be exactly 2 land groups - its
    #                     BridgesGenerator splits the shore into 2 banks and a 3rd group crashes HLCI (index -1).
    #                     A shore split by one water hex (the warp shrank a diagonal bridge) is joined: that hex -> beach
    fix_bridge_banks(f, names, NL + NN, w, h, log)
    out = pack(f); out[..., 10:15] = g[..., 10:15]
    prefix = replace_region_lists(src[:P], land + [x[0] for x in new_regions], sea_names)
    body = prefix + struct.pack("<II", w, h) + out.tobytes()
    OUT.write_bytes(body + struct.pack("<I", zlib.crc32(body) & 0xFFFFFFFF))
    for k, pv in provinces.items():
        pv["hexes"] = {n: int((reg == rid[n]).sum()) for n in pv["regions"]}
        pv["towns"] = {n: list(v) for n, v in pv["towns"].items()}
    json.dump(dict(provinces=provinces, moved={m["key"]: dict(site=list(placed.get(m["key"], [])), lat=m["lat"], lon=m["lon"], old_site=m["old_site"])
                                                 for m in moved.values()}, dropped=dropped,
                   moved_r7={m["key"]: dict(site=list(placed[m["key"]]), old_site=m["old_site"], lat=m["lat"], lon=m["lon"])
                             for m in gen_moved.values() if m.get("placed")}),
              open(HERE / "regions_new.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    log(f"wrote {OUT}: {NL + NN} land regions (+{NN}), {len(sea_names)} sea")
    if preview:
        from regions_carve import draw_preview
        centres = {}
        for i in range(NL + NN):
            m = (reg == i) & (f["slot"] == 0)
            if m.any():
                pts = np.argwhere(m); r, c = pts[np.argmin(((pts - pts.mean(0)) ** 2).sum(1))]; centres[i] = (int(c), int(r))
        draw_preview(reg, f, new_ids | moved_ids, centres, w, h, preview, box=(0, w, 300, h))
    town_of = {x[0]: x[1] for x in new_regions}
    return provinces, dropped, [(town_of.get(n, n), n, a) for n, a in viol]


if __name__ == "__main__":
    # retries: a province in pieces gets its resource closer to the capital; a dropped core / must capital a wider search
    cand = json.load(open(CAND, encoding="utf-8")); tier = {p["label"]: p["tier"] for p in cand["provinces"]}
    rr0 = {p["key"]: tuple(p["res_range"]) for p in cand["provinces"] if p.get("res_range")}
    key_of = {p["label"]: p["key"] for p in cand["provinces"]}
    ro, so, nr, skip = {}, {}, set(), set()
    label_of = {}
    for p in cand["provinces"]:
        for t in p["towns"]: label_of[t[0]] = (p["label"], p["tier"], t[3])
    rank = {"must": 3, "core": 2, "optional": 1}
    for attempt in range(16):
        print(f"=== attempt {attempt}: resource ranges {ro}, no resource {sorted(nr)}, size-rule drops {sorted(skip)}")
        provinces, dropped, viol = main(res_override=ro, search_override=so, no_res=nr, skip=skip)
        todo = False
        for k, pv in provinces.items():
            if not pv.get("connected", True) and not pv.get("attach"):
                lo, hi = ro.get(k, rr0.get(k, RES_RANGE))
                if hi - lo <= 12: nr.add(k)                        # cannot connect: province becomes one region (rule 1)
                else: ro[k] = (lo, max(lo + 12, hi - 12))
                todo = True
        if not todo and viol:
            # size rule: drop one town per attempt - optional before core (never must), resource before capital, smallest first
            cands_ = [(rank[label_of[t][1]], label_of[t][2] == "capital", a if a >= 0 else 0, t) for t, n, a in viol
                      if t in label_of and label_of[t][1] != "must"]
            if cands_:
                t = sorted(cands_)[0][3]; skip.add((label_of[t][0], t)); print(f"   size rule: dropping {t}"); todo = True
        if not todo: break
