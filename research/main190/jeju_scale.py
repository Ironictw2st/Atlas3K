#!/usr/bin/env python3
"""Enlarge Jeju (Tamna) in place (user 2026-10-02: each Tamna region ~1/8 of Taiwan): the island, its terrain and its two
regions are scaled about the island centroid by S = sqrt(TARGET / current land), in world space.

map.hex: every hex inside the scaled disc (old island + SHELF hexes of sea, x S) that is sea or Jeju now takes the hex at the
inverse position (terrain, region, impassable, ground, climate, attributes); towns / roads / rivers / bridges on Jeju are
cleared, then the towns are re-stamped at their scaled spots (town_restamp), the coast ring rule applied and the Jeju
road redrawn. Rasters in terrain/ (heights 8 px/hex, sea 4 px/hex, blend, climate, tree, tile_map_warped): the same
inverse resample inside the disc. Writes hex/.jeju_scaled (centre, S, old radius) for the props hook
(x15_land.jeju_warp); refuses to run twice. Backups: hex/map_pre_jeju_<ts>.hex, terrain/_pre_jeju/. --dry: report only."""
import json, shutil, struct, sys, time, zlib
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
Image.MAX_IMAGE_PIXELS = None
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent, Path(r"Z:/Claude/CAIME/webpainter")): sys.path.insert(0, str(p))
import town_fix as T
from hexgrid import neighbour_arrays, nearest_hex, HX, HZ
TARGET = 980
SHELF = 3
MARK = HERE / "hex" / ".jeju_scaled"
TOWNS = ("ironic_region_tamna_capital", "ironic_region_baek_resource_1")
RAST = HERE / "terrain"
RASTERS = {  # file: (px per hex, resample order)
    "3k_dlc07_main_map.height.191fd803c1a801d.tif": (8, 1), "lf_heights.tif": (8, 1),
    "3k_dlc07_main_map.sea_height.191fd804ab3801e.tif": (4, 1), "lf_sea_heights.tif": (4, 1),
    "3k_dlc07_main_map.blend.191fd8068da8020.tif": (8, 0), "climate_map_g.png": (8, 0), "climate_map.png": (2, 0),
    "3k_dlc07_main_map.tree.191fd7dc12fe7e4.tif": (2, 0), "tile_map_warped.png": (2, 0)}


def world(c, r):
    c = np.asarray(c, float); r = np.asarray(r, float)
    return c * HX, r * HZ + (np.mod(np.rint(c), 2)) * HZ / 2


def main(dry):
    if MARK.exists() and not dry: raise SystemExit(f"already scaled ({MARK.read_text()}) - restore hex/map_pre_jeju_* + terrain/_pre_jeju first")
    b, P, w, h, g, f, names = T.load(str(HERE / "hex" / "map.hex"))
    NA = neighbour_arrays(h, w)
    land = f["terr"] != 1
    lab, _ = ndi.label(land)
    k0 = names.index(TOWNS[0]); rr, cc = np.nonzero((f["slot"] == 0) & (f["region"] == k0))
    isl = lab == lab[rr[0], cc[0]]
    n_old = int(isl.sum()); S = float(np.sqrt(TARGET / n_old))
    ir, ic = np.nonzero(isl)
    wx, wz = world(ic, ir); cx, cz = float(wx.mean()), float(wz.mean())
    shelf = ndi.binary_dilation(isl, iterations=SHELF)
    sr, sc = np.nonzero(shelf); sx, sz = world(sc, sr)
    R0 = float(np.hypot(sx - cx, sz - cz).max()); R1 = R0 * S
    other = land & ~isl
    near_other = ndi.binary_dilation(other, iterations=3)
    rows, cols = np.mgrid[0:h, 0:w]
    X, Z = world(cols, rows)
    target = (np.hypot(X - cx, Z - cz) <= R1) & ~near_other & (~land | isl)
    # inverse map every target hex
    tr, tc = np.nonzero(target)
    tx, tz = world(tc, tr)
    ux, uz = cx + (tx - cx) / S, cz + (tz - cz) / S
    ucol, urow = nearest_hex(ux, uz, w, h)
    ucol = np.asarray(ucol, int); urow = np.asarray(urow, int)
    G = g.copy()
    G[tr, tc] = g[urow, ucol]
    # clear towns / roads / rivers / bridges / trade on the scaled area (re-made below)
    G[tr, tc, 2] = G[tr, tc, 2] & 0x0F                          # slot nibble -> -1 (stored +1 = 0)
    G[tr, tc, 3] = 0                                            # road edges, sprawl, bridge
    G[tr, tc, 4] = G[tr, tc, 4] & 0xC0                          # river edges
    f2 = T.unpack(G) if hasattr(T, "unpack") else None
    from rebuild_hex import unpack, pack
    f2 = unpack(G)
    newland = (f2["terr"] != 1) & target
    print(f"Jeju: {n_old} land hexes -> {int((ndi.label(f2['terr'] != 1)[0] == ndi.label(f2['terr'] != 1)[0][int(cz / HZ), int(cx / HX)]).sum())} "
          f"(target {TARGET}); S {S:.3f}; centre world ({cx:.2f},{cz:.2f}); old disc {R0:.1f}u -> {R1:.1f}u; "
          f"regions {[(n, int(((f2['region'] == names.index(n)) & (f2['terr'] != 1)).sum())) for n in TOWNS]}")
    if dry: return
    ts = time.strftime("%Y%m%d_%H%M%S")
    shutil.copy2(HERE / "hex" / "map.hex", HERE / "hex" / f"map_pre_jeju_{ts}.hex")
    # towns: one slot-0 hex at each scaled town centre, then town_restamp grows the footprint
    import town_restamp as TR
    seeds = []
    for kname, kind in zip(TOWNS, ("city", "resource")):
        k = names.index(kname)
        r0, c0 = np.nonzero((f["slot"] == 0) & (f["region"] == k))
        ox, oz = world(c0.mean(), r0.mean())
        nx, nz = cx + (float(ox) - cx) * S, cz + (float(oz) - cz) * S
        c, r = nearest_hex(np.array([nx]), np.array([nz]), w, h); c, r = int(np.asarray(c)[0]), int(np.asarray(r)[0])
        okm = (f2["region"] == k) & (f2["terr"] == 0) & (f2["imp"] == 0)
        if not okm[r, c]:
            rr_, cc_ = np.nonzero(okm); j = int(np.argmin((cc_ - c) ** 2 + (rr_ - r) ** 2)); c, r = int(cc_[j]), int(rr_[j])
        G[r, c, 2] = (G[r, c, 2] & 0x0F) | (1 << 4); G[r, c, 3] |= 1
        seeds.append((k, kind))
    for k, kind in seeds:
        _, rep = TR.restamp(G, k, kind); print("  town", names[k], rep.get("total"), rep.get("warnings") or rep.get("error"))
    # region edge bits (b15) for the changed area
    f3 = unpack(G); reg = f3["region"]
    redge = np.zeros((h, w), np.int32)
    for d, (nr, nc, v) in enumerate(NA): redge |= ((v & (reg[nr, nc] != reg)).astype(np.int32) << d)
    f3["redge"] = redge
    out = pack(f3); out[..., 10:15] = g[..., 10:15]
    body = bytearray(b); body[P + 8:P + 8 + 16 * w * h] = out.tobytes()
    body[-4:] = struct.pack("<I", zlib.crc32(bytes(body[:-4])) & 0xFFFFFFFF)
    (HERE / "hex" / "map.hex").write_bytes(bytes(body))
    # rasters
    bk = RAST / "_pre_jeju"; bk.mkdir(exist_ok=True)
    for fn, (pph, order) in RASTERS.items():
        p = RAST / fn
        if not p.exists(): print("  missing", fn); continue
        shutil.copy2(p, bk / fn)
        im = Image.open(p); mode, pal = im.mode, im.getpalette() if im.mode == "P" else None
        a = np.array(im)
        Hp = a.shape[0]
        # pixel <-> hex: col = x / pph, row = (Hp - 1 - y) / pph (row 0 south); centre in pixels
        ccol, crow = cx / HX, (cz - 0) / HZ
        px0, py0 = ccol * pph + pph / 2, Hp - 1 - (crow * pph + pph / 2)
        rx, ry = R1 / HX * pph + 2 * pph, R1 / HZ * pph + 2 * pph
        x0, x1 = int(max(0, px0 - rx)), int(min(a.shape[1], px0 + rx)); y0, y1 = int(max(0, py0 - ry)), int(min(Hp, py0 + ry))
        yy, xx = np.mgrid[y0:y1, x0:x1]
        hc = np.clip((xx // pph).astype(int), 0, w - 1); hr = np.clip(((Hp - 1 - yy) // pph).astype(int), 0, h - 1)
        sel = target[hr, hc]
        sx_ = px0 + (xx - px0) / S; sy_ = py0 + (yy - py0) / S
        chans = [a] if a.ndim == 2 else [a[..., i] for i in range(a.shape[2])]
        res = []
        for ch in chans:
            v = ndi.map_coordinates(ch.astype(np.float64), [sy_, sx_], order=order, mode="nearest")
            blk = ch[y0:y1, x0:x1].copy()
            blk[sel] = np.rint(v[sel]).astype(ch.dtype) if order else v[sel].astype(ch.dtype)
            res.append(blk)
        if a.ndim == 2: a[y0:y1, x0:x1] = res[0]
        else: a[y0:y1, x0:x1] = np.stack(res, -1)
        im2 = Image.fromarray(a, mode if mode in ("P", "L", "RGB", "RGBA") else None)
        if pal: im2.putpalette(pal)
        im2.save(p, compression="tiff_lzw") if fn.endswith(".tif") else im2.save(p)
        print("  raster", fn, a.shape, int(sel.sum()), "px")
    MARK.write_text(json.dumps(dict(cx=cx, cz=cz, S=S, R0=R0, R1=R1, ts=ts)))
    print("wrote map.hex + rasters; marker", MARK)


if __name__ == "__main__":
    main("--dry" in sys.argv)
