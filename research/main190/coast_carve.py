#!/usr/bin/env python3
"""Make the land raster agree with map.hex's sea. Run after dem_fill.py, before class_fill.py.

190E's map.hex was edited (Korea, Jeju, Liaodong Bay, islands, coasts) but its terrain is vanilla's, so 5.5% of
the sea hexes sit on DRY terrain. Compiled, that ground shows in game as flat plates standing out of the water
(the Liaodong "slab", the square Jeju block) and as sea/river hexes without water.
For every pixel whose (smoothed) nearest hex is sea: land = min(land, waterline - MARGIN - SLOPE * distance from
the coast), never below the sea floor value. The waterline is the sea source at that pixel (the dry test is
land >= sea, both compile at the same scale). The hex sea mask is blurred before thresholding so the new coast
follows the hexes without hexagon steps. Land-hex cores (land pixels more than CORE px from a sea hex) are never touched.
In/out: terrain/<height> and terrain/lf_heights.tif (in place; the pre-carve rasters are kept in terrain/_pre_carve/).
"""
import os, shutil, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
for p in (HERE, os.path.join(HERE, "..", "guandu"), os.path.join(HERE, ".."), os.path.join(HERE, "..", "..", "output", "pylibs")):
    sys.path.insert(0, p)
import tifffile
from tiff16 import write_gray16
from terrain_main import FULL, NWW, NWH
from dem_fill import box3
from regions_plan import load
from hexgrid import nearest_hex

T = os.path.join(HERE, "terrain"); KEEP = os.path.join(T, "_pre_carve")
HEIGHTS = ["3k_dlc07_main_map.height.191fd803c1a801d.tif", "lf_heights.tif"]
SEA = "3k_dlc07_main_map.sea_height.191fd804ab3801e.tif"
SEAS = [SEA, "lf_sea_heights.tif"]
SEA_LEVEL = 9594                    # flat sea surface (vanilla's open-sea value, sea source scale)
MARGIN, SLOPE, FLOOR, MAXD = 400, 250, 3084, 40      # land units; px
GROW, CORE = 12, 3                                   # px
KB_DIST, KB_GROW = 48, 24
LAKE_DROP = 120                                      # new lakes: water surface this far under the shore p10 (land units)                            # Korea beach ramp: px from the waterline; px around beach hexes


def korea_beach_zone(f, names, w, h):
    """Full-res weight (0..1) of 'near a Korean beach hex': beach hexes grown by KB_GROW px and feathered.
    Returns (weight crop, (y0, y1, x0, x1)) over Korea's bounding box."""
    from korea_fix import is_korean
    from hexgrid import centre
    kr = np.array([is_korean(n) for n in names] + [False])[np.clip(f["region"], -1, len(names) - 1)]
    rr, cc = np.nonzero(kr & (f["terr"] == 2))
    hx, hz = centre(cc, rr)
    px = (hx / NWW * FULL[0]).astype(int); py = ((1 - hz / NWH) * FULL[1]).astype(int)
    pad = KB_DIST + 16
    y0, y1 = max(0, py.min() - pad), min(FULL[1], py.max() + pad); x0, x1 = max(0, px.min() - pad), min(FULL[0], px.max() + pad)
    ys = np.arange(y0, y1); xs = np.arange(x0, x1)
    X, Z = np.meshgrid((xs + 0.5) / FULL[0] * NWW, (1 - (ys + 0.5) / FULL[1]) * NWH)
    c, r = nearest_hex(X, Z, w, h)
    beachP = (kr & (f["terr"] == 2))[np.clip(r, 0, h - 1), np.clip(c, 0, w - 1)].astype(np.float32)
    wgt = np.clip(box3(beachP, KB_GROW // 3) * 4, 0, 1)                 # grown beach cells, soft edge
    wgt = box3(wgt, 3)
    return wgt, (y0, y1, x0, x1)


def korea_beach_ramp(H, Sup, kb, name):
    """Korea's coast (190E's Korean terrain) is a flat shelf at world +0.41 that drops straight into the sea - in
    game the beaches read as raised steps. Near Korean beach hexes, lower the ground to the profile of the map's
    other beaches: -0.68 world 2 px from the waterline, ~0 at 8 px, +0.3 at 40 px (median of all non-Korean beach
    hexes). Only ever lowers; beyond KB_DIST px from the water, or away from beaches, nothing changes."""
    wgt, (y0, y1, x0, x1) = kb
    Hc = H[y0:y1, x0:x1]; Sc = Sup[y0:y1, x0:x1]
    wet = Sc > Hc
    d = np.full(Hc.shape, KB_DIST, np.int16); cur = wet.copy(); d[cur] = 0
    for k in range(1, KB_DIST):
        g = cur.copy(); g[1:] |= cur[:-1]; g[:-1] |= cur[1:]; g[:, 1:] |= cur[:, :-1]; g[:, :-1] |= cur[:, 1:]
        d[g & ~cur] = k; cur = g
    dw = d.astype(np.float32)
    world = -1.02 + 1.05 * (1 - np.exp(-dw / 5)) + 0.008 * dw           # other-beach profile (world units)
    target = (world + 3.12) / 0.00021849
    # fade out towards KB_DIST so the ramp meets the untouched land without a seam
    fade = np.clip((KB_DIST - dw) / 12, 0, 1)
    wt = wgt * fade * ~wet
    new = np.where(Hc > target, Hc - (Hc - target) * wt, Hc)
    out = H.copy(); out[y0:y1, x0:x1] = np.rint(new).astype(np.int32)
    ch = (out[y0:y1, x0:x1] < Hc)
    print(f"{name}: korea beach ramp lowered {int(ch.sum()):,} px (mean drop {float((Hc - out[y0:y1, x0:x1])[ch].mean()) * 0.00021849 if ch.any() else 0:.2f} world)")
    return out


def new_lake_levels(f, names, w, h, hh, ww, xs2):
    """Round-6 lakes (Hexi: Dunhuang, Yuanquan, Juyan): hexes that are lake in map.hex but land in 190E's
    map_korea.hex. They sit on the 1-1.5 km high corridor floor, so their water surface is set per lake just under
    the low part of its shore (the carve below then sinks the ground under that surface)."""
    from hexgrid import neighbour
    f0, _, _, _ = load(os.path.join(HERE, "hex", "map_korea.hex"))
    if f0["terr"].shape != f["terr"].shape:      # map_korea.hex is from an older grid (first pass after a warp change)
        print("new lakes: map_korea.hex is from another grid - skipped (rerun after the carve)"); return
    new = (f["terr"] == 1) & (f["region"] == names.index("3k_main_sea_lake")) & (f0["terr"] != 1)
    comp = np.zeros((h, w), np.int32); n = 0
    for r0, c0 in zip(*np.nonzero(new)):
        if comp[r0, c0]: continue
        n += 1; st = [(c0, r0)]; comp[r0, c0] = n
        while st:
            c, r = st.pop()
            for k in range(6):
                nc, nr = neighbour(c, r, k)
                if 0 <= nc < w and 0 <= nr < h and new[nr, nc] and not comp[nr, nc]: comp[nr, nc] = n; st.append((nc, nr))
    if not n: return
    compP = np.zeros((hh, ww), np.int32)
    for r0 in range(0, hh, 512):
        r1 = min(hh, r0 + 512); zs2 = (1 - (np.arange(r0, r1) + 0.5) / hh) * NWH
        X, Z = np.broadcast_arrays(xs2[None, :], zs2[:, None]); c, r = nearest_hex(X, Z, w, h)
        compP[r0:r1] = comp[np.clip(r, 0, h - 1), np.clip(c, 0, w - 1)]
    Hs = tifffile.imread(os.path.join(KEEP, HEIGHTS[0])).astype(np.int32)[::2, ::2][:hh, :ww]
    rasters = {k: tifffile.imread(os.path.join(T, k)).astype(np.int32) for k in SEAS}
    for k in range(1, n + 1):
        ys, xs = np.nonzero(compP == k)
        if not len(ys): continue
        y0, y1, x0, x1 = max(0, ys.min() - 20), min(hh, ys.max() + 21), max(0, xs.min() - 20), min(ww, xs.max() + 21)
        m = (compP[y0:y1, x0:x1] == k).astype(np.float32)
        ring = (box3(m, 4) > 0.01) & ~(box3(m, 1) > 0.01)
        level = int(np.percentile(Hs[y0:y1, x0:x1][ring], 10)) - LAKE_DROP
        area = box3(m, 2) > 0.01
        for R in rasters.values(): R[y0:y1, x0:x1][area] = level
        print(f"new lake {k}: {int(m.sum()):,} sea px, water surface {level} (shore p10 {level + LAKE_DROP})")
    for k, R in rasters.items(): write_gray16(os.path.join(T, k), np.clip(R, 0, 65535).astype(np.uint16))


def main():
    # input: dem_fill.py's output, which dem_fill writes to terrain/_pre_carve/ (never refreshed from terrain/, which
    # holds the carved result - re-reading that would carve twice)
    for n in HEIGHTS: assert os.path.exists(os.path.join(KEEP, n)), "run dem_fill.py first"
    # (sea rasters: dem_fill.py's output is copied to _pre_carve on first run; dem_fill.py refreshes it - see below)
    f, names, w, h = load()
    # 1. open sea (map.hex sea hexes outside river/lake regions) gets a FLAT surface: 190E's sea raster is vanilla's,
    #    and where vanilla had land its sea values are raised junk that land used to hide. Exposed by 190E's new sea
    #    they show as raised water plates (the Liaodong "slab"). Rivers and lakes keep their raised surfaces.
    riverlake = np.array([("riv_sea" in n or "lake" in n) for n in names] + [False])
    open_hex = (f["terr"] == 1) & ~riverlake[np.clip(f["region"], -1, len(names) - 1)]
    for n in SEAS:
        src = os.path.join(KEEP, n)
        if not os.path.exists(src): shutil.copy2(os.path.join(T, n), src)          # dem_fill output (first run only)
    S0 = tifffile.imread(os.path.join(KEEP, SEA)).astype(np.int32); hh, ww = S0.shape
    xs2 = (np.arange(ww) + 0.5) / ww * NWW; openP = np.zeros((hh, ww), np.float32); rlP = np.zeros((hh, ww), bool)
    rl_hex = (f["terr"] == 1) & riverlake[np.clip(f["region"], -1, len(names) - 1)]
    for r0 in range(0, hh, 512):
        r1 = min(hh, r0 + 512); zs2 = (1 - (np.arange(r0, r1) + 0.5) / hh) * NWH
        X, Z = np.broadcast_arrays(xs2[None, :], zs2[:, None]); c, r = nearest_hex(X, Z, w, h)
        openP[r0:r1] = open_hex[np.clip(r, 0, h - 1), np.clip(c, 0, w - 1)]
        rlP[r0:r1] = rl_hex[np.clip(r, 0, h - 1), np.clip(c, 0, w - 1)]
    # flat right up to (and a little under) the shore; a soft edge only where open sea meets a river mouth or lake
    near_rl = box3(rlP.astype(np.float32), 3) > 0.01
    wo = np.where(near_rl, np.clip(box3(openP, 2), 0, 1), (box3(openP, 2) > 0.01).astype(np.float32))
    for n in SEAS:
        Sx = tifffile.imread(os.path.join(KEEP, n)).astype(np.float32)
        out = np.rint(Sx * (1 - wo) + SEA_LEVEL * wo).astype(np.uint16)
        write_gray16(os.path.join(T, n), out)
        print(f"{n}: open sea flattened to {SEA_LEVEL} ({int((openP > 0.5).sum()):,} px; raised px there before: {int(((openP > 0.5) & (Sx > SEA_LEVEL + 50)).sum()):,})")
    new_lake_levels(f, names, w, h, hh, ww, xs2)
    S = tifffile.imread(os.path.join(T, SEA)).astype(np.int32)
    sea_hex = (f["terr"] == 1)
    seaP = np.zeros((FULL[1], FULL[0]), np.float32)
    CH = 512
    xs = (np.arange(FULL[0]) + 0.5) / FULL[0] * NWW
    for r0 in range(0, FULL[1], CH):                                     # pixel -> nearest hex -> sea?
        r1 = min(FULL[1], r0 + CH); zs = (1 - (np.arange(r0, r1) + 0.5) / FULL[1]) * NWH
        X, Z = np.broadcast_arrays(xs[None, :], zs[:, None]); c, r = nearest_hex(X, Z, w, h)
        seaP[r0:r1] = sea_hex[np.clip(r, 0, h - 1), np.clip(c, 0, w - 1)]
    seaS = box3(seaP, 5) >= 0.5                                          # smoothed hex coast
    # distance (px) from the smoothed coast into the sea, up to MAXD
    dist = np.full(seaS.shape, MAXD, np.int16); land = ~seaS; cur = land.copy(); dist[cur] = 0
    for k in range(1, MAXD):
        g = cur.copy(); g[1:] |= cur[:-1]; g[:-1] |= cur[1:]; g[:, 1:] |= cur[:, :-1]; g[:, :-1] |= cur[:, 1:]
        dist[g & ~cur] = k; cur = g
    Sup = np.repeat(np.repeat(S, 2, 0), 2, 1)[:FULL[1], :FULL[0]]
    # land-hex cores (land pixels more than CORE px from any sea-hex pixel) are never lowered
    near_sea = box3(seaP, CORE // 3 + 1) > 0.01
    land_core = (seaP < 0.5) & ~near_sea
    # plus the centre of every land hex (+-2 px), so even one-hex slivers of land stay above water
    from hexgrid import centre
    rr, cc = np.nonzero(f["terr"] != 1); hx, hz = centre(cc, rr)
    cx = np.clip((hx / NWW * FULL[0]).astype(int), 0, FULL[0] - 1); cy = np.clip(((1 - hz / NWH) * FULL[1]).astype(int), 0, FULL[1] - 1)
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            land_core[np.clip(cy + dy, 0, FULL[1] - 1), np.clip(cx + dx, 0, FULL[0] - 1)] = True
    kb = korea_beach_zone(f, names, w, h)
    for n in HEIGHTS:
        H = tifffile.imread(os.path.join(KEEP, n)).astype(np.int32)
        target = np.maximum(Sup - MARGIN - SLOPE * dist.astype(np.int32), FLOOR)
        # 1. the mismatch: ground dry or within MARGIN of the waterline under the smoothed sea, outside land-hex cores
        base = seaS & ~land_core & (H > Sup - MARGIN) & (H > target)
        # 2. plus everything within GROW px of it (the underwater flanks of the old land - else a ridge remains)
        grown = box3(base.astype(np.float32), GROW // 3) > 0.02
        cut = grown & seaS & ~land_core & (H > target)
        # 3. feather beyond that into the untouched seabed
        wgt = np.maximum(box3(cut.astype(np.float32), 4), cut.astype(np.float32)) * (seaS & ~land_core)
        out = np.rint(H - (H - np.minimum(H, target)) * wgt).astype(np.int32)
        out = korea_beach_ramp(out, Sup, kb, n)
        write_gray16(os.path.join(T, n), out.astype(np.uint16))
        dry_before = seaS & (H >= Sup); dry_after = seaS & (out >= Sup)
        print(f"{n}: lowered {cut.sum():,} sea px (mean drop {float((H - out)[cut].mean()) if cut.any() else 0:.0f}); "
              f"dry px under sea hexes {dry_before.sum():,} -> {dry_after.sum():,}")


if __name__ == "__main__":
    main()
