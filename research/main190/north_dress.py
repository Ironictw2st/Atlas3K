#!/usr/bin/env python3
"""Apply the steppe + Hexi polish plans (korea_ref/steppe_plan.json, hexi_plan.json; user 2026-10-02 "start applying").

climate()  ONE-OFF, in place (marker hex/.north_climate): each zone's suggested climate (arid / cold / temperate) written
           to map.hex (climate field) and to the climate rasters terrain/climate_map.png (2 px/hex) and climate_map_g.png
           (8 px/hex) - the ground texture follows the climate. korea_forest is left alone. Backups in terrain/_pre_north_dress
           and hex/map_pre_north_dress_<ts>.hex.
add(out_dir, map_name)  BUILD RULE (ak_main.py, after lake_props): the plans' dressing sites as vanilla props at ground
           height: rock outcrops (1-3 rocks) and groves (4-8 poplars / firs), each with a satellite clump (2026-10-03; the
           camps moved to village_dress.py as big nomad camps), ridge / peak props,
           the Han frontier wall (broken straights along the line + a beacon tower at every plan point). Any prop that
           would cover a new town (town_props_scan.covered) is skipped. Appended to the referenced non-playable layer.
           2026-10-04 polish (docs/proposals/new_areas_lookover.md M2 / M3b / M5):
             * poplars: all 5 vanilla sizes, each tree a vanilla 5-entity seasonal set; no grove trees on river hexes
             * cold peaks / ridges (LF-offset shader) get y = offset above the ground (kit_edits/01 values), not absolute
             * korea_ridges: ~1 mountain prop / 100 impassable Korea hexes (+ rock outcrops to vanilla's 1.9 / 1000 land)
             * np_new ridges / peaks within 25 hexes of playable land at the np_old density (1.3 / 1000 impassable)
             The plan entities keep their ids (same rng stream); the new entities get md5-hashed '0e' ids."""
import json, math, re, shutil, struct, sys, time, zlib
from pathlib import Path
import numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
PLANS = [HERE / "korea_ref" / "steppe_plan.json", HERE / "korea_ref" / "hexi_plan.json"]
CLIM_COL = {"arid": (255, 170, 0), "cold": (0, 85, 85), "temperate": (0, 85, 0), "subtropical": (170, 170, 85)}
MARK = HERE / "hex" / ".north_climate"
U2W = 0.000218712; W0 = 3.12725
HEIGHT = HERE / "terrain" / "3k_dlc07_main_map.height.191fd803c1a801d.tif"
M = "rigidmodels/campaign/"
TENTS = [M + "settlements/tent_%d.wsmodel" % i for i in range(8)]
ROCKS = [M + "rocks/general/general_rock_large_1.wsmodel", M + "rocks/general/general_rock_medium_1.wsmodel", M + "rocks/general/general_rock_scree_1.wsmodel"]
POPLAR = [M + "vegetation/arid/arid_tree_poplar_medium_1.wsmodel", M + "vegetation/arid/arid_tree_poplar_large_1.wsmodel"]
# 2026-10-04 polish M2 (docs/proposals/new_areas_lookover.md): every vanilla poplar size, as vanilla's 5-entity seasonal
# set (base model = season_summer + spring / harvest / autumn / winter variants, identical transform; 1017 such sets in
# the kit). The grove loop still draws its medium / large class with the same rng call as before (POPLAR index 0 / 1) so
# the existing entity ids (kit_edits/01 + 04 reference them) do not move; the size within the class is picked from a hash
# of the entity id, weighted like vanilla's own use (kit counts: small_1 114, medium_1 258, medium_2 52 | large_1 218,
# large_2 375).
POPLAR_CLASS = {0: (("small_1", 114), ("medium_1", 258), ("medium_2", 52)), 1: (("large_1", 218), ("large_2", 375))}
POPLAR_FMT = M + "vegetation/arid/arid_tree_poplar_%s%s.wsmodel"       # % ("" | "spring_" ..., size)
SEASON_VARIANTS = ("spring", "harvest", "autumn", "winter")             # the base model carries season_summer
# 2026-10-04: the cold peaks / ridges use shaders/rigid_detail_map_terrain_blend_with_LF_offset (the game adds the lf
# ground to every vertex), so their stored y is an OFFSET above the terrain, not an absolute height. Offsets in model
# units x scale = the values of kit_edits/01_sink_floating_mountains.json (47 north_dress peaks / ridges, checked
# seated in game 2026-10-04: peak -4.32 x scale, ridge -2.00 x scale). All other props (rocks, temperate_mt_*,
# trees, walls) keep absolute y (rigid_detail_map_campaign_shroud etc.).
LF_OFFSET = {M + "mountains/cold/cold_peak_1.wsmodel": -4.32, M + "mountains/cold/cold_ridge_small_1.wsmodel": -2.00}
# 2026-10-04 polish M3(b) "korea_ridges": Korea / NE impassable mountain hexes get the ridge / peak + rock-outcrop
# routine. Temperate hexes: vanilla's temperate mountain meshes (absolute y, rigid_detail_map_campaign_shroud; vanilla
# scale 0.44-0.69, seated with korea_ref/vanilla_sink.json); cold hexes: the cold ridge / peak (LF offset).
KOREA_MTN = [M + "mountains/temperate/temperate_mt_%d.wsmodel" % i for i in (1, 2, 3, 4)]
KOREA_MTN_SCALE = (0.40, 0.58)
KOREA_MTN_PER_IMP = 1 / 100            # ~1 mountain prop per 100 impassable hexes (proposal M3b)
KOREA_ROCK_PER_LAND = 1.9 / 1000       # vanilla temperate rocks per land hex (props_density: 1.9 / 1000)
KOREA_SPACING = 4                      # hexes between Korea mountain sites
# 2026-10-04 polish M5: np_new (west / north padding) ridges within NP_NEAR hexes of playable land, at the np_old density
NP_PER_IMP, NP_NEAR, NP_SPACING = 1.3 / 1000, 25, 5
NP_EXTRA_SPACING_FROM_PLAN = 6         # hexes to keep from the steppe / Hexi plans' own ridge / peak sites
FIR = [M + "vegetation/cold/cold_tree_fir_medium_1.wsmodel"]
RIDGE = [M + "mountains/cold/cold_ridge_small_1.wsmodel"]
PEAK = [M + "mountains/cold/cold_peak_1.wsmodel", M + "mountains/cold/cold_ridge_small_1.wsmodel"]
# 2026-10-04 (user: "make it look like the rest of the wall"): the intact Great Wall kit, as vanilla's own line uses,
# instead of the broken pieces (which read as a row of rock mounds). Straights run 0..4 along local +x (0.84 world at
# scale 0.21); the _up piece rises 2 (0.42 world) over the same run, for slopes.
GW = M + "area_of_interest/great_wall/"
WALL, WALL_UP, TOWER = GW + "great_wall_straight.rigid_model_v2", GW + "great_wall_straight_up.rigid_model_v2", GW + "great_wall_tower_1.rigid_model_v2"
SCALE = {"tent": 0.24, "rock": 0.42, "scree": 0.52, "poplar": 0.32, "fir": 0.46, "ridge": 0.10, "peak": 0.12, "wall": 0.21}


# ---------------------------------------------------------------- climate (one-off)
def climate():
    if MARK.exists(): print("north climate already applied", MARK.read_text()); return
    import town_fix as T, hexmap
    HEX = HERE / "hex" / "map.hex"
    b, P, w, h, g, f, names = T.load(str(HEX))
    cl = hexmap.load(str(HEX))["lists"]["climates"]
    ts = time.strftime("%Y%m%d_%H%M%S")
    shutil.copy2(HEX, HERE / "hex" / f"map_pre_north_dress_{ts}.hex")
    want = np.full((h, w), -1, np.int16)
    for pf in PLANS:
        pl = json.load(open(pf, encoding="utf-8")); cs = pl["climate_suggestion"]
        for r, runs in pl["zone_rle"].items():
            for s, n, z in runs:
                if z in cs and z != "korea_forest": want[int(r), s:s + n] = cl.index(cs[z])
    m = (want >= 0) & (f["terr"] != 1)
    G = g.copy()
    G[..., 7] = np.where(m, ((want + 1) & 127) << 1, G[..., 7]).astype(np.uint8)
    out = bytearray(b); out[P + 8:P + 8 + 16 * w * h] = G.tobytes()
    out[-4:] = struct.pack("<I", zlib.crc32(bytes(out[:-4])) & 0xFFFFFFFF); HEX.write_bytes(bytes(out))
    bk = HERE / "terrain" / "_pre_north_dress"; bk.mkdir(exist_ok=True)
    for fn, pph in (("climate_map.png", 2), ("climate_map_g.png", 8)):
        p = HERE / "terrain" / fn; shutil.copy2(p, bk / fn)
        a = np.array(Image.open(p).convert("RGB")); Hp, Wp = a.shape[:2]
        yy, xx = np.mgrid[0:Hp, 0:Wp]
        hc = np.clip(xx // pph, 0, w - 1); hr = np.clip((Hp - 1 - yy) // pph, 0, h - 1)
        wz = want[hr, hc]; mm = m[hr, hc]
        for ci, name in enumerate(cl):
            if name in CLIM_COL: a[mm & (wz == ci)] = CLIM_COL[name]
        Image.fromarray(a).save(p)
        print("  climate raster", fn, int(mm.sum()), "px")
    MARK.write_text(json.dumps(dict(ts=ts, hexes=int(m.sum()))))
    print(f"north climate: {int(m.sum())} hexes re-zoned")


# ---------------------------------------------------------------- props (build rule)
def _rot(rot):
    """rotation attribute: a yaw (degrees) or a full (x, y, z) Euler triple (TerryTransform order)."""
    return f"0 {rot:.2f} 0" if not isinstance(rot, tuple) else " ".join(f"{a:.3f}" for a in rot)


def _scl(s):
    return f"{s:.5f} {s:.5f} {s:.5f}" if not isinstance(s, tuple) else " ".join(f"{a:.5f}" for a in s)


def _euler(X, Y):
    """Euler (x, y, z) degrees whose rotation maps local +x to X and local +y to (Y made orthogonal to X), in the
    convention of TerryClone's TerryTransform.RotationMatrix (Blender eul_to_mat3)."""
    X = np.asarray(X, float); X = X / np.linalg.norm(X)
    Y = np.asarray(Y, float); Y = Y - X * (Y @ X); Y = Y / np.linalg.norm(Y)
    Z = np.cross(X, Y)
    m = np.column_stack([X, Y, Z])                 # columns = images of the local axes
    j = math.asin(max(-1.0, min(1.0, -m[2, 0])))
    i = math.atan2(m[2, 1], m[2, 2])
    h = math.atan2(m[1, 0], m[0, 0])
    return (math.degrees(i), math.degrees(j), math.degrees(h))


def _ent(eid, model, x, y, z, rot, s, clamp, season="", unseen=False):
    # season: ECCampaignProperties season_mask ("" = all seasons; poplar sets use season_summer / season_spring ...)
    # unseen: visible_in_unseen_shroud (vanilla's landscape mountains / np_old peaks mostly "true")
    return (f'<entity id="{eid}">\n      <ECPropMesh/>\n      <ECMesh model_path="{model}" animation_path=""/>\n'
            '      <ECMeshRenderSettings inherit_from_parent="false" cast_shadow="true" alpha="1" tint_colour="255 255 255 255" '
            'set_tint_colour_from_colour_overlay="false" faction_colour="255 255 255 255"/>\n'
            '      <ECPropHeightPatch has_height_patch="false" apply_height_patch="false"/>\n'
            '      <ECCampaignProperties visible_inside_snow_region="true" visible_outside_snow_region="true" '
            f'visible_inside_destruction_region="true" visible_outside_destruction_region="true" visible_in_unseen_shroud="{"true" if unseen else "false"}" '
            f'visible_in_seen_shroud="true" no_culling="false" culture_mask="" season_mask="{season}"/>\n'
            '      <ECDLCMask type="Exclude" mask=""/>\n'
            f'      <ECTransform position="{x:.4f} {y:.5f} {z:.4f}" rotation="{_rot(rot)}" scale="{_scl(s)}" pivot="0 0 0"/>\n'
            f'      {clamp}\n    </entity>')


def _hid(tag, used):
    """2026-10-04: deterministic id for the entities added by the polish (seasonal variants, korea_ridges, np_new
    ridges): '0e' (layer_sort's north_dress prefix) + md5 of a stable tag. Independent of the main rng stream, so neither
    these ids nor the old ones move when a rule's count changes. Re-hashed on a collision with any id in the project."""
    import hashlib
    k = tag
    while True:
        e = "0e" + hashlib.md5(k.encode()).hexdigest()[:13]
        if e not in used: used.add(e); return e
        k += "#"


def _kit_deleted():
    """0e ids that kit_edits/*.json deletes (north_dress trees on town hexes, op 04): their base entity is still made
    (so the replay stays the same) but no seasonal variants, which the replay would not know to delete."""
    out = set()
    for p in (HERE / "kit_edits").glob("*.json"):
        try: ops = json.load(open(p, encoding="utf-8"))
        except Exception: continue
        out |= {o["id"] for o in ops if isinstance(o, dict) and o.get("op") == "delete" and str(o.get("id", "")).startswith("0e")}
    return out


def add(out_dir, map_name="3k_dlc07_main_map"):
    import town_props_scan, prop_seat, prop_removals, hashlib
    import town_fix as T
    from hexgrid import neighbour_arrays, nearest_hex
    from scipy import ndimage as ndi
    out_dir = Path(out_dir)
    terry = open(out_dir / f"{map_name}.terry", encoding="utf-8", errors="replace").read()
    used = set(re.findall(r'id="([0-9a-f]+)"', terry))
    host = None
    for p in sorted(out_dir.glob(f"{map_name}.*.layer")):
        if p.name.split(".")[-2] in used and "3k_main_reg_non_playable" in open(p, encoding="utf-8").read(400):
            host = p; break
    if host is None:
        host = next(p for p in sorted(out_dir.glob(f"{map_name}.*.layer")) if p.name.split(".")[-2] in used)
    t = open(host, encoding="utf-8").read()
    cm = re.search(r"<ECTerrainClamp[^>]*/>", t)
    clamp = cm.group(0) if cm else '<ECTerrainClamp active="false" clamp_to_sea_level="false" terrain_oriented="false" fit_height_to_terrain="false"/>'
    # every entity id already in the project (all layers): the polish's hashed ids must not collide with any of them
    all_ids = set(used)
    for p in out_dir.glob(f"{map_name}.*.layer"):
        all_ids |= set(re.findall(r'<entity id="([0-9a-f]+)"', open(p, encoding="utf-8", errors="replace").read()))
    kit_del = _kit_deleted()
    hgt = np.array(Image.open(HEIGHT)); H8, W8 = hgt.shape
    from hexgrid import HX, HZ
    def ground(x, z):
        c = x / HX; r = z / HZ
        px = int(round(c * 8 + 4)); py = int(round(H8 - 1 - (r * 8 + 4)))
        return float(hgt[min(max(py, 0), H8 - 1), min(max(px, 0), W8 - 1)]) * U2W - W0
    # map.hex: river hexes (2026-10-04 M2: no groves on rivers), all towns + roads (korea_ridges / np_new keep-clear:
    # town_props_scan only guards the NEW towns, the Korea towns are stock 190E ones)
    _, _, w, h, _, f, names = T.load(str(HERE / "hex" / "map.hex")); NA = neighbour_arrays(h, w)
    river = f["river"] > 0
    for d, (nr, nc, v) in enumerate(NA):
        m_ = v & (((f["river"] >> d) & 1) > 0); river[nr[m_], nc[m_]] = True
    land = f["terr"] == 0; imp = (f["imp"] > 0) & land
    road = (f["road"] > 0) | (f["bridge"] > 0)
    town_all = (f["slot"] >= 0) | (f["sprawl"] > 0)
    dt_town = ndi.distance_transform_edt(~town_all, sampling=(HZ, HX))          # world units to the nearest town hex
    def hex_of(x, z):
        c_, r_ = nearest_hex(np.array([x]), np.array([z]), w, h); return int(r_[0]), int(c_[0])
    rng = np.random.default_rng(31)
    ents, skipped, counts = [], 0, {}
    n_river = n_var = 0
    def put(model, x, z, s, rot=None, kind="x", R=None, eid=None, unseen=False, guard=False, y=None):
        """R / eid: the polish rules pass their own rng and a hashed id (the main rng stream - and so every old id - is
        consumed exactly as before: one uniform for the yaw, one integer for the id, per put). guard: also keep clear of
        every town (not only the new ones) and of roads. Returns True when placed."""
        nonlocal skipped, n_river, n_var
        R_ = rng if R is None else R
        rot = float(R_.uniform(0, 360)) if rot is None else rot
        if eid is None: eid = "%015x" % int(rng.integers(0x0e00000000000000 >> 4, 0x0effffffffffffff >> 4))
        size = None
        if isinstance(model, tuple):                               # ("poplar", class 0 medium / 1 large) -> vanilla size
            sizes = POPLAR_CLASS[model[1]]; hv = int(hashlib.md5(eid.encode()).hexdigest()[:8], 16) % sum(n for _, n in sizes)
            for size, n in sizes:
                if hv < n: break
                hv -= n
            model = POPLAR_FMT % ("", size)
        e = _ent(eid, model, x, ground(x, z) if y is None else y, z, rot, s, clamp)
        if model in LF_OFFSET:                                     # LF-offset shader: y is the offset above the ground
            e = _ent(eid, model, x, LF_OFFSET[model] * s, z, rot, s, clamp)
        elif prop_seat.is_mountain(e):                             # 2026-10-03: base on the lowest ground under it
            e = _ent(eid, model, x, prop_seat.seat_y(x, z, prop_seat.radius(e), model, s), z, rot, s, clamp)
        hit, _ = town_props_scan.covered(e, x, z)
        if hit or prop_removals.removed(e, x, z): skipped += 1; return False
        r_, c_ = hex_of(x, z)
        if kind == "tree" and river[r_, c_]: n_river += 1; return False     # 2026-10-04 M2: groves off river hexes
        if guard and (road[r_, c_] or not land[r_, c_] or dt_town[r_, c_] < prop_seat.radius(e) * town_props_scan.REACH + HX):
            skipped += 1; return False
        if unseen or size: e = re.sub(r'visible_in_unseen_shroud="false"', 'visible_in_unseen_shroud="%s"' % ("true" if unseen else "false"), e)
        if size:                                                   # M2: the vanilla 5-entity seasonal set
            e = e.replace('season_mask=""', 'season_mask="season_summer"')
        ents.append(e); counts[kind] = counts.get(kind, 0) + 1; all_ids.add(eid)
        if size and eid not in kit_del:
            for sn in SEASON_VARIANTS:
                ve = e.replace(f'<entity id="{eid}">', f'<entity id="{_hid("season:%s:%s" % (eid, sn), all_ids)}">', 1)
                ve = ve.replace(POPLAR_FMT % ("", size), POPLAR_FMT % (sn + "_", size)).replace('season_mask="season_summer"', f'season_mask="season_{sn}"')
                ents.append(ve); n_var += 1
        return True
    jit = lambda s: s * float(rng.uniform(0.85, 1.15))
    plan_mtn = []                                                  # the plans' ridge / peak sites (np_new keeps clear)
    for pf in PLANS:
        pl = json.load(open(pf, encoding="utf-8"))
        wall = []
        for st in pl["sites"]:
            k, x0, z0 = st["kind"], st["x"], st["z"]
            if k == "camp": continue                                # 2026-10-03: big nomad camps come from village_dress.py
            # 2026-10-03 (vanilla standard): groves / spruce / outcrops get a satellite clump 1.0-1.8 units off
            for rep in range(2 if k in ("grove", "spruce", "outcrop") else 1):
                if rep: aa, dd = rng.uniform(0, 2 * math.pi), rng.uniform(1.0, 1.8); x, z = x0 + dd * math.cos(aa), z0 + dd * math.sin(aa)
                else: x, z = x0, z0
                if k == "outcrop":
                    for _ in range(int(rng.integers(1, 4))):
                        a, d = rng.uniform(0, 2 * math.pi), rng.uniform(0, 0.5)
                        mdl = ROCKS[int(rng.integers(0, len(ROCKS)))]
                        put(mdl, x + d * math.cos(a), z + d * math.sin(a), jit(SCALE["scree" if "scree" in mdl else "rock"]), kind="rock")
                elif k in ("grove", "spruce"):
                    for _ in range(int(rng.integers(4, 9))):
                        a, d = rng.uniform(0, 2 * math.pi), rng.uniform(0, 0.8)
                        if k == "spruce": put(FIR[0], x + d * math.cos(a), z + d * math.sin(a), jit(SCALE["fir"]), kind="tree")
                        # M2: same rng draw as before (class 0 / 1), the vanilla size + seasonal set are resolved in put()
                        else: put(("poplar", int(rng.integers(0, 2))), x + d * math.cos(a), z + d * math.sin(a), jit(SCALE["poplar"]), kind="tree")
            x, z = x0, z0
            if k in ("camp", "outcrop", "grove", "spruce"): continue
            if k in ("ridge_rock", "ridge_forest"):
                put(RIDGE[0], x, z, jit(SCALE["ridge"] * 1.2), kind="ridge"); plan_mtn.append((x, z))
                if k == "ridge_rock": put(ROCKS[0], x + 0.8, z - 0.6, jit(SCALE["rock"]), kind="rock")
            elif k == "peak":
                mdl = PEAK[int(rng.integers(0, len(PEAK)))]
                put(mdl, x, z, jit(SCALE["peak"] if "peak" in mdl else SCALE["ridge"] * 1.3), kind="peak"); plan_mtn.append((x, z))
            elif k == "wall":
                wall.append((x, z))
        # the Han wall: intact straights end to end along each leg (2026-10-04 fix after the in-game check): n =
        # round(L / piece) pieces stretched along their length to fill the leg exactly (no overshoot past the corner
        # towers), each tilted from the ground at its start to the ground at its end (instead of the ramp-like _up
        # piece): local +x along the slope, local +z kept horizontal (north_dress._euler, TerryTransform order).
        # Hashed ids: the main rng stream (every other generated id) is untouched.
        def wid(*k): return "0e" + hashlib.md5(("hanwall:%s" % (k,)).encode()).hexdigest()[:13]
        piece = 4.0 * SCALE["wall"]
        for li, ((x0, z0), (x1, z1)) in enumerate(zip(wall, wall[1:])):
            L = math.hypot(x1 - x0, z1 - z0)
            if L > 12: continue                                     # a gap in the line (desert edge breaks): no wall across
            ux, uz = (x1 - x0) / L, (z1 - z0) / L
            n = max(1, int(round(L / piece)))
            step = L / n
            for i in range(n):
                sx, sz = x0 + ux * step * i, z0 + uz * step * i
                ga, gb = ground(sx, sz), ground(sx + ux * step, sz + uz * step)
                X = (ux * step, gb - ga, uz * step)
                length = math.sqrt(step * step + (gb - ga) ** 2)
                rot = _euler(X, (0.0, 1.0, 0.0))
                put(WALL, sx, sz, (length / 4.0, SCALE["wall"], SCALE["wall"]), rot=rot, kind="wall", eid=wid(li, i), y=ga)
        for ti, (x, z) in enumerate(wall): put(TOWER, x, z, SCALE["wall"], kind="tower", eid=wid("tower", ti))
    n_plan = len(ents)

    # ------------------------------------------------ 2026-10-04 polish: korea_ridges (M3b) + np_new ridges (M5)
    # own rng (seeded per rule) + hashed ids: the plans' entities above are untouched by these rules
    rows, cols = np.mgrid[0:h, 0:w]
    hx_, hz_ = cols * HX, rows * HZ + (cols & 1) * HZ / 2
    py_ = np.clip(np.rint(H8 - 1 - (hz_ / HZ * 8 + 4)).astype(int), 0, H8 - 1); px_ = np.clip(np.rint(hx_ / HX * 8 + 4).astype(int), 0, W8 - 1)
    hh = hgt[py_, px_].astype(np.float32) * U2W - W0                                # ground at each hex centre
    prom = hh - ndi.uniform_filter(hh, 9, mode="nearest")                           # local prominence: ridge / peak tops
    def sites(cand, n, spacing, R, taken):
        """Up to n hexes of cand, highest prominence first (plus a little noise), >= spacing hexes apart."""
        rr, cc = np.nonzero(cand & (prom > 0) & ~taken)
        order = np.argsort(-(prom[rr, cc] + R.uniform(0, 0.25, len(rr))))
        for i in order:
            r, c = int(rr[i]), int(cc[i])
            if taken[r, c]: continue
            yield r, c
            r0, r1, c0, c1 = max(0, r - spacing), min(h, r + spacing + 1), max(0, c - spacing), min(w, c + spacing + 1)
            taken[r0:r1, c0:c1] |= np.hypot(cols[r0:r1, c0:c1] - c, (rows[r0:r1, c0:c1] - r) * HZ / HX) <= spacing
    def outcrop(x, z, R, tag, kind, unseen):
        """1-3 rocks round (x, z) - the plans' outcrop routine."""
        n = 0
        for j in range(int(R.integers(1, 4))):
            a, d = R.uniform(0, 2 * math.pi), R.uniform(0, 0.5)
            mdl = ROCKS[int(R.integers(0, len(ROCKS)))]
            n += put(mdl, x + d * math.cos(a), z + d * math.sin(a), SCALE["scree" if "scree" in mdl else "rock"] * float(R.uniform(0.85, 1.15)),
                     kind=kind, R=R, eid=_hid(f"{tag}:rock{j}", all_ids), unseen=unseen, guard=True)
        return n
    def ridge_or_peak(r, c, R, tag, kind, unseen, temperate):
        x, z = float(hx_[r, c]), float(hz_[r, c])
        if temperate:                                               # Korea temperate: vanilla's temperate mountains
            mdl = KOREA_MTN[int(R.integers(0, len(KOREA_MTN)))]; s = float(R.uniform(*KOREA_MTN_SCALE))
        elif R.random() < 0.5: mdl = PEAK[0]; s = SCALE["peak"] * float(R.uniform(0.85, 1.15))
        else: mdl = RIDGE[0]; s = SCALE["ridge"] * 1.2 * float(R.uniform(0.85, 1.15))
        ok = put(mdl, x, z, s, kind=kind, R=R, eid=_hid(f"{tag}:mtn", all_ids), unseen=unseen, guard=True)
        nr = 0
        if ok and R.random() < 0.5:                                 # half the sites: a rock outcrop on the flank
            a = R.uniform(0, 2 * math.pi); d = prop_seat.radius(_ent("x", mdl, 0, 0, 0, 0, s, "")) * 0.6 + 0.4
            nr = outcrop(x + d * math.cos(a), z + d * math.sin(a), R, tag, kind + "_rock", unseen)
        return ok, nr
    # korea_ne = ironic_region_* that the proposal does not count as hexi / nomad
    kor_ids = [i for i, n in enumerate(names) if n.startswith("ironic_region_")
               and not any(n.startswith("ironic_region_" + k) for k in ("hanyang", "xi_", "wuwei", "xiping", "wuyuan"))]
    kor = np.isin(f["region"], kor_ids) & land
    R = np.random.default_rng(190413)
    taken = np.zeros((h, w), bool)
    n_imp_k = int((kor & imp).sum()); want = int(round(n_imp_k * KOREA_MTN_PER_IMP)); got = rk = 0
    for r, c in sites(kor & imp, 10 ** 9, KOREA_SPACING, R, taken):
        if got >= want: break
        ok, nr = ridge_or_peak(r, c, R, f"korea_ridge:{r}:{c}", "korea_mtn", True, int(f["climate"][r, c]) != 1)
        got += ok; rk += nr
    # foothill outcrops up to vanilla temperate's rock density: passable Korea land within 2 hexes of the mountains
    foot = kor & ~imp & ~road & ~river & ~town_all
    near_imp = ndi.binary_dilation(kor & imp, iterations=2)
    want_r = int(round(int(kor.sum()) * KOREA_ROCK_PER_LAND)) - rk
    taken2 = np.zeros((h, w), bool)
    for r, c in sites(foot & near_imp, 10 ** 9, 3, R, taken2):
        if want_r <= 0: break
        want_r -= outcrop(float(hx_[r, c]), float(hz_[r, c]), R, f"korea_outcrop:{r}:{c}", "korea_rock", True)
    print(f"north_dress korea_ridges: {got}/{want} mountain sites on {n_imp_k} impassable hexes, {counts.get('korea_mtn_rock', 0) + counts.get('korea_rock', 0)} rocks")
    # np_new: the west / north padding (terrain/pad_mask.png) ridges within NP_NEAR hexes of playable land
    pm = np.array(Image.open(HERE / "terrain" / "pad_mask.png")); Hp = pm.shape[0]
    if pm.ndim == 3: pm = pm[..., 0]
    pxx = np.clip(8 * cols + 4, 0, pm.shape[1] - 1); pyy = np.clip(Hp - 8 * rows - 4 - 4 * (cols & 1), 0, Hp - 1)
    pad = pm[pyy, pxx] > 0
    npk = names.index("3k_main_reg_non_playable")
    nonp = (f["region"] == npk) | (f["region"] < 0) | np.isin(f["region"], [i for i, n in enumerate(names) if n.startswith("ironic_sea_")])
    playable = land & ~nonp
    near = ndi.distance_transform_edt(~playable) <= NP_NEAR
    npn = (f["region"] == npk) & pad & imp & near
    R = np.random.default_rng(190415)
    taken = np.zeros((h, w), bool)
    for (x, z) in plan_mtn:                                         # keep off the plans' own ridges / peaks
        r, c = hex_of(x, z); s_ = NP_EXTRA_SPACING_FROM_PLAN
        r0, r1, c0, c1 = max(0, r - s_), min(h, r + s_ + 1), max(0, c - s_), min(w, c + s_ + 1); taken[r0:r1, c0:c1] = True
    want = int(round(int(npn.sum()) * NP_PER_IMP)); got = 0
    for r, c in sites(npn, 10 ** 9, NP_SPACING, R, taken):
        if got >= want: break
        got += ridge_or_peak(r, c, R, f"np_new_ridge:{r}:{c}", "np_mtn", True, False)[0]
    print(f"north_dress np_new ridges: {got}/{want} mountain sites on {int(npn.sum())} impassable padding hexes within {NP_NEAR} of playable land")
    i = t.rindex("</entities>")
    t = t[:i] + "\n    " + "\n    ".join(ents) + "\n  " + t[i:]
    open(host, "w", encoding="utf-8", newline="").write(t)
    print(f"north_dress: {len(ents)} props {counts}; {skipped} skipped (would cover a town / road), {n_river} grove trees off river hexes, "
          f"{n_var} poplar season variants, {len(ents) - n_plan} polish-rule props -> {host.name}")
    return len(ents)


if __name__ == "__main__":
    if "--climate" in sys.argv: climate()
