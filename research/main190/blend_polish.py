#!/usr/bin/env python3
"""Ground-texture (blend map) polish for the new areas: H2 + H3 of docs/proposals/new_areas_lookover.md.

terrain/3k_dlc07_main_map.blend.191fd8068da8020.tif: palette-indexed, 8 px / hex, row 0 = north. Palette index ->
texture group (texture_arrays.xml): 0-3 arid, 4-7 cold (Qilian-red "mountain" ground), 19-22 steppe,
23-26 subtropical, 27-30 temperate; 8-18 / 31 are special (grain, rice, tea, road, mud, shroud, wetlands).

Groups (hex/map.hex regions):
  hexi      ironic_hexi_* + ironic_region_{hanyang,xi,wuwei,xiping}
  nomad     ironic_nomad_* + ironic_region_wuyuan
  korea_ne  the other ironic_region_* EXCEPT Korea's south (KOREA_SOUTH below, korea_fix already fine)
  np_new    non-playable padding (terrain/pad_mask.png), np_old the rest of the non-playable land
  PROTECTED vanilla (3k_*), ironic_central_*, ironic_south_*, Korea's south, sea: never written.

H2  mountain ground (4-7) on flat passable land in hexi / nomad / korea_ne -> by hex climate: arid / cold -> steppe
    19-22, temperate / subtropical -> temperate 27-30 (mixes learned from vanilla flat land). "Flat" = 5-hex mean of
    the height gradient at hex centres < 30 (the proposal's measure), passable, land. The hex mask is smoothed,
    upsampled and dithered with smooth noise, so the new edge is organic (no hex staircase). Xiping: its slopes are not
    flat, so they keep cold ground; its basins become steppe (hexi_plan's "high grassland"). Variant per PIXEL from
    ranked 2-octave smooth noise (class_fill's method).
H3  on hexi + np_new + the old north edge band (hex rows 1035-1080) + the Hexi zone edge (hexi_geo zone boundary):
    (c) single-texture areas (no class change within ~40 px) get 1-2 extra variants of the same family as noise patches
    (b) the comb along the old north edge (pixel rows EDGE_Y-72 .. EDGE_Y+6) is redrawn from the rows 12 px outside the
        band, mirrored, with a noisy north/south split and x jitter
    (a) domain-warp re-sample (dx, dy = smooth noise, +-6 px fine + +-8 px coarse, tapered to 0 at the domain edge),
        then a 5x5 majority filter. Only natural-family pixels (arid/cold/steppe/subtrop/temperate) are rewritten and
        only from natural-family sources; special classes (roads, wetlands, ...) stay.

ONE-OFF, in place (marker hex/.blend_polish); backup terrain/_pre_blend_polish/. Refuses to run twice.
  python blend_polish.py --dry     metrics + previews to output/polish/blend/, nothing written in terrain/ or hex/
  python blend_polish.py           apply (then copy the blend into the kit, see relief_build.sh)
If class_fill.py / north_cull.py / korea_fix.py ever rewrite the blend, delete the marker and run this again."""
import io, json, shutil, sys, time
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
Image.MAX_IMAGE_PIXELS = None
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
TER = HERE / "terrain"
BLEND = TER / "3k_dlc07_main_map.blend.191fd8068da8020.tif"
HEIGHT = TER / "3k_dlc07_main_map.height.191fd803c1a801d.tif"
PAD = TER / "pad_mask.png"
MARK = HERE / "hex" / ".blend_polish"
BACKUP = TER / "_pre_blend_polish"
OUT = HERE.parent.parent / "output" / "polish" / "blend"

KOREA_SOUTH = ("baek", "baekje", "dongye", "gyeongju", "hanseong", "jinbeongun", "kimhae", "ye", "tamna")
HEXI_R = ("hanyang", "xi", "wuwei", "xiping")
PROT, HEXI, NOMAD, KNE, NPNEW, NPOLD = 0, 1, 2, 3, 4, 5
GNAME = {HEXI: "hexi", NOMAD: "nomad", KNE: "korea_ne", NPNEW: "np_new", NPOLD: "np_old"}
FAM = np.zeros(256, np.uint8)                       # 0 special, 1 arid, 2 cold, 3 steppe, 4 subtrop, 5 temperate
FAM[0:4], FAM[4:8], FAM[19:23], FAM[23:27], FAM[27:31] = 1, 2, 3, 4, 5
FAMN = {1: "arid", 2: "cold", 3: "steppe", 4: "subtrop", 5: "temperate"}
STEPPE_MIX = {21: .4, 20: .2, 22: .2, 19: .2}       # class_fill STEPPE (fallback)
TEMP_MIX = {27: .5, 28: .2, 29: .2, 30: .1}
FLAT_SLOPE = 30.0                                   # 5-hex mean gradient (u16 / px) below = flat
BAND_ROWS = (1035, 1080)                            # hex rows (row 0 = south) of the old north edge band
ZONE_EDGE = 6                                       # hexes either side of the Hexi zone boundary
WARP_FINE, WARP_COARSE = 6.0, 8.0                   # px
UNIFORM_WIN, UNIFORM_MAX = 41, 0.004                 # (c): "single texture" = < 0.4% class changes in a 41 px window
PATCH1, PATCH2 = 0.22, 0.10                         # (c): share of alt1 / alt2 patches there
TILE = 256


# ---------------------------------------------------------------------------------------------------------- helpers
def group_code(n):
    if n.startswith("ironic_hexi_"): return HEXI
    if n.startswith("ironic_nomad_"): return NOMAD
    if n.startswith(("ironic_central_", "ironic_south_", "ironic_sea_")): return PROT
    if n.startswith("ironic_region_"):
        k = n[len("ironic_region_"):]
        if any(k.startswith(p + "_") for p in HEXI_R): return HEXI
        if k.startswith("wuyuan"): return NOMAD
        if k.startswith("sea_"): return PROT
        if any(k.startswith(p + "_") for p in KOREA_SOUTH): return PROT
        return KNE
    return PROT                                     # vanilla 3k_* (non-playable handled by the caller)


def px_hex(y, x, H, w, h):
    """hex (row, col) of pixels (row 0 = south; the measurement scripts' mapping, odd columns half a hex up)."""
    c = np.minimum(x // 8, w - 1)
    r = np.clip((H - 1 - y - 4 * (c & 1)) // 8, 0, h - 1)
    return r, c


_LAT = {}
def noise_at(y, x, cell, seed):
    """smooth (smoothstep-interpolated lattice) noise in [-1, 1] at pixel coords, evaluated only where asked."""
    k = (cell, seed)
    if k not in _LAT:
        _LAT[k] = np.random.default_rng(seed).uniform(-1, 1, (9068 // cell + 3, 11824 // cell + 3)).astype(np.float32)
    g = _LAT[k]
    fy = np.asarray(y, np.float32) / cell; fx = np.asarray(x, np.float32) / cell
    y0 = np.clip(fy.astype(np.int32), 0, g.shape[0] - 2); x0 = np.clip(fx.astype(np.int32), 0, g.shape[1] - 2)
    ty = fy - y0; tx = fx - x0; ty = ty * ty * (3 - 2 * ty); tx = tx * tx * (3 - 2 * tx)
    return (g[y0, x0] * (1 - ty) * (1 - tx) + g[y0, x0 + 1] * (1 - ty) * tx
            + g[y0 + 1, x0] * ty * (1 - tx) + g[y0 + 1, x0 + 1] * ty * tx)


def noise2(y, x, cell, seed):                       # class_fill's 2-octave mix
    return 0.5 * noise_at(y, x, cell, seed) + noise_at(y, x, 4 * cell, seed + 1)


def ranked(v):
    u = np.empty(len(v), np.float64); u[np.argsort(v, kind="stable")] = (np.arange(len(v)) + 0.5) / max(len(v), 1)
    return u


def pick(mix, u):
    ks = np.array(list(mix)); cdf = np.cumsum(list(mix.values())); cdf = cdf / cdf[-1]
    return ks[np.minimum(np.searchsorted(cdf, u), len(ks) - 1)]


def upsample(field, y, x, H):
    """bilinear sample of a (h, w) hex field (row 0 = south) at pixel coords."""
    rf = (H - 0.5 - y) / 8.0 - 0.5; cf = (x + 0.5) / 8.0 - 0.5
    return ndi.map_coordinates(field.astype(np.float32), [rf.ravel(), cf.ravel()], order=1, mode="nearest").reshape(np.shape(y))


# ---------------------------------------------------------------------------------------------------------- inputs
def load_inputs():
    import town_fix as T
    _, _, w, h, _, f, names = T.load(str(HERE / "hex" / "map.hex"))
    im = Image.open(BLEND); B = np.array(im); pal = im.getpalette()
    H, W = B.shape
    assert (W, H) == (8 * w, 8 * h + (H - 8 * h)) and H - 8 * h in (0, 4), (W, H, w, h)
    reg, terr = f["region"], f["terr"]
    npk = names.index("3k_main_reg_non_playable")
    gc = np.array([group_code(n) for n in names] + [PROT], np.uint8)[np.where(reg >= 0, reg, len(names))]
    padm = np.array(Image.open(PAD)) > 0
    rr, cc = np.indices((h, w))
    py = np.clip(H - 8 * rr - 4 - 4 * (cc & 1), 0, H - 1); pxx = np.clip(8 * cc + 4, 0, W - 1)
    padh = padm[py, pxx]
    gc[(reg == npk) & padh] = NPNEW; gc[(reg == npk) & ~padh] = NPOLD
    gc[terr == 1] = PROT
    ks = np.array([n.startswith("ironic_region_") and any(n[14:].startswith(p + "_") for p in KOREA_SOUTH) for n in names] + [False])[
        np.where(reg >= 0, reg, len(names))] & (terr != 1)
    edge_y = int(np.nonzero(~padm[:, W // 2])[0].min())        # first non-pad pixel row (the old north edge)
    del padm
    hgt = np.array(Image.open(HEIGHT))
    # gradient magnitude at hex centres (np.gradient central differences), 5-hex mean = the proposal's slope measure
    a = lambda yy, xx: hgt[np.clip(yy, 0, H - 1), np.clip(xx, 0, W - 1)].astype(np.float32)
    gx = (a(py, pxx + 1) - a(py, pxx - 1)) / 2; gy = (a(py + 1, pxx) - a(py - 1, pxx)) / 2
    s5 = ndi.uniform_filter(np.hypot(gx, gy), 5)
    try:
        import hexi_geo
        zw = hexi_geo._zone()["w"]
        zw = zw if zw.shape == (h, w) else None
    except Exception as e:
        print("hexi zone unavailable:", e); zw = None
    return dict(ks=ks, w=w, h=h, f=f, names=names, B=B, pal=pal, H=H, W=W, gc=gc, edge_y=edge_y, hgt=hgt, s5=s5, zw=zw,
                py=py, px=pxx, img=im)


# ---------------------------------------------------------------------------------------------------------- metrics
def metrics(B, I):
    w, h, H, f, gc = I["w"], I["h"], I["H"], I["f"], I["gc"]
    land = f["terr"] == 0
    Bh = B[I["py"], I["px"]]
    flat = land & (f["imp"] == 0) & (I["s5"] < FLAT_SLOPE)
    out = {"flat_mountain_pct": {}, "hex_border_pct": {}, "classes_per_climate": {}}
    groups = dict(GNAME); groups[PROT] = "protected"
    for g, n in groups.items():
        m = flat & (gc == g)
        out["flat_mountain_pct"][n] = round(100 * float(np.isin(Bh[m], [4, 5, 6, 7]).mean()), 1) if m.any() else None
        for cl in range(5):
            mm = land & (gc == g) & (f["climate"] == cl)
            if mm.sum() >= 2000: out["classes_per_climate"][f"{n}/{cl}"] = int(len(np.unique(Bh[mm])))
    for n, m in (("korea_south", flat & I["ks"]), ("korea_all(proposal def)", flat & ((gc == KNE) | I["ks"]))):
        out["flat_mountain_pct"][n] = round(100 * float(np.isin(Bh[m], [4, 5, 6, 7]).mean()), 1)
    # share of horizontal class transitions exactly on a hex-column border (every 4th row, like py/blend.py)
    xs = np.arange(1, B.shape[1]); ondiv = xs % 8 == 0; c = np.minimum(xs // 8, w - 1)
    tot = np.zeros(6, np.int64); on = np.zeros(6, np.int64)
    for y in range(0, H, 4):
        r = np.clip((H - 1 - y - 4 * (c & 1)) // 8, 0, h - 1)
        d = (B[y, 1:] != B[y, :-1]) & land[r, c]; g = gc[r, c]
        tot += np.bincount(g[d], minlength=6); on += np.bincount(g[d & ondiv], minlength=6)
    for g, n in groups.items():
        out["hex_border_pct"][n] = round(100 * on[g] / max(tot[g], 1), 1)
    out["h_transitions_per_land_hex"] = {n: round(4 * float(tot[g]) / max(int((land & (gc == g)).sum()), 1), 3)
                                         for g, n in groups.items()}       # x4: every 4th row sampled
    return out


# ---------------------------------------------------------------------------------------------------------- the edit
def learn_mixes(I):
    """variant mixes of steppe / temperate on vanilla-style flat land (protected groups = vanilla look)."""
    f, Bh = I["f"], I["B"][I["py"], I["px"]]
    base = (I["gc"] == PROT) & (f["terr"] == 0) & (I["s5"] < FLAT_SLOPE)
    mixes = {}
    for fam, fb in ((3, STEPPE_MIX), (5, TEMP_MIX)):
        v = Bh[base & (FAM[Bh] == fam)]
        cnt = np.bincount(v, minlength=256)
        mixes[fam] = {int(k): float(cnt[k] / cnt.sum()) for k in np.nonzero(cnt)[0]} if cnt.sum() > 2000 else fb
    alts = {}
    for fam in (1, 2, 3, 4, 5):                      # (c): per class, the two most common other variants (vanilla)
        v = Bh[(I["gc"] == PROT) & (f["terr"] == 0) & (FAM[Bh] == fam)]
        cnt = np.bincount(v, minlength=256); order = [int(k) for k in np.argsort(-cnt) if FAM[k] == fam and cnt[k] > 0]
        for k in np.nonzero(FAM == fam)[0]:
            o = [a for a in order if a != k] or [a for a in np.nonzero(FAM == fam)[0] if a != k]
            alts[int(k)] = (int(o[0]), int(o[1] if len(o) > 1 else o[0]))
    return mixes, alts


def domain_h3(I):
    """hex mask of the H3 domain (never protected), and its smoothed taper weight."""
    gc, f, h, w = I["gc"], I["f"], I["h"], I["w"]
    ok = (gc != PROT) & (f["terr"] != 1)
    rows = np.indices((h, w))[0]
    dom = ok & ((gc == HEXI) | (gc == NPNEW) | ((rows >= BAND_ROWS[0]) & (rows <= BAND_ROWS[1])))
    if I["zw"] is not None:
        z = I["zw"] > 0
        edge = z ^ ndi.binary_erosion(z)
        dom |= ok & (ndi.distance_transform_edt(~edge) <= ZONE_EDGE)
    taper = np.clip(ndi.gaussian_filter(dom.astype(np.float32), 1.5) * 2.0, 0, 1) * ok
    patchw = ndi.gaussian_filter(dom.astype(np.float32), 6.0)          # (c) fades out over ~6 hexes round the domain edge
    return dom, taper, patchw


def polish(I, log=print):
    B0, H, W, w, h, f, gc = I["B"], I["H"], I["W"], I["w"], I["h"], I["f"], I["gc"]
    cur = B0.copy()
    mixes, alts = learn_mixes(I)
    log("mixes: " + json.dumps({FAMN[k]: {c: round(v, 3) for c, v in m.items()} for k, m in mixes.items()}))
    stats = {}
    # ---------------- H2: flat mountain ground -> steppe / temperate
    flat_ok = ((gc == HEXI) | (gc == NOMAD) | (gc == KNE)) & (f["terr"] == 0) & (f["imp"] == 0) & (I["s5"] < FLAT_SLOPE)
    fsm = ndi.gaussian_filter(flat_ok.astype(np.float32), 0.8)
    clim = f["climate"].astype(np.float32)
    sel_y, sel_x, sel_t = [], [], []
    for y0 in range(0, H, TILE):
        y1 = min(H, y0 + TILE)
        yy, xx = np.mgrid[y0:y1, 0:W]
        cand = FAM[cur[y0:y1]] == 2
        if not cand.any(): continue
        ys, xs = yy[cand], xx[cand]
        r, c = px_hex(ys, xs, H, w, h)
        g = gc[r, c]
        k = (g == HEXI) | (g == NOMAD) | (g == KNE)
        ys, xs, r, c = ys[k], xs[k], r[k], c[k]
        if not len(ys): continue
        v = upsample(fsm, ys, xs, H) + 0.3 * noise2(ys, xs, 6, 101)
        k = v > 0.5
        ys, xs = ys[k], xs[k]
        # climate looked up at a noise-displaced pixel: organic climate borders between steppe and temperate fills
        cy = np.clip(ys + 12 * noise_at(ys, xs, 24, 103), 0, H - 1).astype(np.int64)
        cx = np.clip(xs + 12 * noise_at(ys, xs, 24, 104), 0, W - 1).astype(np.int64)
        rr, cc_ = px_hex(cy, cx, H, w, h)
        cl = f["climate"][rr, cc_]
        sel_y.append(ys); sel_x.append(xs); sel_t.append(np.where((cl == 4) | (cl == 3), 5, 3).astype(np.uint8))
    ys, xs, tf = (np.concatenate(a) if a else np.zeros(0, np.int64) for a in (sel_y, sel_x, sel_t))
    nz = noise2(ys, xs, 48, 111)            # class_fill: 12 / 48 quarter px = 48 / 192 full px
    for fam in (3, 5):
        m = tf == fam
        if m.any(): cur[ys[m], xs[m]] = pick(mixes[fam], ranked(nz[m])).astype(np.uint8)
    stats["h2_px"] = int(len(ys)); stats["h2_to_steppe_px"] = int((tf == 3).sum()); stats["h2_to_temperate_px"] = int((tf == 5).sum())
    log(f"H2: {len(ys):,} px reclassed ({int((tf == 3).sum()):,} -> steppe, {int((tf == 5).sum()):,} -> temperate)")
    del ys, xs, tf, nz, sel_y, sel_x, sel_t

    dom, taper, patchw = domain_h3(I)
    hr = np.nonzero(dom.any(1))[0]
    ylo = max(0, H - 8 * (hr.max() + 2) - 8); yhi = min(H, H - 8 * hr.min() + 8)
    stats["h3_domain_hexes"] = int(dom.sum())

    def tile_masks(y0, y1):
        yy, xx = np.mgrid[y0:y1, 0:W]
        r, c = px_hex(yy, xx, H, w, h)
        return yy, xx, dom[r, c]

    # ---------------- H3 (c): extra variants in single-texture areas
    n_c = 0
    for y0 in range(ylo, yhi, TILE):
        y1 = min(yhi, y0 + TILE); a0, a1 = max(0, y0 - UNIFORM_WIN), min(H, y1 + UNIFORM_WIN)
        blk = cur[a0:a1]
        ch = np.zeros(blk.shape, np.float32)
        ch[:, 1:] += blk[:, 1:] != blk[:, :-1]; ch[1:] += blk[1:] != blk[:-1]
        gch = ndi.gaussian_filter(ch, UNIFORM_WIN / 3.0)[y0 - a0:y1 - a0]      # local class-change density
        yy, xx, _ = tile_masks(y0, y1)
        r, c = px_hex(yy, xx, H, w, h)
        sub = cur[y0:y1]
        m = (gc[r, c] != PROT) & (f["terr"][r, c] != 1) & (FAM[sub] > 0) & (gch < 3 * UNIFORM_MAX)
        if not m.any(): continue
        ys, xs = yy[m], xx[m]
        pw = np.clip((upsample(patchw, ys, xs, H) - 0.1) / 0.8, 0, 1)
        if not (pw > 0).any(): continue
        # soft fade: the noise threshold rises towards the domain edge and towards existing texture borders, so the
        # patches shrink there (their outline stays a noise contour) instead of being cut by a mask edge
        pen = (1.5 * (1 - pw) + 0.75 * np.clip(gch[m] / UNIFORM_MAX - 1, 0, 2)) * (1 + 0.6 * noise_at(ys, xs, 14, 231))
        cls = sub[m]
        n1 = noise2(ys, xs, 40, 201); n2 = noise2(ys, xs, 32, 211)
        alt = np.array([alts.get(int(k), (int(k), int(k))) for k in range(256)], np.uint8)
        p1 = n1 > T1 + pen; p2 = (n2 > T2 + pen) & ~p1
        new = np.where(p1, alt[cls, 0], np.where(p2, alt[cls, 1], cls)).astype(np.uint8)
        sub[m] = new; n_c += int((new != cls).sum())
    stats["h3c_px"] = n_c
    log(f"H3c: {n_c:,} px variant patches in single-texture areas")

    # ---------------- H3 (b): the comb along the old north edge
    ey = I["edge_y"]; ya, yb = ey - 72, ey + 6
    nsrc, ssrc = ya - 12, yb + 12
    yy, xx = np.mgrid[ya:yb + 1, 0:W]
    r, c = px_hex(yy, xx, H, w, h)
    ok = (gc[r, c] != PROT) & (f["terr"][r, c] != 1) & (FAM[cur[ya:yb + 1]] > 0)
    t = (yy - ya) / float(yb - ya) + 0.35 * noise2(yy, xx, 8, 301)
    jx = np.clip(np.rint(xx + 8 * noise_at(yy, xx, 16, 302)), 0, W - 1).astype(np.int64)
    sy = np.where(t < 0.5, 2 * nsrc - yy + np.rint(4 * noise_at(yy, xx, 12, 303)).astype(np.int64),
                  2 * ssrc - yy + np.rint(4 * noise_at(yy, xx, 12, 304)).astype(np.int64))
    sy = np.clip(sy, 0, H - 1)
    src = cur[sy, jx]
    ok &= FAM[src] > 0
    band = cur[ya:yb + 1]
    n_b = int((ok & (band != src)).sum()); band[ok] = src[ok]
    stats["h3b_px"] = n_b; stats["comb_rows"] = [int(ya), int(yb)]
    log(f"H3b: comb rows {ya}-{yb} (old edge y={ey}), {n_b:,} px redrawn from y<{nsrc} / y>{ssrc}")

    # ---------------- H3 (a): domain warp + 5x5 majority (reads cur, writes out)
    out = cur.copy()
    n_a = 0; HALO = 2
    for y0 in range(ylo, yhi, TILE):
        y1 = min(yhi, y0 + TILE); a0, a1 = max(0, y0 - HALO), min(H, y1 + HALO)
        yy, xx = np.mgrid[a0:a1, 0:W]
        r, c = px_hex(yy, xx, H, w, h)
        tp = upsample(taper, yy, xx, H) * (gc[r, c] != PROT)
        dx = tp * (WARP_FINE * noise_at(yy, xx, 12, 401) + WARP_COARSE * noise_at(yy, xx, 48, 402))
        dy = tp * (WARP_FINE * noise_at(yy, xx, 12, 403) + WARP_COARSE * noise_at(yy, xx, 48, 404))
        sy = np.clip(np.rint(yy + dy), 0, H - 1).astype(np.int64); sx = np.clip(np.rint(xx + dx), 0, W - 1).astype(np.int64)
        src = cur[sy, sx]; orig = cur[a0:a1]
        wv = np.where((FAM[orig] > 0) & (FAM[src] > 0) & (tp > 0), src, orig)
        # 5x5 majority over natural classes (strictly more votes than the warped class itself)
        best = wv.copy(); bestn = np.zeros(wv.shape, np.float32)
        for k in np.unique(wv):
            if FAM[k] == 0: continue
            cnt = ndi.uniform_filter((wv == k).astype(np.float32), 5, mode="nearest")
            better = cnt > bestn + 1e-6
            bestn = np.where(better, cnt, bestn); best = np.where(better, k, best).astype(np.uint8)
        cntself = np.zeros(wv.shape, np.float32)
        for k in np.unique(wv):
            if FAM[k] == 0: continue
            mk = wv == k; cntself[mk] = ndi.uniform_filter(mk.astype(np.float32), 5, mode="nearest")[mk]
        res = np.where((FAM[wv] > 0) & (bestn > cntself + 1e-6), best, wv)
        s = slice(y0 - a0, y0 - a0 + (y1 - y0))
        write = (tp[s] > 0) & (FAM[orig[s]] > 0) & (gc[r[s], c[s]] != PROT)
        o = out[y0:y1]; n_a += int((write & (o != res[s])).sum()); o[write] = res[s][write]
    stats["h3a_px"] = n_a
    log(f"H3a: {n_a:,} px changed by warp + majority")
    return out, stats


# fixed thresholds of noise2 (the 2-octave sum spans about [-1.5, 1.5], roughly triangular around 0)
def _thr(share, cell, seed):
    rng = np.random.default_rng(999)
    v = noise2(rng.uniform(0, 9068, 400000), rng.uniform(0, 11824, 400000), cell, seed)
    return float(np.quantile(v, 1 - share))
T1 = None; T2 = None


# ---------------------------------------------------------------------------------------------------------- previews
BASE = {"arid": (214, 170, 110), "cold": (150, 110, 100), "grain": (200, 190, 90), "rice": (120, 170, 90), "tea": (80, 140, 70),
        "road": (90, 90, 90), "mud": (110, 90, 60), "shroud": (60, 60, 60), "steppe": (150, 170, 90), "subtrop": (70, 140, 60),
        "temperate": (100, 160, 90), "wetlands": (60, 120, 130)}
_F = ["arid"] * 4 + ["cold"] * 4 + ["grain"] * 2 + ["rice"] * 2 + ["tea", "road", "mud"] + ["shroud"] * 4 + ["steppe"] * 4 + ["subtrop"] * 4 + ["temperate"] * 4 + ["wetlands"]
_IDX = [0, 1, 2, 3, 0, 1, 2, 3, 0, 1, 0, 1, 0, 0, 0, 0, 1, 2, 3, 0, 1, 2, 3, 0, 1, 2, 3, 0, 1, 2, 3, 0]
LUT = np.zeros((256, 3), np.uint8)
for _i in range(32): LUT[_i] = np.clip(np.array(BASE[_F[_i]], float) * (1.15 - 0.12 * _IDX[_i]), 0, 255)
LUT[4:8] = [(205, 95, 80), (185, 85, 75), (165, 75, 70), (145, 65, 65)]     # cold/"mountain" in red so it stands out


def render(B, hgt, y0, y1, x0, x1, step):
    b = B[y0:y1:step, x0:x1:step]; hh = hgt[y0:y1:step, x0:x1:step].astype(np.float32)
    gy, gx = np.gradient(hh); shade = np.clip(1 + (-gx + gy) / (250 * step), 0.5, 1.3)
    rgb = LUT[b].astype(np.float32) * shade[..., None]
    rgb[hh < 14219] = (40, 70, 120)
    return np.clip(rgb, 0, 255).astype(np.uint8)


def previews(B0, B1, I, crops):
    from PIL import ImageDraw
    OUT.mkdir(parents=True, exist_ok=True)
    H = I["H"]
    for name, (c0, c1, r0, r1, step) in crops.items():
        y0, y1 = max(0, H - 8 * r1), min(H, H - 8 * r0); x0, x1 = max(0, 8 * c0), min(I["W"], 8 * c1)
        a = render(B0, I["hgt"], y0, y1, x0, x1, step); b = render(B1, I["hgt"], y0, y1, x0, x1, step)
        horiz = a.shape[1] <= a.shape[0] * 1.6
        sep = np.full((a.shape[0], 6, 3), 255, np.uint8) if horiz else np.full((6, a.shape[1], 3), 255, np.uint8)
        im = Image.fromarray(np.concatenate([a, sep, b], 1 if horiz else 0))
        d = ImageDraw.Draw(im); d.text((6, 4), f"BEFORE  {name}  cols {c0}-{c1} rows {r0}-{r1} 1:{step}", fill=(255, 255, 255))
        d.text(((a.shape[1] + 12) if horiz else 6, 4 if horiz else a.shape[0] + 10), "AFTER", fill=(255, 255, 255))
        im.save(OUT / f"blend_{name}.png", optimize=True)
    # change overview, 1 px per hex: grey land, colour = share of changed px
    w, h = I["w"], I["h"]
    ch = (B0[H - 8 * h:] != B1[H - 8 * h:]).reshape(h, 8, w, 8).mean((1, 3))[::-1]
    img = np.full((h, w, 3), 255, np.uint8); land = I["f"]["terr"] == 0
    img[land] = (225, 225, 225); img[I["f"]["terr"] == 1] = (170, 190, 215)
    img[land & (I["gc"] == PROT)] = (200, 200, 200)
    v = np.clip(ch * 3, 0, 1)
    img[ch > 0] = (np.array([255, 120, 0]) * v[ch > 0, None] + np.array([225, 225, 225]) * (1 - v[ch > 0, None])).astype(np.uint8)
    Image.fromarray(img[::-1]).save(OUT / "changed_overview.png", optimize=True)


def crops_for(I):
    names, reg, gc = I["names"], I["f"]["region"], I["gc"]
    rows, cols = np.indices(reg.shape)
    def bbox(sel, pad=6):
        return (int(cols[sel].min()) - pad, int(cols[sel].max()) + pad, int(rows[sel].min()) - pad, int(rows[sel].max()) + pad)
    ids = lambda *ks: np.isin(reg, [i for i, n in enumerate(names) if any(n.startswith("ironic_region_" + k + "_") for k in ks)])
    kn = bbox(ids("buyeo", "goguryeo", "hyunto"))
    st = bbox(gc == NOMAD); xp = bbox(ids("xiping"), 10)
    ey_row = (I["H"] - I["edge_y"]) // 8
    return {"korea_ne": (*kn, 2), "steppe": (*st, 4), "xiping": (*xp, 1),
            "hexi_corridor_border": (100, 220, 890, 990, 1), "comb_row1053": (300, 620, ey_row - 14, ey_row + 16, 1),
            "padding": (0, 200, 700, 950, 2)}


# ---------------------------------------------------------------------------------------------------------- main
def tiff_tags(path_or_buf):
    im = Image.open(path_or_buf)
    return im.mode, im.size, len(im.getpalette() or []), {k: v for k, v in im.tag_v2.items() if k not in (273, 279)}


def main(dry=False):
    global T1, T2
    if MARK.exists() and not dry:
        print("blend polish already applied:", MARK.read_text()); return
    if not dry and (BACKUP / BLEND.name).exists():
        print(f"backup {BACKUP / BLEND.name} exists but no marker: restore or delete it first"); return
    t0 = time.time()
    T1 = _thr(PATCH1, 40, 201); T2 = _thr(PATCH2 / (1 - PATCH1), 32, 211)
    I = load_inputs()
    print(f"loaded {I['W']}x{I['H']} blend, {I['w']}x{I['h']} hexes, old north edge y={I['edge_y']}, "
          f"hexi zone {'ok' if I['zw'] is not None else 'MISSING'} ({time.time() - t0:.0f}s)")
    before = metrics(I["B"], I)
    B1, stats = polish(I)
    after = metrics(B1, I)
    # protected pixels must be unchanged
    H, w, h = I["H"], I["w"], I["h"]
    prot_changed = 0; changed = np.zeros(6, np.int64)
    for y0 in range(0, H, TILE):
        y1 = min(H, y0 + TILE)
        d = B1[y0:y1] != I["B"][y0:y1]
        if not d.any(): continue
        yy, xx = np.nonzero(d); r, c = px_hex(yy + y0, xx, H, w, h)
        g = I["gc"][r, c]; changed += np.bincount(g, minlength=6)
    prot_changed = int(changed[PROT])
    rep = dict(before=before, after=after, stats=stats, changed_px={("protected" if g == PROT else GNAME[g]): int(changed[g]) for g in range(6)},
               protected_px_changed=prot_changed, ts=time.strftime("%Y%m%d_%H%M%S"))
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump(rep, open(OUT / ("metrics_dry.json" if dry else "metrics_applied.json"), "w"), indent=1)
    print("\nflat-land mountain texture % (before -> after):")
    for k in before["flat_mountain_pct"]: print(f"  {k:10s} {before['flat_mountain_pct'][k]} -> {after['flat_mountain_pct'][k]}")
    print("hex-border transition share % (before -> after):")
    for k in before["hex_border_pct"]: print(f"  {k:10s} {before['hex_border_pct'][k]} -> {after['hex_border_pct'][k]}")
    print("classes per group/climate (before -> after):")
    for k in before["classes_per_climate"]: print(f"  {k:12s} {before['classes_per_climate'][k]} -> {after['classes_per_climate'].get(k)}")
    print("changed px:", rep["changed_px"], " PROTECTED px changed:", prot_changed)
    assert prot_changed == 0, "protected pixels changed"
    # format check: same mode / size / palette / compression / tags as the input
    res = Image.fromarray(B1, "P"); res.putpalette(I["pal"])
    buf = io.BytesIO(); res.save(buf, format="TIFF", compression="tiff_lzw"); buf.seek(0)
    t_in, t_out = tiff_tags(BLEND), tiff_tags(buf)
    same = t_in == t_out
    print("TIFF format identical:", same, "" if same else f"\n  in  {t_in}\n  out {t_out}")
    if dry:
        previews(I["B"], B1, I, crops_for(I))
        print(f"dry run: previews + metrics in {OUT} ({time.time() - t0:.0f}s)"); return rep
    assert same, "TIFF format would change"
    BACKUP.mkdir(exist_ok=True); shutil.copy2(BLEND, BACKUP / BLEND.name)
    BLEND.write_bytes(buf.getvalue())
    MARK.write_text(json.dumps(dict(ts=rep["ts"], stats=stats, after=after["flat_mountain_pct"])))
    previews(I["B"], B1, I, crops_for(I))
    print("wrote", BLEND, "backup", BACKUP, "marker", MARK, f"({time.time() - t0:.0f}s)")
    return rep


if __name__ == "__main__":
    main(dry="--dry" in sys.argv)
