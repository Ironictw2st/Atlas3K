#!/usr/bin/env python3
"""Build the Guandu map.hex properly at scale S (default 2.25), instead of block-replicating records.

 1. Crop vanilla at 1x and clean it (crop_scale_map_hex: fix_orphans, frame_edges, drop_broken_bridges).
 2. Area layers (terrain, region, impassable, ground type, attrition, climate, AOI, restriction): every new hex takes
    the values of the old hex nearest to its world position mapped back through the scale (same mapping as the
    terrain rasters). Beach/cliff are kept aside and recomputed in step 6.
 3. Settlements: each connected blob of town-slot/sprawl hexes is pasted at its ORIGINAL size (main slot must stay
    19/16 hexes), centred on its anchor hex's scaled position. Props/settlement models stay life-size the same way.
 4. Roads, rivers, trade routes: every old edge is redrawn as a hex line between the mapped end hexes, so lines stay
    one hex wide. Roads/rivers only on non-sea hexes; bridges become the sea hexes on the line between the road ends
    either side of an old bridge.
 5. Trade route masks = adjacency of trade route hexes (CAIME CalculateTradeRouteEdgeMasks).
 6. Beach/cliff: only land hexes touching sea keep the type of their source hex; roads on a coast hex that do not lead
    to a bridge drop the beach/cliff.
 7. Region edge masks: neighbours in a different region (matches vanilla exactly).
"""
import argparse, struct, sys, zlib
from collections import deque
from pathlib import Path
import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import crop_scale_map_hex as C
from hexgrid import HX, HZ, neighbour, neighbour_arrays, nearest_hex, centre, to_cube, from_cube, hex_line, direction_between


# Provinces left out of the campaign on purpose (made non-playable like the south): the Sichuan basin.
DROP_PROVINCES = ["3k_main_province_baxi", "3k_main_province_bajun", "3k_main_province_chengdu",
                  "3k_main_province_jiangyang"]
R2P_XML = r"C:/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/assembly_kit/raw_data/db/region_to_province_junctions.xml"


def province_map():
    """region -> (province, is_capital) from the AK db."""
    import re
    s = open(R2P_XML, encoding="utf-8").read()
    g = lambda r, f: re.search(rf"<{f}>([^<]*)</{f}>", r).group(1)
    return {g(r, "region"): (g(r, "province"), g(r, "is_capital") in ("1", "true"))
            for r in re.findall(r"<region_to_province_junctions[ >].*?</region_to_province_junctions>", s, re.S)}


def unpack(g):
    g = g.astype(np.int32)
    return dict(
        terr=g[..., 0] & 3, region=((g[..., 1] << 5) | (g[..., 0] >> 3)) - 1, imp=(g[..., 2] >> 3) & 1,
        slot=(g[..., 2] >> 4) - 1, sprawl=g[..., 3] & 1, road=(g[..., 3] >> 1) & 63, bridge=(g[..., 3] >> 7) & 1,
        river=g[..., 4] & 63, trade=((g[..., 5] & 15) << 2) | (g[..., 4] >> 6), ground=(((g[..., 6] & 7) << 4) | (g[..., 5] >> 4)) - 1,
        attr=(g[..., 6] >> 3) - 1, climate=(g[..., 7] >> 1) - 1, aoi=(g[..., 8] >> 3) - 1, restr=g[..., 8] & 7, b9=g[..., 9])


def pack(f):
    h, w = f["terr"].shape
    out = np.zeros((h, w, 16), np.uint8)
    reg, gt = f["region"] + 1, f["ground"] + 1
    out[..., 0] = ((reg & 0x1F) << 3) | (f["terr"] & 3)
    out[..., 1] = (reg >> 5) & 0xFF
    out[..., 2] = (((f["slot"] + 1) & 15) << 4) | ((f["imp"] & 1) << 3)
    out[..., 3] = ((f["bridge"] & 1) << 7) | ((f["road"] & 63) << 1) | (f["sprawl"] & 1)
    out[..., 4] = ((f["trade"] & 3) << 6) | (f["river"] & 63)
    out[..., 5] = ((gt & 15) << 4) | ((f["trade"] >> 2) & 15)
    out[..., 6] = (((f["attr"] + 1) & 31) << 3) | ((gt >> 4) & 7)
    out[..., 7] = ((f["climate"] + 1) & 127) << 1
    out[..., 8] = (((f["aoi"] + 1) & 31) << 3) | (f["restr"] & 7)
    out[..., 9] = f["b9"]            # reserved for CAIME, but set on 855 vanilla hexes: carried through
    out[..., 15] = (f["redge"] & 63) << 2
    return out


def replace_region_lists(prefix, land, sea):
    """Swap the land/sea region name lists in a map.hex header prefix; every other byte is kept.
    Layout: 4 x u32, u32-length game name, u32-length map name, then the land and sea lists
    (u32 count, then u32-length strings), then the remaining lists and colour tables."""
    p = 16
    for _ in range(2): p += 4 + struct.unpack_from("<I", prefix, p)[0]
    start = p
    for _ in range(2):
        n = struct.unpack_from("<I", prefix, p)[0]; p += 4
        for _ in range(n): p += 4 + struct.unpack_from("<I", prefix, p)[0]
    def enc(names):
        return struct.pack("<I", len(names)) + b"".join(struct.pack("<I", len(s.encode())) + s.encode() for s in names)
    return prefix[:start] + enc(land) + enc(sea) + prefix[p:]


def components(mask):
    """Connected components (6-neighbour) of a boolean hex mask -> list of [(col,row), ...]."""
    h, w = mask.shape; seen = np.zeros_like(mask); comps = []
    for r0, c0 in zip(*np.nonzero(mask)):
        if seen[r0, c0]: continue
        comp, q = [], deque([(c0, r0)]); seen[r0, c0] = True
        while q:
            c, r = q.popleft(); comp.append((c, r))
            for d in range(6):
                nc, nr = neighbour(c, r, d)
                if 0 <= nc < w and 0 <= nr < h and mask[nr, nc] and not seen[nr, nc]:
                    seen[nr, nc] = True; q.append((nc, nr))
        comps.append(comp)
    return comps


def rebuild(scale=2.25, name="3k_guandu_map", log=print, src_path=None, mapping=None, crop=True, guandu_drops=True, fill_holes=False,
            padding_sea=None):
    """scale: uniform upscale of the Guandu crop (default build). mapping: an object with W, H, fwd_world(x, z) and
    inv_world(x, z) (world units of the source grid <-> the new grid) - used instead of the uniform scale, e.g. the
    190E Central-Plains warp. crop: take the Guandu box (C.COL0..) out of the source first. guandu_drops: the
    south-of-the-Yangtze / Sichuan drops that only apply to the Guandu campaign."""
    src_path = src_path or C.VANILLA
    src = Path(src_path).read_bytes()
    sys.path.insert(0, str(HERE.parent)); import hexmap
    names = hexmap.load(src_path)["lists"]; land_names = names["land_regions"]; names = names["land_regions"] + names["sea_regions"]
    non_playable = names.index("3k_main_reg_non_playable") if "3k_main_reg_non_playable" in names else None
    P, w, h = C.locate_dims(src)
    grid = np.frombuffer(src, np.uint8, 16 * w * h, P + 8).reshape(h, w, 16)
    if crop:
        raw = grid[C.ROW0:C.ROW1, C.COL0:C.COL1]
        crop, orphans = C.fix_orphans(grid, raw)
    else:
        raw, crop, orphans = grid, grid.copy(), []
    crop = C.frame_edges(crop)
    crop, nbr = C.drop_broken_bridges(raw, crop)
    log(f"1x clean: {len(orphans)} cut settlements handed to neighbours, {nbr} bridges removed")
    O = unpack(crop); ch, cw = O["terr"].shape
    if mapping is None:
        NW, NH = C.NW, C.NH                                 # multiples of 4 (see crop_scale_map_hex)
        assert abs(NW / cw - scale) < 0.02 and abs(NH / ch - scale) < 0.02, (NW, NH, scale)
        sx, sz = NW / cw, NH / ch
        fwd = lambda x, z: (x * sx, z * sz)
        inv = lambda x, z: (x / sx, z / sz)
    else:
        NW, NH = mapping.W, mapping.H
        fwd, inv = mapping.fwd_world, mapping.inv_world

    # old <-> new positions (crop col 0 is even, so parity is unchanged by the crop)
    def old_to_new(col, row):
        x, z = centre(np.asarray(col), np.asarray(row))
        X, Z = fwd(x, z)
        return nearest_hex(X, Z, NW, NH)

    # --- 2. area layers ------------------------------------------------------------------------------------
    rows, cols = np.mgrid[0:NH, 0:NW]
    x, z = centre(cols, rows)
    xo, zo = inv(x, z)
    oc, orr = nearest_hex(xo, zo, cw, ch)
    N = {k: v[orr, oc].copy() for k, v in O.items()}
    # hexes whose source lies outside the old grid (padding for new land): non-playable, impassable, no lines
    outside = (xo < -HX / 2) | (xo > (cw - 0.5) * HX) | (zo < -HZ / 2) | (zo > (ch - 0.5) * HZ)
    if mapping is not None and outside.any() and non_playable is not None:
        sea_np_i = names.index("3k_main_sea_non_playable") if "3k_main_sea_non_playable" in names else non_playable
        if padding_sea is not None:              # land/sea of new land from real data (e.g. a DEM), not edge extrusion
            ps = padding_sea(xo[outside], zo[outside])
            known = ps >= 0
            t = N["terr"][outside]; t[known] = np.where(ps[known] == 1, 1, 0); N["terr"][outside] = t
            log(f"padding: land/sea from padding_sea for {int(known.sum())} hexes ({int((ps == 1).sum())} sea)")
        N["region"][outside] = np.where(N["terr"][outside] == 1, sea_np_i, non_playable)
        N["imp"][outside] = 1
        log(f"padding: {int(outside.sum())} hexes outside the source grid made non-playable")
    src_bc = N["terr"].copy()                               # remembered beach/cliff type of the source hex
    N["terr"] = np.where(N["terr"] == 1, 1, 0)
    for k in ("slot",): N[k][:] = -1
    for k in ("sprawl", "road", "bridge", "river", "trade"): N[k][:] = 0

    # --- 3. settlements ------------------------------------------------------------------------------------
    # A settlement = one connected footprint of town-slot/sprawl hexes. It can span regions: a port's water-side
    # slot hexes belong to the neighbouring sea region, so the whole footprint is pasted as one unit.
    blob_mask = (O["slot"] >= 0) | (O["sprawl"] == 1)
    sea_new = N["terr"] == 1                                # sampled water, before any paste
    old2new = {}                                            # old hex -> new hex for hexes inside settlements
    pasted = np.zeros((NH, NW), bool)
    offsets = sorted({(dq, dr) for dq in range(-6, 7) for dr in range(-6, 7) if max(abs(dq), abs(dr), abs(dq + dr)) <= 6},
                     key=lambda o: (max(abs(o[0]), abs(o[1]), abs(o[0] + o[1])), o))
    comps = components(blob_mask); moved = 0; misfit = 0
    for comp in comps:
        def score(p):                                       # same-slot neighbours: 6 = centre of a slot
            c, r = p; s = O["slot"][r, c]; k = 0
            for d in range(6):
                nc, nr = neighbour(c, r, d)
                if s >= 0 and 0 <= nc < cw and 0 <= nr < ch and O["slot"][nr, nc] == s: k += 1
            return k
        cx = np.mean([centre(c, r)[0] for c, r in comp]); cz = np.mean([centre(c, r)[1] for c, r in comp])
        main = [p for p in comp if O["slot"][p[1], p[0]] == 0] or comp
        anchor = max(main, key=lambda p: (score(p), -((centre(*p)[0] - cx) ** 2 + (centre(*p)[1] - cz) ** 2)))
        nac, nar = (int(v) for v in old_to_new(*anchor))
        aq, ar, _ = to_cube(*anchor); bq, br, _ = to_cube(nac, nar)
        rel = [(to_cube(c, r)[0] - aq, to_cube(c, r)[1] - ar, O["terr"][r, c] == 1) for c, r in comp]
        best = None
        for dq, dr in offsets:                              # fit the footprint's land/water to the scaled coast
            bad = 0; ok = True
            for q, r, wet in rel:
                col, row = from_cube(bq + dq + q, br + dr + r)
                if not (0 <= col < NW and 0 <= row < NH) or pasted[row, col]: ok = False; break
                bad += wet != sea_new[row, col]
            if ok and (best is None or bad < best[0]):
                best = (bad, dq, dr)
                if bad == 0: break
        if best is None: continue
        bad, dq, dr = best
        moved += (dq, dr) != (0, 0); misfit += bad > 0
        for (c, r), (q, rr, _) in zip(comp, rel):
            ncol, nrow = from_cube(bq + dq + q, br + dr + rr)
            for k in ("terr", "region", "imp", "slot", "sprawl", "ground", "attr", "climate", "aoi", "restr", "b9"):
                N[k][nrow, ncol] = O[k][r, c]
            src_bc[nrow, ncol] = O["terr"][r, c]
            if N["terr"][nrow, ncol] in (2, 3): N["terr"][nrow, ncol] = 0
            if N["sprawl"][nrow, ncol] or N["slot"][nrow, ncol] >= 0: N["imp"][nrow, ncol] = 0   # towns are passable
            pasted[nrow, ncol] = True
            old2new[(c, r)] = (ncol, nrow)
    log(f"settlements: {len(comps)} pasted at original size ({int(pasted.sum())} hexes); {moved} nudged to fit the coast, "
        f"{misfit} still overlap land/water")

    def m(c, r):
        if (c, r) in old2new: return old2new[(c, r)]
        nc, nr = old_to_new(c, r); return int(nc), int(nr)

    # --- 4. lines --------------------------------------------------------------------------------------------
    def old_edges(mask):
        E = set()
        for r, c in zip(*np.nonzero(mask)):
            for d in range(6):
                if (mask[r, c] >> d) & 1:
                    nc, nr = neighbour(c, r, d)
                    if 0 <= nc < cw and 0 <= nr < ch and (mask[nr, nc] >> ((d + 3) % 6)) & 1:
                        E.add(tuple(sorted(((c, r), (nc, nr)))))
        return E

    sea = N["terr"] == 1

    def draw(edges, field, allow):
        for a, b in edges:
            path = hex_line(m(*a), m(*b))
            for p, q in zip(path, path[1:]):
                if not (allow(p) and allow(q)) or p == q: continue
                d = direction_between(p, q)
                N[field][p[1], p[0]] |= 1 << d; N[field][q[1], q[0]] |= 1 << ((d + 3) % 6)

    land = lambda p: not sea[p[1], p[0]]
    draw(old_edges(O["road"]), "road", land)
    N["imp"][(N["road"] > 0) & ~pasted] = 0                 # a road through scaled-up rough ground stays passable
    draw(old_edges(O["river"]), "river", land)

    # bridges: vanilla bridges are standalone sea-hex crossings of a narrow strait (no road on them). Find the
    # land sides touching each old bridge, and mark the sea hexes on the line between the mapped sides.
    nbridge = 0
    for comp in components(O["bridge"] == 1):
        shore = np.zeros((ch, cw), bool)
        for c, r in comp:
            for d in range(6):
                nc, nr = neighbour(c, r, d)
                if 0 <= nc < cw and 0 <= nr < ch and O["terr"][nr, nc] != 1:
                    shore[nr, nc] = True
        sides = components(shore)
        bx = np.mean([centre(c, r)[0] for c, r in comp]); bz = np.mean([centre(c, r)[1] for c, r in comp])
        reps = [min(s, key=lambda p: (centre(*p)[0] - bx) ** 2 + (centre(*p)[1] - bz) ** 2) for s in sides]
        for i in range(len(reps)):
            for j in range(i + 1, len(reps)):
                path = hex_line(m(*reps[i]), m(*reps[j]))
                wet = [p for p in path if sea[p[1], p[0]]]
                if not wet: continue
                for p in wet:
                    N["bridge"][p[1], p[0]] = 1; N["imp"][p[1], p[0]] = 0
                nbridge += 1
    log(f"bridges: {nbridge} crossings redrawn, {int(N['bridge'].sum())} bridge hexes")

    # trade routes: boolean along lines, masks from adjacency
    tr = np.zeros((NH, NW), bool)
    for a, b in old_edges(O["trade"]):
        for p in hex_line(m(*a), m(*b)): tr[p[1], p[0]] = True
    for r, c in zip(*np.nonzero(O["trade"] > 0)):
        p = m(c, r); tr[p[1], p[0]] = True
    NA = neighbour_arrays(NH, NW)
    trade = np.zeros((NH, NW), np.int32)
    for d, (nr, nc, v) in enumerate(NA): trade |= ((tr & v & tr[nr, nc]).astype(np.int32) << d)
    N["trade"] = trade

    # --- 6. beach / cliff --------------------------------------------------------------------------------------
    # Vanilla rule (checked on 3k_dlc07): the coast is exactly one ring - no plain land touches the sea, and every
    # beach/cliff hex touches plain land. BOB's coast tiles are built for that one-hex strip; the 2.25x upscale leaves
    # one-hex "teeth" (coast hexes with ~4 sea and 2 coast neighbours, no land behind) that showed as see-through
    # gaps on beaches in game. So: every land hex touching sea is coast (type from the source hex, else from the
    # neighbouring coast, else beach); teeth without anything on them become sea (record copied from a sea
    # neighbour); repeat until stable.
    coast_type = np.where(np.isin(src_bc, (2, 3)), src_bc, 0)
    for _ in range(4):                                       # spread known coast types to nearby land
        nb = np.zeros((NH, NW), np.int32)
        for nr, nc, v in NA: nb = np.where((nb == 0) & v, coast_type[nr, nc], nb)
        coast_type = np.where(coast_type == 0, nb, coast_type)
    coast_type = np.where(coast_type == 0, 2, coast_type)
    keep = (N["slot"] >= 0) | (N["sprawl"] == 1) | (N["road"] > 0) | (N["river"] > 0) | (N["bridge"] == 1)
    near_bridges = N["bridge"] == 1                          # and the land sides of every bridge (2 rings)
    for _ in range(2):
        grow = near_bridges.copy()
        for nr, nc, v in NA: grow |= v & near_bridges[nr, nc]
        near_bridges = grow
    keep |= near_bridges
    teeth_total = 0
    for _ in range(20):
        touches_sea = np.zeros((NH, NW), bool)
        for nr, nc, v in NA: touches_sea |= v & sea[nr, nc]
        coast = ~sea & touches_sea
        plain = ~sea & ~coast
        n_plain = np.zeros((NH, NW), np.int32)
        for nr, nc, v in NA: n_plain += (v & plain[nr, nc])
        teeth = coast & (n_plain == 0) & ~keep
        if not teeth.any(): break
        teeth_total += int(teeth.sum())
        for d, (nr, nc, v) in enumerate(NA):                  # copy the whole record from a sea neighbour
            take = teeth & v & sea[nr, nc]
            for k in N:
                if k in ("redge",): continue
                N[k][take] = N[k][nr, nc][take]
            teeth &= ~take
        conv = N["terr"] == 1
        conv &= ~sea                                          # just converted: plain sea, no slot/town/lines
        N["slot"][conv] = -1; N["sprawl"][conv] = 0; N["bridge"][conv] = 0; N["road"][conv] = 0; N["river"][conv] = 0
        sea = N["terr"] == 1
    N["terr"] = np.where(sea, 1, np.where(coast, coast_type, 0))
    log(f"coast: {teeth_total} one-hex coast teeth turned to sea")
    near_bridge = np.zeros((NH, NW), bool)
    for nr, nc, v in NA: near_bridge |= v & (N["bridge"][nr, nc] == 1)
    fix = (N["road"] > 0) & np.isin(N["terr"], (2, 3)) & ~near_bridge
    N["terr"][fix] = 0
    log(f"coast: {int((N['terr'] == 2).sum())} beach, {int((N['terr'] == 3).sum())} cliff hexes; {int(fix.sum())} road hexes kept off the beach")

    # --- 6b. regions: one piece each ---------------------------------------------------------------------------
    # the crop can leave a region in several pieces; keep the piece with its settlement (else the largest) and hand
    # the rest to the neighbouring region they share the longest border with (same land/sea class)
    reassigned = 0
    for reg in np.unique(N["region"]):
        if reg < 0: continue
        pieces = components(N["region"] == reg)
        if len(pieces) < 2: continue
        keep = max(pieces, key=lambda p: (any(N["slot"][r, c] >= 0 for c, r in p), len(p)))
        for piece in pieces:
            if piece is keep: continue
            votes = {}
            for c, r in piece:
                for d in range(6):
                    nc, nr = neighbour(c, r, d)
                    if 0 <= nc < NW and 0 <= nr < NH and N["region"][nr, nc] != reg and (N["terr"][nr, nc] == 1) == (N["terr"][r, c] == 1):
                        votes[N["region"][nr, nc]] = votes.get(N["region"][nr, nc], 0) + 1
            if not votes: continue
            new = max(votes, key=votes.get)
            for c, r in piece:
                N["region"][r, c] = new; N["slot"][r, c] = -1; N["sprawl"][r, c] = 0
            reassigned += len(piece)
    log(f"regions: {reassigned} hexes of stray region fragments handed to neighbours")

    # the non-playable filler region must stay fully impassable
    if non_playable is not None:
        np_mask = (N["region"] == non_playable) & (N["terr"] != 1)
        N["imp"][np_mask] = 1; N["road"][np_mask] = 0
    # roads never point into a hex that lost its road
    for d, (nr, nc, v) in enumerate(neighbour_arrays(NH, NW)):
        N["road"] &= ~(((N["road"] >> d) & 1 & ~((N["road"][nr, nc] > 0) & v)) << d)

    # --- 6c. town clearance --------------------------------------------------------------------------------------
    # CAIME: rough ground (impassable/beach/cliff/river) within 2 hexes of a town must touch it, and at most one
    # such area may touch it. Scaling pulls rough ground to odd distances, so clear impassable/beach/cliff in a
    # 2-hex ring round each town, and let the town's sprawl reach one nearby river instead of nearly touching it.
    sprawl = N["sprawl"] == 1
    cleared = extended = 0
    for blob in components(sprawl):
        bset = set(blob); ring1, ring2 = set(), set()
        for c, r in blob:
            for d in range(6):
                p = neighbour(c, r, d)
                if 0 <= p[0] < NW and 0 <= p[1] < NH and p not in bset: ring1.add(p)
        for c, r in ring1:
            for d in range(6):
                p = neighbour(c, r, d)
                if 0 <= p[0] < NW and 0 <= p[1] < NH and p not in bset and p not in ring1: ring2.add(p)
        region = N["region"][blob[0][1], blob[0][0]]
        for c, r in ring1 | ring2:
            if N["terr"][r, c] == 1 or N["region"][r, c] == non_playable: continue
            if N["imp"][r, c]: N["imp"][r, c] = 0; cleared += 1
            # the coast ring stays (vanilla keeps beach/cliff next to its coastal towns too; plain land never
            # touches the sea): only coast hexes that no longer border the sea are cleared
            if N["terr"][r, c] in (2, 3) and not any(0 <= neighbour(c, r, d)[0] < NW and 0 <= neighbour(c, r, d)[1] < NH
                    and N["terr"][neighbour(c, r, d)[1], neighbour(c, r, d)[0]] == 1 for d in range(6)):
                N["terr"][r, c] = 0; cleared += 1
        # what is left near the town is rough ground that cannot be cleared: rivers and the non-playable border
        wet = lambda p: N["terr"][p[1], p[0]] != 1 and (N["river"][p[1], p[0]] > 0 or N["imp"][p[1], p[0]] == 1)
        if any(wet(p) for p in ring1) or not any(wet(p) for p in ring2): continue
        target = next(p for p in sorted(ring2) if wet(p))
        for p in sorted(ring1):                              # a ring-1 hex next to that river hex joins the town
            if N["region"][p[1], p[0]] == region and N["terr"][p[1], p[0]] != 1 and not wet(p) and \
                    any(neighbour(p[0], p[1], d) == target for d in range(6)):
                N["sprawl"][p[1], p[0]] = 1; N["imp"][p[1], p[0]] = 0; extended += 1
                break
    log(f"towns: {cleared} rough hexes cleared round settlements, {extended} towns extended to touch their river")

    # --- 6d. south of the Yangtze -----------------------------------------------------------------------------
    # The campaign is the north: every region lying mostly south of the Yangtze is dropped. Its land becomes
    # impassable 3k_main_reg_non_playable, its water 3k_main_sea_non_playable (impassable). Regions that straddle
    # the river (the East Sea, the lakes) lose only their hexes south of it. The river line is the mean row of the
    # riv_sea_yangtze hexes in each column, interpolated across gaps. Roads, rivers, bridges, trade routes,
    # settlements and sprawl in the dropped area are cleared.
    south_drop = np.zeros((NH, NW), bool)
    yz = np.isin(N["region"], [i for i, n in enumerate(names) if "riv_sea_yangtze" in n])
    if guandu_drops and yz.any() and non_playable is not None and "3k_main_sea_non_playable" in names:
        sea_np = names.index("3k_main_sea_non_playable")
        cols_ = np.arange(NW); line = np.full(NW, np.nan)
        for c in range(NW):
            rr_ = np.nonzero(yz[:, c])[0]
            if len(rr_): line[c] = rr_.mean()
        ok = ~np.isnan(line); line = np.interp(cols_, cols_[ok], line[ok])
        south = (np.arange(NH)[:, None] < line[None, :]) & ~yz
        whole = [i for i in np.unique(N["region"]) if i >= 0 and not yz[N["region"] == i].any()
                 and (south & (N["region"] == i)).sum() > (0.9 if i >= len(land_names) else 0.5) * (N["region"] == i).sum()]
        # provinces dropped on purpose, with the sea regions named after their land regions (x_to_<region>)
        r2p = province_map()
        drop_land = {r for r, (p, _) in r2p.items() if p in DROP_PROVINCES}
        whole += [i for i, n in enumerate(names) if n in drop_land or
                  (i >= len(land_names) and "_to_" in n and any(n.endswith(d.replace("3k_main_", "")) for d in drop_land))]
        # a province without its capital crashes WORLD creation in startpos processing: drop every land region
        # whose province capital is not kept (crop fragments, and what the south line / drops above removed)
        present = set(np.unique(N["region"]).tolist())
        dropped = set(whole) | {i for i in present if i >= 0 and (south & (N["region"] == i)).all()}
        kept = {names[i] for i in present if 0 <= i < len(land_names) and i not in dropped}
        cap = {p: r for r, (p, c) in r2p.items() if c}
        lost = [r for r in kept if r in r2p and cap.get(r2p[r][0]) not in kept]
        whole += [names.index(r) for r in lost]
        log(f"south of the Yangtze: provinces dropped {DROP_PROVINCES}; regions without their province capital: {sorted(lost)}")
        # a kept region's town footprint (slots + sprawl) is never cut by the averaged river line: a settlement slot
        # one hex short (jingzhou_capital lost 1 of its 16 main-slot hexes) has no primary slot and crashes startpos
        town = (N["slot"] >= 0) | (N["sprawl"] == 1)
        south_drop = np.isin(N["region"], whole) | (south & ~town)
        south_drop &= ~np.isin(N["region"], [non_playable, sea_np])
        wet = N["terr"] == 1
        N["region"][south_drop & ~wet] = non_playable
        N["region"][south_drop & wet] = sea_np
        N["imp"][south_drop] = 1
        N["slot"][south_drop] = -1
        for k in ("sprawl", "road", "river", "trade"): N[k][south_drop] = 0
        # bridges: drop any crossing that touches the dropped area
        nb = 0
        for comp in components(N["bridge"] == 1):
            touch = any(south_drop[r, c] or any(0 <= q[0] < NW and 0 <= q[1] < NH and south_drop[q[1], q[0]]
                        for q in (neighbour(c, r, d) for d in range(6))) for c, r in comp)
            if touch:
                for c, r in comp: N["bridge"][r, c] = 0
                nb += 1
        # trade routes: drop route pieces that ran into the dropped area, then rebuild masks from adjacency
        tr = N["trade"] > 0
        for comp in components(tr):
            if any(any(0 <= q[0] < NW and 0 <= q[1] < NH and south_drop[q[1], q[0]]
                       for q in (neighbour(c, r, d) for d in range(6))) for c, r in comp):
                for c, r in comp: tr[r, c] = False
        trade = np.zeros((NH, NW), np.int32)
        for d, (nr, nc, v) in enumerate(NA): trade |= ((tr & v & tr[nr, nc]).astype(np.int32) << d)
        N["trade"] = trade
        for fld in ("road", "river"):                          # no line points into a hex that lost it
            for d, (nr, nc, v) in enumerate(NA):
                N[fld] &= ~(((N[fld] >> d) & 1 & ~((N[fld][nr, nc] > 0) & v)) << d)
        # small non-playable scraps inside the playable land go to the land region they border most (still impassable)
        absorbed = 0
        for piece in components((N["region"] == non_playable) & (N["terr"] != 1)):
            if len(piece) > 5000: continue
            votes = {}
            for c, r in piece:
                for d in range(6):
                    nc, nr = neighbour(c, r, d)
                    if 0 <= nc < NW and 0 <= nr < NH and N["terr"][nr, nc] != 1 and \
                            N["region"][nr, nc] not in (non_playable, -1) and N["region"][nr, nc] < len(land_names):
                        votes[N["region"][nr, nc]] = votes.get(N["region"][nr, nc], 0) + 1
            if votes:
                new = max(votes, key=votes.get)
                for c, r in piece: N["region"][r, c] = new
                absorbed += 1
        log(f"south of the Yangtze: {absorbed} small non-playable scraps absorbed by neighbouring regions")
        log(f"south of the Yangtze: {len(whole)} regions dropped, {int(south_drop.sum())} hexes made non-playable, "
            f"{nb} bridges removed")

    # --- 6e. passable holes -------------------------------------------------------------------------------------
    # CAIME warns about passable pockets fully enclosed by impassable hexes (the warp leaves a few): tiny pockets
    # without a town, road, river or bridge become impassable too.
    if fill_holes:
        passable_land = (N["imp"] == 0) & (N["terr"] != 1)
        filled = 0
        for piece in components(passable_land):
            if len(piece) > 3: continue
            if any(N["slot"][r, c] >= 0 or N["sprawl"][r, c] or N["road"][r, c] or N["river"][r, c] or N["bridge"][r, c]
                   for c, r in piece): continue
            ring = {neighbour(c, r, d) for c, r in piece for d in range(6)} - set(piece)
            if all(0 <= q[0] < NW and 0 <= q[1] < NH and N["imp"][q[1], q[0]] == 1 and N["terr"][q[1], q[0]] != 1 for q in ring):
                for c, r in piece: N["imp"][r, c] = 1
                filled += 1
        log(f"holes: {filled} enclosed passable pockets made impassable")

    # --- 7. region edges ---------------------------------------------------------------------------------------
    redge = np.zeros((NH, NW), np.int32)
    for d, (nr, nc, v) in enumerate(NA): redge |= ((v & (N["region"][nr, nc] != N["region"])).astype(np.int32) << d)
    N["redge"] = redge

    # --- 8. drop regions with no hexes -------------------------------------------------------------------------
    # CA's map-data builder lists every region in the map.hex; a listed region with no hexes (the crop leaves ~150)
    # has no start_pos record and crashes startpos generation. Same as CAIME's Remove region: take the name out of
    # its land/sea list and shift the index of every hex above it down.
    lists = hexmap.load(src_path)["lists"]
    land, sea_names = lists["land_regions"], lists["sea_regions"]
    present = set(np.unique(N["region"]).tolist())
    keep = [i for i in range(len(land) + len(sea_names)) if i in present]
    remap = np.full(len(land) + len(sea_names) + 1, -1, np.int64)
    for new_i, old_i in enumerate(keep): remap[old_i] = new_i
    N["region"] = np.where(N["region"] >= 0, remap[np.clip(N["region"], 0, None)], -1)
    new_land = [land[i] for i in keep if i < len(land)]
    new_sea = [sea_names[i - len(land)] for i in keep if i >= len(land)]
    log(f"regions: kept {len(new_land)} land + {len(new_sea)} sea of {len(land)} + {len(sea_names)} (dropped those with no hexes)")

    out = pack(N)
    prefix = C.rename(src[:P], name) if name else src[:P]
    prefix = replace_region_lists(prefix, new_land, new_sea)
    body = prefix + struct.pack("<II", NW, NH) + out.tobytes()
    res = body + struct.pack("<I", zlib.crc32(body) & 0xFFFFFFFF)
    C.verify(res, (cw, ch), (NW, NH))
    return res, (NW, NH)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=float, default=2.25)
    ap.add_argument("--name", default="3k_guandu_map")
    ap.add_argument("--out", default=str(HERE / "hex"))
    a = ap.parse_args()
    res, (nw, nh) = rebuild(a.scale, a.name)
    out = Path(a.out) / f"map_x{a.scale:g}"; out.mkdir(parents=True, exist_ok=True)
    (out / "map.hex").write_bytes(res)
    print(f"{nw}x{nh} = {nw*nh:,} hexes -> {out / 'map.hex'} ({len(res):,} bytes)")
