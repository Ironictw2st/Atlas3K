#!/usr/bin/env python3
"""Vanilla-standard settlement dressing for every new region (user 2026-10-03: "the props are so far apart, look at how
every other region has props, that should be the standard"; scope: all new regions; steppe: big nomad camps).

BUILD RULE (ak_main.py, after north_dress.add): add(out_dir, map_name)
  * regions: every land region stock 190E doesn't have (town_props_scan's list) + the x15 provinces' regions
  * count per region: DENSITY clusters per 1000 land hexes (stock 190E: 1.45, korea_ref/village_templates.json), at least
    1 for regions over 300 hexes
  * sites: passable plain land 4..30 hexes from a town and >= 3 from every town, not on a road / river / mountain tile,
    gentle ground, >= SPACING hexes apart; hexes within 2 of a road or river first (where vanilla puts them)
  * steppe zones (steppe / Hexi plans): a nomad camp - ring of tents round a banner, livestock pens, hay, logs, barrels,
    carts (vanilla models and scales); everywhere else a vanilla village template of the site's climate (village_templates.py),
    turned 0 or 180 degrees (both unambiguous for the pieces' own yaw), re-seated on the new ground
  * every piece must stand on a usable hex (no road / river / sea / town / impassable) or the site is skipped
  * 2026-10-04 polish (docs/proposals/new_areas_lookover.md M6 / M3a): camp pens capped at FENCE_CAP pieces in
    alternating vanilla fence variants, freed budget partly spent on carts / hay / logs; Korea / NE gets KOREA_DENSITY
    extra village clusters per 1000 land hexes + ambient groups up to the stock density (own rng, after the rest)
Appended to the same referenced non-playable layer as north_dress."""
import json, math, re, sys
from pathlib import Path
import numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
TEMPL = HERE / "korea_ref" / "village_templates.json"
AMB_T = HERE / "korea_ref" / "ambient_templates.json"
VILLAGE_HEX = HERE / "korea_ref" / "village_hexes.npy"      # trees_x15 clears these too
PLANS = [HERE / "korea_ref" / "steppe_plan.json", HERE / "korea_ref" / "hexi_plan.json"]
CAMP_ZONES = {"grass_steppe", "meadow_steppe", "desert_steppe", "corridor_steppe", "gobi", "juyan"}
DENSITY, MIN_HEXES, SPACING = 2.2, 200, 6           # polish r5: stock far-from-town pieces ~70 / 1000 land hexes on this map
POLISH_TENT_GAP, GROUND_RANGE, PROP_CLEAR = 0.9, 0.12, 0.3
U2W = 0.000218712; W0 = 3.12725; SEA_Y = 14219 * U2W - W0
HEIGHT = HERE / "terrain" / "3k_dlc07_main_map.height.191fd803c1a801d.tif"
CLIMATES = ['arid', 'cold', 'default', 'subtropical', 'temperate']
S = "rigidmodels/campaign/settlements/"
TENT_S = [S + "tent_%d.wsmodel" % i for i in range(4)]            # small tents (r 0.36..0.59 x 0.24)
TENT_L = [S + "tent_%d.wsmodel" % i for i in range(4, 8)]         # big tents (r 0.98..1.87 x 0.24)
R_TENT = {**{S + "tent_%d.wsmodel" % i: r for i, r in enumerate((0.588, 0.423, 0.423, 0.356, 0.979, 1.114, 1.303, 1.868))}}
FENCE, HAY, HAYB, BARREL, CART = S + "fence_1_level1.wsmodel", S + "props/hay_pile_1.wsmodel", S + "props/hay_barrel_1.wsmodel", S + "props/barrel_1.wsmodel", S + "props/cart_1.wsmodel"
LOGS = [S + "props/log_1.wsmodel", S + "props/log_3.wsmodel"]
BANNER = "RigidModels/campaign/settlements/props/flag_banner_large_1.wsmodel"
SC = 0.24
# 2026-10-04 polish M6 (docs/proposals/new_areas_lookover.md): fence_1_level1.wsmodel was 27% of Hexi's non-tree props.
# A camp now gets at most FENCE_CAP pen pieces: the first pen keeps a half-open arc, a second pen is an open corral.
# Each fenced pen uses one of the vanilla fence variants (fence wsmodel / its rigid_model_v2 / wall_1 plank fence; wall_1
# is 1 model unit long against the fence's 0.5, so it goes at half scale to fill the same slot). The freed pieces are
# partly spent on carts / hay / log piles of the camp kit round the pens (CLUTTER_SHARE of them, at most CLUTTER_MAX per
# pen). All of it is decided from the camp's existing rng draws: the main rng stream (placements + ids of every later
# camp / village) is unchanged - dropped fence pieces still burn their id draw, the new clutter gets hashed ids.
FENCE_CAP, CLUTTER_SHARE, CLUTTER_MAX = 6, 0.34, 3
FENCE_VARIANTS = [(S + "fence_1_level1.wsmodel", 1.0), (S + "fence_1_level1.rigid_model_v2", 1.0), (S + "wall_1.wsmodel", 0.5)]
# 2026-10-04 polish M3(a): Korea / NE (ironic_region_* outside the Hexi / Wuyuan keys: stock 190E, so never in newk)
# gets villages at KOREA_DENSITY clusters per 1000 land hexes on top of 190E's own, and ambient groups up to the stock
# density (minus what 190E already has there). Own rng after the main rules, so nothing above moves.
KOREA_DENSITY = 0.8                     # proposal said ~1.2; measured: 1.2 -> 129 settlement pieces / 1000 land hexes (vanilla temperate 118), 0.8 -> 96
KOREA_SKIP = ("hanyang", "xi_", "wuwei", "xiping", "wuyuan")
AMB_PIECES_PER_GROUP = 1.9             # measured: 2016 entities / 1064 groups


def _ent(eid, model, x, y, z, rot, s, clamp):
    import north_dress
    return north_dress._ent(eid, model, x, y, z, rot, s, clamp)


def _host(out_dir, map_name):
    terry = open(out_dir / f"{map_name}.terry", encoding="utf-8", errors="replace").read()
    used = set(re.findall(r'id="([0-9a-f]+)"', terry))
    lays = [p for p in sorted(out_dir.glob(f"{map_name}.*.layer")) if p.name.split(".")[-2] in used]
    return next((p for p in lays if "3k_main_reg_non_playable" in open(p, encoding="utf-8").read(400)), lays[0])


def zones(h, w):
    Z = np.full((h, w), "", object)
    for pf in PLANS:
        for r, runs in json.load(open(pf, encoding="utf-8"))["zone_rle"].items():
            for s, n, z in runs: Z[int(r), s:s + n] = z
    return Z


def camp(rng):
    """(model, dx, dz, scale, yaw) pieces of one nomad camp, ~1 hex across."""
    out = []
    out.append((BANNER, 0.0, 0.0, 0.5, float(rng.uniform(0, 360))))
    nt = int(rng.integers(8, 15)); R = float(rng.uniform(0.45, 0.65))
    big = int(rng.integers(0, nt))
    placed = []                                                                # (x, z, footprint radius) of the tents
    def free(x, z, r_):
        return all(math.hypot(x - a, z - b) >= POLISH_TENT_GAP * (r_ + rb) for a, b, rb in placed)
    for i in range(nt):
        m = TENT_L[int(rng.integers(0, 2))] if i == big else TENT_S[int(rng.integers(0, 4))]
        rt = R_TENT[m] * SC
        for _try in range(12):                                                 # polish r1: tents never overlap
            a = 2 * math.pi * i / nt + float(rng.uniform(-0.25, 0.25))
            rr = R * float(rng.uniform(0.9, 1.15)) + (0.12 if i == big else 0) + 0.03 * _try
            tx, tz = rr * math.cos(a), rr * math.sin(a)
            if free(tx, tz, rt): break
        else: continue
        placed.append((tx, tz, rt))
        out.append((m, tx, tz, SC, math.degrees(-a) + 90 + float(rng.uniform(-20, 20))))
    extra, fences_left = [], FENCE_CAP
    for ip in range(int(rng.integers(1, 3))):                                  # livestock pens outside the ring
        a0 = float(rng.uniform(0, 2 * math.pi)); pc = (R + 0.42) * math.cos(a0), (R + 0.42) * math.sin(a0); pr = float(rng.uniform(0.16, 0.24))
        nf = max(6, int(2 * math.pi * pr / 0.11))
        # polish M6: a per-pen local rng from this pen's own draws (no main-stream draw)
        lr = np.random.default_rng([int(a0 * 1e9) & 0xFFFFFFFF, int(pr * 1e9) & 0xFFFFFFFF, ip])
        fm, fs = FENCE_VARIANTS[int(lr.integers(0, len(FENCE_VARIANTS)))]
        k0 = int(lr.integers(1, nf))                                           # the arc starts at a random piece
        freed, arc = 0, min(fences_left, nf - 2)                               # arc of <= the camp's remaining cap
        for k in range(nf):
            if k == 0: continue                                                # the gate
            a = 2 * math.pi * k / nf
            if (k - k0) % nf < arc:
                fences_left -= 1
                out.append((fm, pc[0] + pr * math.cos(a), pc[1] + pr * math.sin(a), SC * fs, math.degrees(-a)))
            else:
                out.append((None, pc[0] + pr * math.cos(a), pc[1] + pr * math.sin(a), 0.0, 0.0)); freed += 1   # dropped: burns its id draw, keeps the site test
        for j in range(min(CLUTTER_MAX, int(round(freed * CLUTTER_SHARE)))):   # carts / hay / logs round the pen
            a, d = float(lr.uniform(0, 2 * math.pi)), float(lr.uniform(0.3, 1.0)) * pr
            m = [CART, HAY, HAYB, LOGS[0], LOGS[1], CART][int(lr.integers(0, 6))]
            extra.append((m, pc[0] + d * math.cos(a), pc[1] + d * math.sin(a), SC, float(lr.uniform(0, 360)), "extra"))
        for _ in range(int(rng.integers(1, 3))):
            a, d = float(rng.uniform(0, 2 * math.pi)), float(rng.uniform(0, pr * 0.5))
            out.append((HAY, pc[0] + d * math.cos(a), pc[1] + d * math.sin(a), SC, float(rng.uniform(0, 360))))
    for _ in range(int(rng.integers(6, 12))):                                  # camp clutter between the tents
        for _try in range(8):
            a, d = float(rng.uniform(0, 2 * math.pi)), float(rng.uniform(0.12, R * 0.8))
            if free(d * math.cos(a), d * math.sin(a), 0.06): break
        else: continue
        m = [HAY, HAYB, BARREL, BARREL, LOGS[0], LOGS[1], CART][int(rng.integers(0, 7))]
        out.append((m, d * math.cos(a), d * math.sin(a), SC, float(rng.uniform(0, 360))))
    return out + extra                                                         # polish M6: hashed-id clutter last


# ---------------------------------------------------------------- ambient life (2026-10-03 VFX round)
AMB_DENSITY, AMB_SPACING = 3.95, 4                     # stock 190E: 1625 ambient groups, 3.95 per 1000 land hexes
NEEDS_TREES = ("leaves", "blossoms", "fireflies")
NEVER = ("panda", "pig_", "rice", "fisher", "river_crossing", "waterfall", "crane", "single_circle", "single_large_circle")
STEPPE_OK = ("dust", "heat_haze", "wind", "pollen", "butterflies", "horse", "deer", "doe", "cow01", "mist", "snow_drift", "flies", "clouds")


def ambient(L):
    """Stock ambient groups (4-season leaf sets, mist, dust, herds, deer) stamped in the new regions at the stock density,
    matching the site climate; leaf / blossom / firefly sets only on tree hexes, steppe zones only steppe-plausible sets."""
    import trees_x15
    f, w, h, rng, Z, AMB, usable, dtown = L["f"], L["w"], L["h"], L["rng"], L["Z"], L["AMB"], L["usable"], L["dtown"]
    HX, HZ, ground, stamp, ok_xz, newk, land_n = L["HX"], L["HZ"], L["ground"], L["stamp"], L["ok_xz"], L["newk"], L["land_n"]
    tim = Image.open(HERE / "terrain" / trees_x15.TREE); tree = trees_x15.hexvals(np.array(tim), w, h) != trees_x15.NO_TREE
    groups = [g for g in AMB["groups"] if not any(k in g["names"] for k in NEVER)]
    bycl = {c: [g for g in groups if g["climate"] == c] for c in CLIMATES}
    taken = np.zeros((h, w), bool); out = []; n_amb = 0
    cand_all = usable & (dtown >= 2)
    for k in sorted(newk):
        n = L["amb_n"][k] if "amb_n" in L else int(round(land_n[k] * AMB_DENSITY / 1000))   # polish M3a: Korea's own count
        rr, cc = np.nonzero(cand_all & (f["region"] == k))
        if n == 0 or len(rr) == 0: continue
        order = rng.permutation(len(rr)); placed = 0
        for i in order:
            if placed >= n: break
            r, c = int(rr[i]), int(cc[i])
            if taken[r, c]: continue
            cl = CLIMATES[int(f["climate"][r, c])] if 0 <= int(f["climate"][r, c]) < 5 else "temperate"
            pool = bycl.get(cl) or bycl["temperate"]
            steppe = Z[r, c] in CAMP_ZONES
            pool = [g for g in pool if (tree[r, c] or not any(t in g["names"] for t in NEEDS_TREES))
                    and (not steppe or all(any(o in nm for o in STEPPE_OK) for nm in g["names"].split()))]
            if not pool: continue
            g = pool[int(rng.integers(0, len(pool)))]
            x = c * HX; z = r * HZ + (c & 1) * HZ / 2
            xs = [x + p["dx"] for p in g["pieces"]]; zs = [z + p["dz"] for p in g["pieces"]]
            if not ok_xz(xs, zs): continue
            g0 = max(ground(x, z), SEA_Y)
            for p, px, pz in zip(g["pieces"], xs, zs):
                out.append(stamp(p, px, g0 + p["dy"], pz, 0.0))
            r0, r1 = max(0, r - AMB_SPACING), min(h, r + AMB_SPACING + 1); c0, c1 = max(0, c - AMB_SPACING), min(w, c + AMB_SPACING + 1)
            taken[r0:r1, c0:c1] = True; placed += 1; n_amb += 1
    print(f"village_dress ambient: {n_amb} groups, {len(out)} entities")
    return out


def clear_trees(mask, w, h):
    """No-tree on the village / camp hexes in the CampaignTree raster (terrain/ + kit copies) - the tree list is built after."""
    import trees_x15
    a_ = None
    kt = trees_x15.TREE.replace("3k_dlc07_main_map", trees_x15.KIT.name)
    for p in (HERE / "terrain" / trees_x15.TREE, trees_x15.KIT / kt, trees_x15.KIT / kt.replace(".tree.", ".tree_new.")):
        if not p.exists(): continue
        im = Image.open(p); a = np.array(im); H, W = a.shape
        ys, xs = np.mgrid[0:H, 0:W]
        pc = np.minimum(xs // 2, w - 1); pr = np.clip((H - 1 - ys - (pc & 1)) // 2, 0, h - 1)
        hit = mask[pr, pc] & (a != trees_x15.NO_TREE); a[hit] = trees_x15.NO_TREE
        out = Image.fromarray(a, "P"); out.putpalette(im.getpalette()); out.save(p, compression="tiff_lzw")
        a_ = int(hit.sum())
    print(f"village_dress: trees cleared on {int(mask.sum())} village / camp hexes ({a_} px)")


def add(out_dir, map_name="3k_dlc07_main_map", dry=False):
    import town_fix as T, town_props_scan, x15_land, caime_tilemap as CT
    from hexgrid import HX, HZ, neighbour_arrays, nearest_hex
    from scipy import ndimage as ndi
    out_dir = Path(out_dir)
    _, _, w, h, _, f, names = T.load(str(HERE / "hex" / "map.hex")); NA = neighbour_arrays(h, w)
    S_ = town_props_scan._setup()
    newk = set(np.flatnonzero(np.isin(np.arange(len(names)), np.unique(f["region"][S_["town"]]))).tolist()) | x15_land._new_ids(names)
    newk = {k for k in newk if not names[k].startswith("3k_")}
    land = f["terr"] == 0
    town = (f["slot"] >= 0) | (f["sprawl"] > 0)
    road = (f["road"] > 0) | (f["bridge"] > 0)
    redge = f["river"] > 0
    for d, (nr, nc, v) in enumerate(NA):
        m = v & (((f["river"] >> d) & 1) > 0); redge[nr[m], nc[m]] = True
    nearwater = np.zeros((h, w), bool)
    for nr, nc, v in NA: nearwater |= v & (f["terr"][nr, nc] != 0)
    nearwater |= redge
    tile = CT.hex_codes(Image.open(HERE / "tile_map_rebuilt.png"), w, h) if (HERE / "tile_map_rebuilt.png").exists() else None
    mtile = np.isin(tile, x15_land.MOUNTAIN_KINDS) if tile is not None else np.zeros((h, w), bool)
    hgt = np.array(Image.open(HEIGHT)); H8, W8 = hgt.shape
    blk = hgt[H8 - 8 * h:, :8 * w] if H8 >= 8 * h else None
    # relief per hex (u16 range inside its 8x8 block, flipped to row 0 = south)
    if blk is not None:
        b = blk.reshape(h, 8, w, 8); rel = (b.max((1, 3)).astype(np.int32) - b.min((1, 3)))[::-1] * U2W
    else: rel = np.zeros((h, w))
    def ground(x, z):
        px = int(round(x / HX * 8 + 4)); py = int(round(H8 - 1 - (z / HZ * 8 + 4)))
        return float(hgt[min(max(py, 0), H8 - 1), min(max(px, 0), W8 - 1)]) * U2W - W0
    dtown = ndi.distance_transform_edt(~town, sampling=(HZ, HX)) / HX               # hexes to the nearest town
    usable = land & ~town & ~road & ~redge & (f["imp"] == 0)
    base = usable & ~mtile & (rel < 0.35) & (dtown >= 4) & (dtown <= 30)
    near_line = np.zeros((h, w), bool); m = road | redge
    for _ in range(2):
        g = m.copy()
        for nr, nc, v in NA: g |= v & m[nr, nc]
        m = g
    near_line = m
    Z = zones(h, w)
    AMB = json.load(open(AMB_T, encoding="utf-8"))
    temps = [t for t in json.load(open(TEMPL, encoding="utf-8"))
             if max(p["dy"] for p in t["pieces"]) < 3.5 and min(p["dy"] for p in t["pieces"]) > -0.6]
    bycl = {c: [t for t in temps if t["climate"] == c] for c in CLIMATES}
    t = open(_host(out_dir, map_name), encoding="utf-8").read()
    cm = re.search(r"<ECTerrainClamp[^>]*/>", t)
    clamp = cm.group(0) if cm else '<ECTerrainClamp active="false" clamp_to_sea_level="false" terrain_oriented="false" fit_height_to_terrain="false"/>'
    rng = np.random.default_rng(77)
    from scipy.spatial import cKDTree                        # polish r4: keep clear of every prop already in the project
    terry = open(out_dir / f"{map_name}.terry", encoding="utf-8", errors="replace").read(); used = set(re.findall(r'id="([0-9a-f]+)"', terry))
    exist = []
    for lp in out_dir.glob(f"{map_name}.*.layer"):
        if lp.name.split(".")[-2] not in used: continue
        for m_ in re.finditer(r'<ECTransform position="([^ ]+) [^ ]+ ([^ "]+)"', open(lp, encoding="utf-8", errors="replace").read()):
            exist.append((float(m_.group(1)), float(m_.group(2))))
    etree = cKDTree(np.array(exist))
    # 190E's own regions (ironic_*: Korea, Wuyuan, ...) that 190E never dressed count as new (polish r5, 2026-10-03)
    sett = []
    for lp in out_dir.glob(f"{map_name}.*.layer"):
        if lp.name.split(".")[-2] not in used: continue
        for m_ in re.finditer(r'<entity id="(?!0d)[0-9a-f]+">\s*<ECPropMesh/>\s*<ECMesh model_path="[^"]*/settlements/[^"]*".*?position="([^ ]+) [^ ]+ ([^ "]+)"',
                              open(lp, encoding="utf-8", errors="replace").read(), re.S):
            sett.append((float(m_.group(1)), float(m_.group(2))))
    sc_, sr_ = nearest_hex(np.array([p[0] for p in sett]), np.array([p[1] for p in sett]), w, h)
    far_ = dtown[sr_, sc_] >= 4
    have = np.bincount(f["region"][sr_[far_], sc_[far_]] + 1, minlength=len(names) + 1)[1:]
    land_all = np.bincount(f["region"][land].ravel() + 1, minlength=len(names) + 1)[1:]
    bare = {k for k, n in enumerate(names) if n.startswith("ironic_") and land_all[k] > MIN_HEXES and have[k] / land_all[k] * 1000 < 10}
    print(f"village_dress: {len(bare - newk)} undressed 190E regions added ({len(newk)} new)")
    newk = newk | bare
    def clear_of_props(xs, zs):
        return bool((etree.query(np.c_[xs, zs])[0] >= PROP_CLEAR).all())
    used_ids = set(re.findall(r'<entity id="([0-9a-f]+)"', t))
    for lp in out_dir.glob(f"{map_name}.*.layer"):           # polish 2026-10-04: every id in the project (hashed ids)
        used_ids |= set(re.findall(r'<entity id="([0-9a-f]+)"', open(lp, encoding="utf-8", errors="replace").read()))
    def nid():
        while True:
            e = "%015x" % int(rng.integers(0x0d00000000000000 >> 4, 0x0dffffffffffffff >> 4))
            if e not in used_ids: used_ids.add(e); return e
    def xid(tag):                                            # polish 2026-10-04: hashed ids, off the main rng stream
        import hashlib
        k = tag
        while True:
            e = "0d" + hashlib.md5(k.encode()).hexdigest()[:13]
            if e not in used_ids: used_ids.add(e); return e
            k += "#"
    def stamp(pc, px, py, pz, yaw):
        rx, ry, rz = pc["rot"]
        return (pc["e"].replace("@ID@", nid()).replace("@POS@", f"{px:.4f} {py:.5f} {pz:.4f}")
                .replace("@ROT@", f"{rx:g} {(ry + yaw) % 360:g} {rz:g}").replace("@SCL@", pc["scl"]))
    allp = [p for tp in temps for p in tp["pieces"]] + [p for g in AMB["groups"] for p in g["pieces"]]
    LIGHTS = [p for p in allp if "<ECPointLight" in p["e"]][:50]
    HERD = [p for p in allp if re.search(r'path="[^"]*(horse|cow01)[^"]*\.csc"', p["e"])][:80]
    village_hex = np.zeros((h, w), bool)
    def foot(xs, zs, ring):                                  # polish r3: no campaign trees through villages / camps
        c_, r_ = nearest_hex(np.asarray(xs), np.asarray(zs), w, h); m_ = np.zeros((h, w), bool); m_[r_, c_] = True
        for _ in range(ring):
            g_ = m_.copy()
            for nr, nc, v in NA: g_ |= v & m_[nr, nc]
            m_ = g_
        village_hex[...] |= m_
    def ok_xz(xs, zs):
        c, r = nearest_hex(np.asarray(xs), np.asarray(zs), w, h)
        return bool(usable[r, c].all())
    ents, taken, stats = [], np.zeros((h, w), bool), dict(villages=0, camps=0, pieces=0, regions=0, short=0)
    land_n = np.bincount(f["region"][land].ravel() + 1, minlength=len(names) + 1)[1:]
    cols = np.arange(w)[None, :].repeat(h, 0)
    def dress(regions, density):                              # polish 2026-10-04: the region loop as a function (M3a)
        for k in regions:
            n = int(round(land_n[k] * density / 1000))
            if land_n[k] > MIN_HEXES: n = max(n, 1)
            if n == 0: continue
            stats["regions"] += 1
            cand = base & (f["region"] == k)
            rr, cc = np.nonzero(cand)
            if len(rr) == 0: stats["short"] += n; continue
            pri = near_line[rr, cc].astype(float) + rng.uniform(0, 0.9, len(rr))
            order = np.argsort(-pri); placed = 0
            for i in order:
                if placed >= n: break
                r, c = int(rr[i]), int(cc[i])
                if taken[r, c]: continue
                x = c * HX; z = r * HZ + (c & 1) * HZ / 2
                if Z[r, c] in CAMP_ZONES:
                    pcs = camp(rng)
                    # polish M6: the site test uses the pre-M6 piece set (dropped fences keep their spot, the new clutter
                    # is not in it) so the same sites pass as before; the clutter is then tested piece by piece
                    base_p = [p for p in pcs if len(p) == 5]; extra_p = [p for p in pcs if len(p) > 5]
                    xs = [x + p[1] for p in base_p]; zs = [z + p[2] for p in base_p]
                    if not ok_xz(xs, zs) or not clear_of_props(xs, zs): continue
                    foot(xs, zs, 1)
                    for (mdl, dx, dz, s, yaw) in base_p:
                        eid = nid()
                        if mdl is None: continue                                   # dropped pen piece (M6)
                        ents.append(_ent(eid, mdl, x + dx, ground(x + dx, z + dz), z + dz, yaw, s * float(rng.uniform(0.92, 1.08)) if "tent" in mdl else s, clamp))
                    for j, (mdl, dx, dz, s, yaw, _) in enumerate(extra_p):
                        if not ok_xz([x + dx], [z + dz]): continue
                        ents.append(_ent(xid(f"campx:{x:.4f}:{z:.4f}:{j}"), mdl, x + dx, ground(x + dx, z + dz), z + dz, yaw, s, clamp))
                    # 2026-10-03 VFX round: a fire glow at the banner, herds round the camp (vanilla living-campaign scenes)
                    life = [(LIGHTS[int(rng.integers(0, len(LIGHTS)))], 0.05, 0.0, 0.12)] if LIGHTS else []
                    for _ in range(int(rng.integers(2, 5))):
                        a, d = float(rng.uniform(0, 2 * math.pi)), float(rng.uniform(0.9, 1.4))
                        if HERD: life.append((HERD[int(rng.integers(0, len(HERD)))], d * math.cos(a), d * math.sin(a), 0.0))
                    for (pc, dx, dz, dy) in life:
                        if not ok_xz([x + dx], [z + dz]): continue
                        ents.append(stamp(pc, x + dx, ground(x + dx, z + dz) + dy, z + dz, float(rng.uniform(0, 360))))
                    stats["camps"] += 1; stats["pieces"] += len(pcs) + len(life)
                else:
                    cl = CLIMATES[int(f["climate"][r, c])] if 0 <= int(f["climate"][r, c]) < 5 else "temperate"
                    pool = [tp for tp in bycl.get(cl) or bycl["temperate"] if nearwater[r, c] or not tp["port"]] or bycl["temperate"]
                    tp = pool[int(rng.integers(0, len(pool)))]
                    flip = -1.0 if rng.random() < 0.5 else 1.0
                    xs = [x + flip * p["dx"] for p in tp["pieces"]]; zs = [z + flip * p["dz"] for p in tp["pieces"]]
                    if not ok_xz(xs, zs) or not clear_of_props(xs, zs): continue
                    gb = [ground(px, pz) for p, px, pz in zip(tp["pieces"], xs, zs) if abs(p["dy"]) < 0.15 and "/settlements/" in p["e"].lower()]
                    if gb and max(gb) - min(gb) > GROUND_RANGE: stats["uneven"] = stats.get("uneven", 0) + 1; continue   # polish r2
                    g0 = max(float(np.median(gb)) if gb else ground(x, z), SEA_Y)
                    foot(xs, zs, 0)
                    for p, px, pz in zip(tp["pieces"], xs, zs):
                        rx, ry, rz = p["rot"]
                        e = (p["e"].replace("@ID@", nid())
                             .replace("@POS@", f"{px:.4f} {g0 + p['dy']:.5f} {pz:.4f}")
                             .replace("@ROT@", f"{rx:g} {ry + (180 if flip < 0 else 0):g} {rz:g}")
                             .replace("@SCL@", p["scl"]))
                        ents.append(e)
                    stats["villages"] += 1; stats["pieces"] += len(tp["pieces"])
                # spacing: block a disc of SPACING hexes
                r0, r1 = max(0, r - SPACING - 1), min(h, r + SPACING + 2); c0, c1 = max(0, c - SPACING - 1), min(w, c + SPACING + 2)
                yy, xx = np.mgrid[r0:r1, c0:c1]
                taken[r0:r1, c0:c1] |= np.hypot((xx - c) * HX, (yy * HZ + (xx & 1) * HZ / 2) - z) <= SPACING * HX
                placed += 1
            stats["short"] += n - placed
    dress(sorted(newk), DENSITY)
    ents += ambient(locals())
    # ------------------------------------------------ polish 2026-10-04 M3(a): Korea / NE villages + ambient life
    # after every other rule and with its own rng (rebinding rng: nid() / stamp() draw from it from here on), so the
    # villages / camps / ambient above keep their places and ids
    # (most Korea regions are already in newk through the "undressed 190E" rule; this pass adds KOREA_DENSITY on top
    # of whatever they have, in all of them, keeping SPACING from every village / camp placed above)
    kor = sorted(k for k, nm in enumerate(names) if nm.startswith("ironic_region_")
                 and not any(nm.startswith("ironic_region_" + s_) for s_ in KOREA_SKIP))
    rng = np.random.default_rng(1903)
    before = dict(stats); n0 = len(ents)
    dress(kor, KOREA_DENSITY)
    # ambient: up to the stock density, minus the groups 190E already has in the region (ECVFX / ECCompositeScene)
    amb_xz = []
    for lp in out_dir.glob(f"{map_name}.*.layer"):
        if lp.name.split(".")[-2] not in used: continue
        for m_ in re.finditer(r'<entity id="[0-9a-f]+">\s*<EC(?:VFX|CompositeScene).*?<ECTransform position="([^ ]+) [^ ]+ ([^ "]+)"',
                              open(lp, encoding="utf-8", errors="replace").read(), re.S):
            amb_xz.append((float(m_.group(1)), float(m_.group(2))))
    for e_ in ents:                                          # + the groups this run already added (not on disk yet)
        if "<ECVFX" in e_ or "<ECCompositeScene" in e_:
            m_ = re.search(r'<ECTransform position="([^ ]+) [^ ]+ ([^ "]+)"', e_); amb_xz.append((float(m_.group(1)), float(m_.group(2))))
    ac_, ar_ = nearest_hex(np.array([p[0] for p in amb_xz]), np.array([p[1] for p in amb_xz]), w, h)
    have_amb = np.bincount(f["region"][ar_, ac_] + 1, minlength=len(names) + 1)[1:] / AMB_PIECES_PER_GROUP
    amb_n = {k: max(0, int(round(land_n[k] * AMB_DENSITY / 1000 - have_amb[k]))) for k in kor}
    L = dict(locals()); L["newk"] = set(kor); L["amb_n"] = amb_n
    ents += ambient(L)
    print(f"village_dress korea_ne: {len(kor)} regions, +{stats['villages'] - before['villages']} villages "
          f"(+{stats['camps'] - before['camps']} camps), {sum(amb_n.values())} ambient groups wanted, {len(ents) - n0} entities")
    print(f"village_dress: {stats}")
    global LAST, LAST_HEX; LAST, LAST_HEX = ents, village_hex
    if dry: return stats
    np.save(VILLAGE_HEX, village_hex)
    clear_trees(village_hex, w, h)
    host = _host(out_dir, map_name); t = open(host, encoding="utf-8").read()
    i = t.rindex("</entities>")
    t = t[:i] + "\n    " + "\n    ".join(ents) + "\n  " + t[i:]
    open(host, "w", encoding="utf-8", newline="").write(t)
    print(f"village_dress: {len(ents)} entities -> {host.name}")
    return stats


if __name__ == "__main__":
    add(HERE / "ak" / "3k_dlc07_main_map", dry="--dry" in sys.argv)
