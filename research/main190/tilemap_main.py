#!/usr/bin/env python3
"""Build tile_map_rebuilt.png for the warped 190E map (research/guandu/build_tilemap.py generalised to the warp).

 - sea / beach / cliff / cliff ends come from the new map.hex (after korea_fix.py)
 - other land takes the area colour of the 190E hex under its inverse-warped position (clamped at the old edge
   for the west/north padding)
 - line families are 190E edges redrawn as hex lines between the forward-warped ends, never over sea, coast or
   the padding; markers go to the mapped hex; river mouths snap onto the coast; 2-thick overlaps are thinned
 - Korea: the old road lines are dropped and Korea's roads are drawn from the map.hex road bits (korea_fix.py
   rebuilt them) in the family 190E used there, so the visual roads match the logical ones
Output: research/main190/tile_map_rebuilt.png (2 px per hex, QUARTER raster size).
"""
import sys
from collections import deque
from pathlib import Path
import numpy as np
from PIL import Image
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
import hexmap
from build_tilemap import (SEA, BEACH, CLIFF, CLIFF_END, AREAS, RIVER, MOUTH, PAVED, IMPERIAL, TRACK, X_PAVED, X_IMPERIAL, X_TRACK, FAMILIES,
                           MARKERS, KNOWN, rgb, load_hex, area_base, family_edges)
from hexgrid import neighbour, neighbour_arrays, nearest_hex, centre, hex_line
from tilemap_hex import hex_pixels, read_codes
from warp import Warp, WarpMapping, current
from korea_fix import is_korean

# 190E's ORIGINAL tile map (the kit's copy is overwritten by ours at install - never read that one)
OLD_TM = r"Z:/Claude/TerryClone/output/backups/main190_originals_20260929_130639/ak190E_terrain_3k_dlc07_main_map/tile_map.png"
OLD_HEX = r"Z:/Claude/190Expanded/campaign_maps/map.hex"
NEW_HEX = HERE / "hex" / "map.hex"
W0, H0 = 892, 702
MAP = WarpMapping(current())
ROADS = {PAVED, IMPERIAL, TRACK}
MOUNTAIN_AREA = 0x1820c1                               # 190E's western high-mountain tile set
CROSSING = {PAVED: X_PAVED, IMPERIAL: X_IMPERIAL, TRACK: X_TRACK}


def old_codes():
    """Per-hex tile code of the 190E tile map (2x2 block majority), stray colours snapped to the palette."""
    code = read_codes(Image.open(OLD_TM))
    ys, xs = hex_pixels(W0, H0)
    blk = code[ys, xs]
    hc = blk[..., 0]; same = (blk == blk[..., :1]).sum(-1)
    for k in range(1, 4):
        cnt = (blk == blk[..., k:k + 1]).sum(-1)
        hc = np.where(cnt > same, blk[..., k], hc); same = np.maximum(same, cnt)
    pal = sorted(KNOWN); P = np.stack([rgb(c) for c in pal])
    unknown = ~np.isin(hc, pal)
    if unknown.any():
        snap = {int(c): pal[int(np.argmin(((P - rgb(int(c))) ** 2).sum(1)))] for c in np.unique(hc[unknown])}
        hc = np.vectorize(lambda c: snap.get(int(c), int(c)))(hc)
    return hc


def build(log=print):
    N, NW, NH = load_hex(NEW_HEX)
    hc = old_codes()
    base = area_base(hc)
    L = hexmap.load(str(NEW_HEX))["lists"]; names = L["land_regions"] + L["sea_regions"]
    KR = np.isin(N["region"], [i for i, n in enumerate(names) if is_korean(n)])
    NEWR = np.isin(N["region"], [i for i, n in enumerate(names) if n.startswith(("ironic_central_", "ironic_hexi_", "ironic_nomad_"))])
    O, _, _ = load_hex(OLD_HEX)
    Lo = hexmap.load(OLD_HEX)["lists"]; onames = Lo["land_regions"] + Lo["sea_regions"]
    KR_old = np.isin(O["region"], [i for i, n in enumerate(onames) if is_korean(n)])

    def m(c, r):
        x, z = centre(c, r); nx, nz = MAP.fwd_world(x, z)
        nc, nr = nearest_hex(np.array([nx]), np.array([nz]), NW, NH); return int(nc[0]), int(nr[0])

    rows, cols = np.mgrid[0:NH, 0:NW]
    x, z = centre(cols, rows)
    ox, oz = MAP.inv_world(x, z)
    oc, orr = nearest_hex(ox, oz, W0, H0)
    oc, orr = np.clip(oc, 0, W0 - 1), np.clip(orr, 0, H0 - 1)
    padding = (ox < -0.4) | (ox > (W0 - 0.5) * 0.668) | (oz < -0.4) | (oz > (H0 - 0.5) * 0.772)
    # padding: no 190E area underneath - mountain tile set (the one 190E uses for its western ranges) where
    # class_fill.py painted mountain texture (blend 4-7), generic land elsewhere
    from terrain_main import FULL, NWW, NWH
    blend = np.array(Image.open(HERE / "terrain" / "3k_dlc07_main_map.blend.191fd8068da8020.tif"))
    px = np.clip((x / NWW * FULL[0]).astype(int), 0, FULL[0] - 1); py = np.clip(((1 - z / NWH) * FULL[1]).astype(int), 0, FULL[1] - 1)
    mnt = np.zeros_like(px, dtype=float)
    for dy in (-3, 0, 3):
        for dx in (-3, 0, 3):
            b = blend[np.clip(py + dy, 0, FULL[1] - 1), np.clip(px + dx, 0, FULL[0] - 1)]
            mnt += (b >= 4) & (b <= 7)
    base_new = base[orr, oc].copy()
    base_new[padding] = np.where(mnt[padding] >= 5, MOUNTAIN_AREA, AREAS[0])
    out = base_new.copy()
    sea, beach, cliff = N["terr"] == 1, N["terr"] == 2, N["terr"] == 3
    out[sea] = SEA; out[beach] = BEACH; out[cliff] = CLIFF          # vanilla: every map.hex sea hex (rivers too) is sea
    coast = beach | cliff
    drawable = lambda p: not sea[p[1], p[0]] and not coast[p[1], p[0]] and (not padding[p[1], p[0]] or NEWR[p[1], p[0]])
    log(f"grid {NW}x{NH}; padding hexes {int(padding.sum())}; Korea hexes {int(KR.sum())}")

    korea_family = {}
    for main, members in FAMILIES:
        E = family_edges(hc, members); n = sk = 0
        for a, b in E:
            if main in ROADS and (KR_old[a[1], a[0]] or KR_old[b[1], b[0]]):
                korea_family[main] = korea_family.get(main, 0) + 1; sk += 1; continue
            for p in hex_line(m(*a), m(*b)):
                if drawable(p): out[p[1], p[0]] = main; n += 1
        log(f"{'%06x' % main}: {len(E)} 190E edges redrawn ({n} hexes){f', {sk} Korean road edges skipped' if sk else ''}")
    kfam = max(korea_family, key=korea_family.get) if korea_family else TRACK
    k = x = 0
    for r, c in zip(*np.nonzero(KR & (N["road"] > 0))):
        if not drawable((c, r)): continue
        if out[r, c] == RIVER: out[r, c] = CROSSING[kfam]; x += 1          # road over a river: crossing marker
        else: out[r, c] = kfam; k += 1
    # new regions (regions_carve.py): their map.hex roads are drawn too, as the family 190E used most in each area
    kn = xn = 0
    for r, c in zip(*np.nonzero(NEWR & (N["road"] > 0))):
        if not drawable((c, r)) or out[r, c] in ROADS or out[r, c] in CROSSING.values(): continue
        if out[r, c] == RIVER: out[r, c] = CROSSING[TRACK]; xn += 1
        else: out[r, c] = TRACK; kn += 1
    log(f"new-region roads from map.hex: {kn} hexes as tracks, {xn} river crossings")
    log(f"Korea roads from map.hex: {k} hexes as {'%06x' % kfam}, {x} river crossings (190E Korean road families {({'%06x' % a: b for a, b in korea_family.items()})})")

    for mk in MARKERS:
        k = 0
        for r, c in zip(*np.nonzero(hc == mk)):
            if mk in CROSSING.values() and KR_old[r, c]: continue          # Korean crossings come from map.hex roads
            p = m(c, r)
            if drawable(p): out[p[1], p[0]] = mk; k += 1
        log(f"{'%06x' % mk}: {k} markers")

    NA = neighbour_arrays(NH, NW)
    touch_sea = np.zeros((NH, NW), bool)
    for nr, nc, v in NA: touch_sea |= v & sea[nr, nc]
    shore = ~sea & touch_sea
    placed = 0
    for r, c in zip(*np.nonzero(hc == MOUTH)):
        s = m(c, r); seen = {s}; q = deque([s]); target = None
        while q:
            p = q.popleft()
            if shore[p[1], p[0]]: target = p; break
            if len(seen) > 400: break
            for d in range(6):
                n_ = neighbour(p[0], p[1], d)
                if 0 <= n_[0] < NW and 0 <= n_[1] < NH and n_ not in seen and not sea[n_[1], n_[0]]:
                    seen.add(n_); q.append(n_)
        if target is None: continue
        for p in hex_line(s, target)[:-1]:
            if drawable(p): out[p[1], p[0]] = RIVER
        out[target[1], target[0]] = MOUTH; placed += 1
    log(f"river mouths: {placed} placed on the coast")

    removed = 0
    for main, members in FAMILIES:
        fam = set(members) | ({MOUTH} if main == RIVER else set())
        changed = True
        while changed:
            changed = False
            mask = np.isin(out, list(fam))
            for r, c in zip(*np.nonzero(mask & (out == main))):
                if main in ROADS and (KR[r, c] or NEWR[r, c]): continue  # hex-drawn roads: keep 1:1 with map.hex
                ring = []
                for d in range(6):
                    n_ = neighbour(c, r, d)
                    ring.append(0 <= n_[0] < NW and 0 <= n_[1] < NH and out[n_[1], n_[0]] in fam)
                kk = sum(ring)
                if kk < 2 or kk == 6: continue
                if sum(1 for d in range(6) if ring[d] and not ring[d - 1]) == 1:
                    out[r, c] = base_new[r, c]; removed += 1; changed = True
    log(f"thinning: {removed} redundant line hexes removed")

    nb = np.zeros((NH, NW), bool)
    for nr, nc, v in NA: nb |= v & (out[nr, nc] == BEACH)
    ends = (out == CLIFF) & nb; out[ends] = CLIFF_END
    log(f"cliff ends: {int(ends.sum())}")
    # coast / river / crossing neighbourhoods vanilla never uses have no BOB tile -> see-through holes
    from tile_repair import repair
    repair(out, log)

    img = np.zeros((2 * NH + 1, 2 * NW), np.int64)
    ys, xs = hex_pixels(NW, NH)
    for k in range(4): img[ys[..., k], xs[..., k]] = out
    rgba = np.stack([(img >> 16) & 255, (img >> 8) & 255, img & 255, np.full_like(img, 255)], -1).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA"), out


if __name__ == "__main__":
    im, out = build()
    im.save(HERE / "tile_map_rebuilt.png")
    vals, cnt = np.unique(out, return_counts=True)
    print(im.size, {('%06x' % v): int(n) for v, n in sorted(zip(vals, cnt), key=lambda t: -t[1])[:16]})
