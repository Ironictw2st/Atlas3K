#!/usr/bin/env python3
"""Ground-texture (blend map) v2 for the new northern areas: guided image quilting from vanilla (replaces blend_polish).

Why: blend_polish (H2/H3) only re-noised the 190E/class_fill painting (big round brush blobs, few flat tones): the in-game
result stayed "blotchy / patchy" with straight seams. v2 rebuilds the texture of the new land from VANILLA pieces of this
same map instead of from noise, so it inherits vanilla's fine field patchwork, its variant mixing and its edge shapes.

Input: the PRE-polish blend (terrain/_pre_blend_polish/), never the current file. Raster: palette index, 8 px / hex,
row 0 = north. Families (texture_arrays.xml): 0-3 arid, 4-7 cold ("mountain" ground), 8-9 grain, 10-11 rice, 12 tea,
13 road, 14 mud, 15-18 shroud, 19-22 steppe, 23-26 subtropical, 27-30 temperate, 31 wetlands.

Domain (rewritten): land hexes of hexi / nomad / korea_ne / np_new (blend_polish's groups) + np_old where flagged
(north of hex row NPOLD_ROW, inside the Hexi zone or within ZONE_EDGE hexes of its edge). Never written: vanilla 3k_*,
ironic_central_* / ironic_south_*, Korea's south, sea / lake hexes, unflagged np_old.

Method (Efros-Freeman image quilting with a texture-transfer guide, Kwatra graph-cut seams):
  * donors: 64x64 px windows (on a 16 px grid) of VANILLA land (3k_* regions, no shroud / rice / tea / road px,
    <= 25% water). Each has a descriptor: dryness mix (arid / steppe / green share of its non-mountain natural px),
    slope-band histogram, water-distance histogram, river share, grain share, hex row and climate.
  * target windows (48 px step, jittered +-8 px, raster order) over the domain. Target descriptor from the land itself:
    slope / water / river histograms of the polished height map + map.hex, the INTENDED dryness mix (pre-polish blend
    smoothed over ~6 hexes, mountain ground and specials ignored, 25% climate prior: desert stays desert, steppe stays
    steppe, Korea stays green) and the expected grain share (vanilla's grain rate by distance to towns; 0 in the
    non-playable land). Top-K donors by descriptor, then classic quilting cost = overlap mismatch with everything
    already there (placed patches AND the fixed vanilla / protected neighbours) + per-cell terrain correspondence
    (slope band, water / river band: mountain ground lands on slopes, riverside classes by rivers) + descriptor cost +
    a reuse penalty; random pick within a tolerance of the best.
  * dryness shift: if the target is much drier than the best donor (Hexi Gobi), whole steppe variants of the donor are
    recoloured to the matching arid variants (structure kept), so the Gobi stays desert with vanilla patch shapes.
  * seams: min-cut (scipy max-flow) per window over the mismatch of old vs new, with smooth noise on the edge weights
    -> irregular seams. Vanilla / protected px are hard "old"; domain px within FEATHER hexes of the protected land start
    as the old pre-polish px but are free, so the cut can run inside the domain instead of along the hex staircase.
  * H2 kept: after quilting, mountain ground (4-7) on flat passable land of hexi / nomad / korea_ne is checked
    (vanilla: 7%); if a group is over FLAT_MTN_MAX the flat cold px take the commonest non-mountain class around them.

  python blend_v2.py --dry   quilt in memory; metrics + previews to output/polish/blend_v2/ (nothing in terrain/ or hex/)
  python blend_v2.py         apply: backup the current blend to terrain/_pre_blend_v2/, write it, marker hex/.blend_v2
Re-running after an apply needs the marker deleted (the result only depends on the pre-polish backup + map.hex +
heights, all fixed seeds, so it is reproducible)."""
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
SRC = TER / "_pre_blend_polish" / BLEND.name          # the pre-polish blend = the input
HEIGHT = TER / "3k_dlc07_main_map.height.191fd803c1a801d.tif"
PAD = TER / "pad_mask.png"
MARK = HERE / "hex" / ".blend_v2"
BACKUP = TER / "_pre_blend_v2"
OUT = HERE.parent.parent / "output" / "polish" / "blend_v2"

KOREA_SOUTH = ("baek", "baekje", "dongye", "gyeongju", "hanseong", "jinbeongun", "kimhae", "ye", "tamna")
HEXI_R = ("hanyang", "xi", "wuwei", "xiping")
# group codes per hex
PROT, HEXI, NOMAD, KNE, NPNEW, NPOLD, NPOLDF, VAN = 0, 1, 2, 3, 4, 5, 6, 7
GNAME = {PROT: "protected_other", HEXI: "hexi", NOMAD: "nomad", KNE: "korea_ne", NPNEW: "np_new", NPOLD: "np_old_kept",
         NPOLDF: "np_old_flagged", VAN: "vanilla"}
DOMAIN = (HEXI, NOMAD, KNE, NPNEW, NPOLDF)
NPOLD_ROW = 830                 # np_old north of this hex row (row 0 = south) is part of "the north" -> rewritten
ZONE_EDGE = 6                   # np_old within this many hexes of the Hexi zone edge (or inside it) -> rewritten

FAM = np.zeros(256, np.uint8)   # 0 special, 1 arid, 2 cold, 3 steppe, 4 subtrop, 5 temperate
FAM[0:4], FAM[4:8], FAM[19:23], FAM[23:27], FAM[27:31] = 1, 2, 3, 4, 5
BAD = np.zeros(256, bool); BAD[10:19] = True        # rice, tea, road, mud?, shroud: never copied (mud 14 allowed below)
BAD[14] = False
GRAIN = (8, 9)

# quilting parameters (full-res px unless noted)
P, OV = 80, 24                  # patch, overlap -> step 56
STEP = P - OV
JIT = 4                         # target window jitter (px), breaks the grid (overlap stays 16..32 px)
Q = 4                           # guide / descriptor cell (px): 2 cells per hex
CSTEP = 16                      # donor grid (px)
K = 256                         # descriptor prefilter (then the full overlap / terrain cost on these)
TOL = 0.08                      # random pick among candidates with cost <= best + TOL
FEATHER = 1.5                   # hexes of domain next to fixed land that start as old (free for the cut)
W_OV, W_G, W_D, W_RE = 1.0, 0.6, 0.35, 0.03
WARP_FINE, WARP_COARSE = 4.0, 6.0                   # px, post-quilt domain warp (wavy seams)
W_M = 1.5                       # land logic: mountain ground where vanilla has it for that slope band (x impassable)
SLOPE_EDGES = (12.0, 33.0, 73.0, 130.0)             # vanilla north slope quantiles (u16 / px, 1-cell blur)
FLAT_SLOPE = 30.0                                   # blend_polish's 5-hex flatness measure (metrics / H2 check)
FLAT_MTN_MAX = 12.0                                 # % of flat passable hex centres with mountain ground, per group
SEED = 20261004


# ------------------------------------------------------------------------------------------------------------ helpers
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
    if n.startswith("3k_") and n != "3k_main_reg_non_playable": return VAN
    return PROT


def px_hex(y, x, H, w, h):
    """hex (row, col) of pixels (row 0 = south; odd columns half a hex up) - blend_polish's mapping."""
    c = np.minimum(x // 8, w - 1)
    r = np.clip((H - 1 - y - 4 * (c & 1)) // 8, 0, h - 1)
    return r, c


def smooth_noise(shape, cell, seed):
    rng = np.random.default_rng(seed)
    g = rng.uniform(-1, 1, (shape[0] // cell + 3, shape[1] // cell + 3)).astype(np.float32)
    return ndi.zoom(g, cell, order=1)[:shape[0], :shape[1]]


def hex_edt(m):
    """distance (hexes, approx) to the nearest True hex (row/col grid; good enough at the scales used here)."""
    return ndi.distance_transform_edt(~m, sampling=(1.0, 0.866))


# ------------------------------------------------------------------------------------------------------------ inputs
def load_inputs(log=print):
    import town_fix as T
    _, _, w, h, _, f, names = T.load(str(HERE / "hex" / "map.hex"))
    im = Image.open(SRC); B0 = np.array(im); pal = im.getpalette()
    H, W = B0.shape
    assert W == 8 * w and H - 8 * h in (0, 4), (W, H, w, h)
    reg, terr = f["region"], f["terr"]
    npk = names.index("3k_main_reg_non_playable")
    gc = np.array([group_code(n) for n in names] + [PROT], np.uint8)[np.where(reg >= 0, reg, len(names))]
    padm = np.array(Image.open(PAD)) > 0
    rr, cc = np.indices((h, w))
    py = np.clip(H - 8 * rr - 4 - 4 * (cc & 1), 0, H - 1); pxx = np.clip(8 * cc + 4, 0, W - 1)
    padh = padm[py, pxx]
    edge_y = int(np.nonzero(~padm[:, W // 2])[0].min())
    del padm
    gc[(reg == npk) & padh] = NPNEW; gc[(reg == npk) & ~padh] = NPOLD
    try:
        import hexi_geo
        zw = hexi_geo._zone()["w"]; zw = zw if zw.shape == (h, w) else None
    except Exception as e:
        log("hexi zone unavailable:", e); zw = None
    flag = (gc == NPOLD) & (rr >= NPOLD_ROW)
    if zw is not None:
        z = zw > 0; edge = z ^ ndi.binary_erosion(z)
        flag |= (gc == NPOLD) & (z | (ndi.distance_transform_edt(~edge) <= ZONE_EDGE))
    gc[flag] = NPOLDF
    land = terr == 0
    gc_land = np.where(land, gc, PROT).astype(np.uint8)        # water hexes never written / never donors
    hgt = np.array(Image.open(HEIGHT))
    a = lambda yy, xx: hgt[np.clip(yy, 0, H - 1), np.clip(xx, 0, W - 1)].astype(np.float32)
    gx = (a(py, pxx + 1) - a(py, pxx - 1)) / 2; gy = (a(py + 1, pxx) - a(py - 1, pxx)) / 2
    s5 = ndi.uniform_filter(np.hypot(gx, gy), 5)                 # blend_polish's flatness measure
    return dict(w=w, h=h, f=f, names=names, B0=B0, pal=pal, H=H, W=W, gc=gc_land, gc_all=gc, edge_y=edge_y, hgt=hgt,
                s5=s5, zw=zw, py=py, px=pxx, img=im)


def cell_maps(I, log=print):
    """Quarter-res (Q px) guide and descriptor maps."""
    H, W, w, h, f, B0 = I["H"], I["W"], I["w"], I["h"], I["f"], I["B0"]
    Hq, Wq = H // Q, W // Q
    hq = I["hgt"][:Hq * Q, :Wq * Q].reshape(Hq, Q, Wq, Q).mean((1, 3), dtype=np.float32)
    hs = ndi.gaussian_filter(hq, 1.0); gy, gx = np.gradient(hs); sl = np.hypot(gx, gy) / Q
    del hq, hs, gy, gx
    sbin = np.digitize(sl, SLOPE_EDGES).astype(np.uint8); del sl
    yy, xx = np.mgrid[0:Hq, 0:Wq]
    r, c = px_hex(yy * Q + Q // 2, xx * Q + Q // 2, H, w, h); del yy, xx
    land_h = f["terr"] == 0
    dw = hex_edt(~land_h); dr = hex_edt(f["river"] > 0)
    town = (f["slot"] >= 0) | (f["sprawl"] > 0); dt = hex_edt(town)
    wbin = np.digitize(dw, (0.5, 1.6, 3.2)).astype(np.uint8)[r, c]          # 0 water, 1 shore, 2 near, 3 inland
    rbin = np.digitize(dr, (0.5, 2.2)).astype(np.uint8)[r, c]               # 0 river hex, 1 near, 2 far
    tbin = np.digitize(dt, (1.5, 3, 6, 10)).astype(np.uint8)[r, c]
    gcq = I["gc"][r, c]; clim = f["climate"][r, c].astype(np.uint8); row = r.astype(np.int16)
    imp = (f["imp"][r, c] > 0) & np.isin(gcq, (HEXI, NOMAD, KNE, VAN, PROT))   # non-playable land is impassable by design
    # block "max" of bad classes and block stats of B0 at cell res (full res -> cells)
    Bc = B0[:Hq * Q, :Wq * Q]
    bad = BAD[Bc].reshape(Hq, Q, Wq, Q).any((1, 3))
    Bq = Bc[Q // 2::Q, Q // 2::Q]                                             # cell sample (centre px)
    return dict(Hq=Hq, Wq=Wq, sbin=sbin, wbin=wbin, rbin=rbin, tbin=tbin, gcq=gcq, clim=clim, row=row, bad=bad, Bq=Bq,
                r=r, c=c, imp=imp)


def dryness(Bq):
    """per cell indicator stack (arid, steppe, green) of non-mountain natural px, and its validity."""
    fam = FAM[Bq]
    return np.stack([(fam == 1), (fam == 3), (fam == 4) | (fam == 5)]).astype(np.float32)


def learn_priors(I, C, log=print):
    """vanilla priors: dryness mix per climate; grain share per town-distance bin (north vanilla)."""
    van = (C["gcq"] == VAN)
    D = dryness(C["Bq"]); nat = D.sum(0) > 0
    north = van & (C["row"] >= 600)
    prior = {}
    for cl in np.unique(C["clim"][van]):                       # north vanilla first (climate 1 is mostly Sichuan)
        for vm in (north, van):
            m = vm & nat & (C["clim"] == cl)
            if m.sum() > 1000: prior[int(cl)] = (D[:, m].sum(1) / m.sum()).astype(np.float32); break
    grain = np.isin(C["Bq"], GRAIN)
    gr = np.array([float(grain[north & (C["tbin"] == b)].mean()) if (north & (C["tbin"] == b)).any() else 0.0 for b in range(5)],
                  np.float32)
    # mountain-ground rate by slope band (x impassable) on north vanilla: the land-logic term's expectation per cell
    cold = FAM[C["Bq"]] == 2
    pc = np.zeros((2, 5), np.float32)
    for ip in (0, 1):
        for b in range(5):
            m = north & (C["sbin"] == b) & (C["imp"] == ip)
            pc[ip, b] = float(cold[m].mean()) if m.sum() > 500 else float(cold[north & (C["sbin"] == b)].mean())
    pslope = np.array([float(cold[north & (C["sbin"] == b)].mean()) for b in range(5)], np.float32)
    play = np.isin(C["gcq"], (HEXI, NOMAD, KNE))
    C["pcold"] = np.where(play & C["imp"], pc[1][C["sbin"]], np.where(play, pc[0][C["sbin"]], pslope[C["sbin"]])).astype(np.float32)
    log("vanilla dryness prior by climate (arid, steppe, green):", {k: np.round(v, 2).tolist() for k, v in prior.items()},
        " grain by town distance bin:", np.round(gr, 3).tolist(), " mountain ground by slope band (passable / impassable; any):",
        np.round(pc, 2).tolist(), np.round(pslope, 2).tolist())
    return prior, gr


def intent_map(I, C, prior, sigma=12.0):
    """Intended dryness mix per cell: the pre-polish blend's non-mountain natural px, smoothed over ~6 hexes, 25% prior."""
    D = dryness(C["Bq"]); wv = D.sum(0)
    out = np.zeros_like(D)
    ws = ndi.gaussian_filter(wv, sigma)
    for k in range(3): out[k] = ndi.gaussian_filter(D[k], sigma)
    pr = np.stack([np.full(C["clim"].shape, 1 / 3, np.float32)] * 3)
    for cl, v in prior.items():
        m = C["clim"] == cl
        for k in range(3): pr[k][m] = v[k]
    with np.errstate(invalid="ignore", divide="ignore"):
        it = np.where(ws > 0.05, out / np.maximum(ws, 1e-6), pr)
    a = np.clip(ws / 0.3, 0, 1)                        # little information (mountain areas) -> lean on the prior
    it = (0.75 * a) * it + (1 - 0.75 * a) * pr
    return (it / it.sum(0, keepdims=True)).astype(np.float32)


# ------------------------------------------------------------------------------------------------------------ quilting
class Quilter:
    """Guided image quilting on the blend. Descriptor channels per cell; donors / targets as Q-cell windows."""
    NC = P // Q

    def __init__(self, I, C, prior, grain_by_t, log=print):
        self.I, self.C, self.log = I, C, log
        Hq, Wq, n = C["Hq"], C["Wq"], self.NC
        self.int = intent_map(I, C, prior)
        # descriptor channel maps (per cell): 0-2 dryness (donor: own px; target: intent), 3-7 slope bins, 8-11 water
        # bins, 12 river near, 13 grain, then validity channels
        self.van = (C["gcq"] == VAN)
        D = dryness(C["Bq"])
        self.grain_exp = np.where(np.isin(C["gcq"], (NPNEW, NPOLD, NPOLDF)), 0.0, grain_by_t[C["tbin"]]).astype(np.float32)
        chans = []
        for k in range(3): chans.append(D[k])
        for b in range(5): chans.append((C["sbin"] == b).astype(np.float32))
        for b in range(4): chans.append((C["wbin"] == b).astype(np.float32))
        chans.append((C["rbin"] <= 1).astype(np.float32))
        chans.append(np.isin(C["Bq"], GRAIN).astype(np.float32))
        chans.append(D.sum(0))                                                   # natural non-mountain share
        chans.append(self.van.astype(np.float32))
        chans.append(C["bad"].astype(np.float32))
        chans.append((C["wbin"] == 0).astype(np.float32))
        # donor candidates on the CSTEP grid
        cs = CSTEP // Q
        ys = np.arange(0, Hq - n, cs); xs = np.arange(0, Wq - n, cs)
        gy, gx = np.meshgrid(ys, xs, indexing="ij"); gy, gx = gy.ravel(), gx.ravel()
        S = np.zeros((len(gy), len(chans)), np.float32)
        for i, ch in enumerate(chans):                       # window means via uniform filter, sampled at the corners
            m = ndi.uniform_filter(ch, n, mode="constant", origin=-(n // 2))
            S[:, i] = m[gy, gx]
        vanok = S[:, 15] >= 0.75 - 1e-4; badok = S[:, 16] <= 1e-6; watok = S[:, 17] <= 0.25
        ok = vanok & badok & watok
        self.cy, self.cx = gy[ok], gx[ok]
        S = S[ok]
        dr = S[:, 0:3]; natsh = np.maximum(S[:, 14:15], 1e-6)
        self.cdry = dr / natsh                                                     # dryness mix among natural px
        self.cdry[S[:, 14] < 0.05] = 1 / 3
        self.cslope, self.cwat, self.criv, self.cgrain = S[:, 3:8], S[:, 8:12], S[:, 12], S[:, 13]
        rc = (self.cy + n // 2, self.cx + n // 2)
        self.crow = C["row"][rc].astype(np.float32); self.cclim = C["clim"][rc]
        self.creg = I["f"]["region"][C["r"][rc], C["c"][rc]]
        self.used = np.zeros(len(self.cy), np.float32)
        log(f"donor windows: {len(self.cy):,} valid of {len(gy):,} (vanilla land >= 75%, no rice/tea/road/shroud, <= 25% water)")
        # noise for the cut edge weights (irregular seams where old and new disagree everywhere)
        self.rng = np.random.default_rng(SEED)

    def target_desc(self, y0, x0, dmask_c):
        """descriptor of a target window (cell coords), averaged over its domain cells."""
        n = self.NC; C = self.C; sl = (slice(y0, y0 + n), slice(x0, x0 + n))
        m = dmask_c; cnt = max(int(m.sum()), 1)
        it = self.int[:, sl[0], sl[1]][:, m].mean(1)
        sb = np.bincount(C["sbin"][sl][m], minlength=5)[:5] / cnt
        wb = np.bincount(C["wbin"][sl][m], minlength=4)[:4] / cnt
        rv = float((C["rbin"][sl][m] <= 1).mean()); gr = float(self.grain_exp[sl][m].mean())
        rw = float(C["row"][sl][m].mean()); cl = int(np.bincount(C["clim"][sl][m]).argmax())
        return it, sb, wb, rv, gr, rw, cl

    def prefilter(self, td):
        it, sb, wb, rv, gr, rw, cl = td
        cost = (2.0 * np.abs(self.cdry - it).sum(1) + 1.0 * np.abs(self.cslope - sb).sum(1) + 1.0 * np.abs(self.cwat - wb).sum(1)
                + 0.5 * np.abs(self.criv - rv) + 3.0 * np.abs(self.cgrain - gr)
                + 1.5 * np.clip((np.abs(self.crow - rw) - 120) / 300, 0, 1) + 0.3 * (self.cclim != cl))
        k = min(K, len(cost) - 1)
        idx = np.argpartition(cost, k)[:k]
        return idx, cost[idx]

    def shift_dry(self, blk, it):
        """recolour whole steppe variants of a donor block to arid while it is much less arid than the target."""
        fam = FAM[blk]; nat = (fam == 1) | (fam == 3) | (fam == 4) | (fam == 5)
        nn = max(int(nat.sum()), 1)
        a = float((fam == 1).sum()) / nn
        if it[0] - a <= 0.15: return blk
        cnt = np.bincount(blk.ravel(), minlength=256)
        out = blk.copy()
        for v in sorted([v for v in range(19, 23) if cnt[v] > 0], key=lambda v: -cnt[v]):
            if a >= it[0] - 0.05: break
            out[blk == v] = v - 19; a += cnt[v] / nn
        return out

    def run(self, B0, canvas, dom_fn, soft_fn, windows, log=print):
        """windows: list of (y, x) px top-left. dom_fn / soft_fn(y0, x0) -> (P, P) bool."""
        I, C, n = self.I, self.C, self.NC
        H, W = canvas.shape
        filled = np.zeros(canvas.shape, bool)                  # decided domain px (placed or kept)
        stats = dict(windows=0, skipped=0, px_new=0, cut_ms=0.0, shift=0)
        donor_px = {}
        noise = None
        t0 = time.time()
        for i, (y0, x0) in enumerate(windows):
            dom = dom_fn(y0, x0)
            if not dom.any(): stats["skipped"] += 1; continue
            fil = filled[y0:y0 + P, x0:x0 + P]
            soft = soft_fn(y0, x0) & dom & ~fil
            must_new = dom & ~fil & ~soft
            if not must_new.any(): stats["skipped"] += 1; continue
            yc, xc = y0 // Q, x0 // Q
            dmc = dom[Q // 2::Q, Q // 2::Q]
            if not dmc.any(): dmc = dom.reshape(n, Q, n, Q).any((1, 3))
            td = self.target_desc(yc, xc, dmc)
            idx, dcost = self.prefilter(td)
            old = canvas[y0:y0 + P, x0:x0 + P]
            known = ~dom | fil | soft                           # px with an existing value the patch should agree with
            wpx = np.ones((P, P), np.float32)
            wat = ~(I["f"]["terr"] == 0)[px_hex(np.arange(y0, y0 + P)[:, None], np.arange(x0, x0 + P)[None, :], H, I["w"], I["h"])]
            wpx[wat] = 0.2
            kw = known * wpx; kn = max(float(kw.sum()), 1.0)
            # candidate blocks
            by = self.cy[idx] * Q; bx = self.cx[idx] * Q
            blocks = np.stack([B0[a:a + P, b:b + P] for a, b in zip(by, bx)])
            blocks = np.stack([self.shift_dry(bk, td[0]) for bk in blocks]) if td[0][0] > 0.3 else blocks
            ov = (mismatch(blocks, old[None]) * kw[None]).sum((1, 2)) / kn if kn > 1 else np.zeros(len(idx), np.float32)
            # per-cell terrain correspondence on the domain cells
            sl = (slice(yc, yc + n), slice(xc, xc + n))
            tsb, twb, trb = C["sbin"][sl], C["wbin"][sl], C["rbin"][sl]
            dsb = np.stack([C["sbin"][a:a + n, b:b + n] for a, b in zip(self.cy[idx], self.cx[idx])])
            dwb = np.stack([C["wbin"][a:a + n, b:b + n] for a, b in zip(self.cy[idx], self.cx[idx])])
            drb = np.stack([C["rbin"][a:a + n, b:b + n] for a, b in zip(self.cy[idx], self.cx[idx])])
            gm = (0.6 * np.abs(dsb.astype(np.int16) - tsb) / 4.0 + 0.25 * (np.minimum(dwb, 2) != np.minimum(twb, 2))
                  + 0.15 * (drb != trb))
            gm = (gm * dmc[None]).sum((1, 2)) / max(int(dmc.sum()), 1)
            # land logic: a donor's mountain px should sit where vanilla puts mountain ground for this slope band
            dcold = FAM[blocks[:, Q // 2::Q, Q // 2::Q]] == 2
            pt = C["pcold"][sl]
            mm = (np.where(dcold, 1.0 - pt[None], pt[None]) * dmc[None]).sum((1, 2)) / max(int(dmc.sum()), 1)
            E = W_OV * ov + W_G * gm + W_M * mm + W_D * dcost + W_RE * self.used[idx]
            ok = np.nonzero(E <= E.min() + TOL)[0]
            j = int(ok[self.rng.integers(len(ok))])
            new = blocks[j]
            stats["shift"] += int(not np.array_equal(new, B0[by[j]:by[j] + P, bx[j]:bx[j] + P]))
            # graph cut: source = old, sink = new
            border = np.zeros((P, P), bool); border[0, :] = border[-1, :] = border[:, 0] = border[:, -1] = True
            must_old = ~dom | (border & (fil | soft))
            t1 = time.time()
            take = graph_cut(old, new, must_old, must_new, self._noise(y0, x0), wpx)
            stats["cut_ms"] += 1000 * (time.time() - t1)
            wr = take & dom
            old[wr] = new[wr]
            fil |= dom
            stats["px_new"] += int(wr.sum()); stats["windows"] += 1
            self.used[idx[j]] += 1
            gq = C["gcq"][sl][dmc]; gq = int(np.bincount(gq).argmax()) if len(gq) else int(I["gc"].max())
            key = (gq, int(self.creg[idx[j]])); donor_px[key] = donor_px.get(key, 0) + int(wr.sum())
            if stats["windows"] % 2000 == 0:
                log(f"  {stats['windows']:,} windows ({i + 1:,}/{len(windows):,} visited), {time.time() - t0:.0f}s")
        stats["cut_ms"] = round(stats["cut_ms"] / max(stats["windows"], 1), 2)
        stats["donor_reuse_max"] = int(self.used.max()); stats["donors_used"] = int((self.used > 0).sum())
        stats["seconds"] = round(time.time() - t0, 1)
        return stats, donor_px

    _NZ = None

    def _noise(self, y0, x0):
        """seam-cost multiplier: fractal noise with a wide range (x0.15 .. x4), so a min-cut through uniformly
        disagreeing px follows noise valleys (an irregular line) instead of the shortest, straight path."""
        if Quilter._NZ is None:
            S_ = 512 + P
            v = (smooth_noise((S_, S_), 6, SEED + 7) + 0.6 * smooth_noise((S_, S_), 16, SEED + 8) + 0.3 * smooth_noise((S_, S_), 3, SEED + 9))
            Quilter._NZ = np.exp(1.4 * v / v.std()).clip(0.15, 4.0).astype(np.float32)
        a, b = (y0 * 7 + x0 * 3) % 512, (x0 * 13 + y0 * 5) % 512
        return Quilter._NZ[a:a + P, b:b + P]


FAMX = FAM.astype(np.int16).copy(); FAMX[FAM == 0] = 100 + np.nonzero(FAM == 0)[0]     # specials: each its own family


def mismatch(a, b):
    """visual mismatch of two label arrays: 0 same class, 0.35 other variant of the same family, 1 other family."""
    return (a != b) * (1.0 - 0.65 * (FAMX[a] == FAMX[b]))


def graph_cut(old, new, must_old, must_new, noise, wpx, d=None):
    """Kwatra min-cut on a (P, P) window: True = take new. Edge cost = mismatch of old vs new at both px (x noise),
    lowered along existing label edges of old / new. d: optional precomputed per-px mismatch (other label sets)."""
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import maximum_flow, breadth_first_order
    ph, pw = old.shape; nn = ph * pw; S, T = nn, nn + 1
    if not must_old.any(): return np.ones(old.shape, bool)
    d = (mismatch(old, new) if d is None else d).astype(np.float32) * wpx
    idx = np.arange(nn).reshape(ph, pw)
    a, b, c = [], [], []
    for sa, sb in (((slice(None), slice(0, -1)), (slice(None), slice(1, None))),
                   ((slice(0, -1), slice(None)), (slice(1, None), slice(None)))):
        u = idx[sa].ravel(); v = idx[sb].ravel()
        edge = (old[sa] != old[sb]).astype(np.float32) + (new[sa] != new[sb])      # Kwatra: hide seams along class edges
        cap = (100 * (d[sa] + d[sb]) * noise[sa] / (1 + 2 * edge) + 1 + 2 * noise[sa]).ravel().astype(np.int32)
        a += [u, v]; b += [v, u]; c += [cap, cap]
    BIG = 1 << 28
    mo = idx[must_old]; mn = idx[must_new]
    a += [np.full(len(mo), S), mn]; b += [mo, np.full(len(mn), T)]
    c += [np.full(len(mo), BIG, np.int32), np.full(len(mn), BIG, np.int32)]
    a = np.concatenate(a); b = np.concatenate(b); c = np.concatenate(c).astype(np.int32)
    G = csr_matrix((c, (a, b)), shape=(nn + 2, nn + 2))
    r = maximum_flow(G, S, T, method="dinic")
    res = G - r.flow
    res.data[res.data < 0] = 0; res.eliminate_zeros()
    order = breadth_first_order(res, S, directed=True, return_predecessors=False)
    side = np.zeros(nn + 2, bool); side[order] = True
    return ~side[:nn].reshape(ph, pw)


# ------------------------------------------------------------------------------------------------------------ the edit
def synthesize(I, log=print):
    t0 = time.time()
    H, W, w, h, f, gc = I["H"], I["W"], I["w"], I["h"], I["f"], I["gc"]
    C = cell_maps(I, log); prior, grain_by_t = learn_priors(I, C, log)
    log(f"cell maps {C['Hq']}x{C['Wq']} ({time.time() - t0:.0f}s)")
    Qt = Quilter(I, C, prior, grain_by_t, log)
    dom_h = np.isin(gc, DOMAIN)
    fixed_land = (f["terr"] == 0) & ~dom_h
    soft_h = dom_h & (hex_edt(fixed_land) <= FEATHER)
    hr, hc = np.nonzero(dom_h)
    ylo = max(0, H - 8 * (hr.max() + 2) - 8); yhi = min(H, H - 8 * hr.min() + 8)
    xlo = max(0, 8 * hc.min() - 8); xhi = min(W, 8 * hc.max() + 16)
    rng = np.random.default_rng(SEED + 1)
    wins = []
    for y in range(ylo - OV, yhi, STEP):
        for x in range(xlo - OV, xhi, STEP):
            yy = int(np.clip(y + rng.integers(-JIT, JIT + 1), 0, H - P)); xx = int(np.clip(x + rng.integers(-JIT, JIT + 1), 0, W - P))
            wins.append((yy, xx))
    # windows touching the domain only
    def hexwin(fn):
        def g(y0, x0):
            r, c = px_hex(np.arange(y0, y0 + P)[:, None], np.arange(x0, x0 + P)[None, :], H, w, h)
            return fn[r, c]
        return g
    dom_fn, soft_fn = hexwin(dom_h), hexwin(soft_h)
    wins = [(y, x) for (y, x) in wins if dom_h[px_hex(np.array([y, y, y + P - 1, y + P - 1, y + P // 2]),
                                                       np.array([x, x + P - 1, x, x + P - 1, x + P // 2]), H, w, h)].any()
            or dom_fn(y, x)[::8, ::8].any()]
    if REGION is not None:                                 # tuning aid (--region y0,y1,x0,x1 px; dry only)
        y0r, y1r, x0r, x1r = REGION; wins = [(y, x) for (y, x) in wins if y0r <= y < y1r and x0r <= x < x1r]
    log(f"domain {int(dom_h.sum()):,} hexes ({', '.join(f'{GNAME[g]} {int((gc == g).sum()):,}' for g in DOMAIN)}); "
        f"{len(wins):,} target windows")
    canvas = I["B0"].copy()
    stats, donor_px = Qt.run(I["B0"], canvas, dom_fn, soft_fn, wins, log)
    log(f"quilting: {stats}")
    stats["warp_px"] = warp_domain(canvas, I, dom_h, fixed_land, log)
    # H2 check: mountain ground on flat passable land of the playable groups
    stats["h2_fixed_px"] = h2_fix(canvas, I, C, log)
    names = I["names"]
    nm = lambda k: names[k] if 0 <= k < len(names) else str(k)
    tot = {}
    for (g, k), v in donor_px.items(): tot[g] = tot.get(g, 0) + v
    stats["donor_regions"] = {}
    for g in sorted(tot):
        d = sorted(((k, v) for (gg, k), v in donor_px.items() if gg == g), key=lambda kv: -kv[1])
        stats["donor_regions"][GNAME[g]] = [(nm(k), round(100 * v / tot[g], 1)) for k, v in d[:12]]
        log(f"donor regions for {GNAME[g]} (% of its quilted px):", stats["donor_regions"][GNAME[g]][:8])
    return canvas, stats


_LAT = {}


def noise_at(y, x, cell, seed):
    """smooth lattice noise in [-1, 1] at pixel coords (blend_polish's), evaluated only where asked."""
    k = (cell, seed)
    if k not in _LAT:
        _LAT[k] = np.random.default_rng(seed).uniform(-1, 1, (9068 // cell + 3, 11824 // cell + 3)).astype(np.float32)
    g = _LAT[k]
    fy = np.asarray(y, np.float32) / cell; fx = np.asarray(x, np.float32) / cell
    y0 = np.clip(fy.astype(np.int32), 0, g.shape[0] - 2); x0 = np.clip(fx.astype(np.int32), 0, g.shape[1] - 2)
    ty = fy - y0; tx = fx - x0; ty = ty * ty * (3 - 2 * ty); tx = tx * tx * (3 - 2 * tx)
    return (g[y0, x0] * (1 - ty) * (1 - tx) + g[y0, x0 + 1] * (1 - ty) * tx
            + g[y0 + 1, x0] * ty * (1 - tx) + g[y0 + 1, x0 + 1] * ty * tx)


def warp_domain(canvas, I, dom_h, fixed_land, log=print):
    """Light domain warp of the quilted px (+-WARP_FINE px at 12 px + +-WARP_COARSE at 40 px): the remaining straight
    stretches of quilting seams become wavy. Tapered to 0 within ~1-2.5 hexes of the protected land (no new seam there);
    reads anywhere, writes domain px only. Shapes stay vanilla's (a warp, not a filter)."""
    H, W, w, h = I["H"], I["W"], I["w"], I["h"]
    taper = np.clip((hex_edt(fixed_land) - 1.0) / 1.5, 0, 1).astype(np.float32) * dom_h
    src = canvas.copy(); n = 0
    hr = np.nonzero(dom_h.any(1))[0]
    ylo = max(0, H - 8 * (hr.max() + 2) - 8); yhi = min(H, H - 8 * hr.min() + 8)
    for y0 in range(ylo, yhi, 256):
        y1 = min(yhi, y0 + 256)
        yy, xx = np.mgrid[y0:y1, 0:W]
        rf = (H - 0.5 - yy) / 8.0 - 0.5; cf = (xx + 0.5) / 8.0 - 0.5
        tp = ndi.map_coordinates(taper, [rf.ravel(), cf.ravel()], order=1, mode="nearest").reshape(yy.shape)
        r, c = px_hex(yy, xx, H, w, h)
        tp *= dom_h[r, c]
        if not (tp > 0).any(): continue
        dx = tp * (WARP_FINE * noise_at(yy, xx, 12, 401) + WARP_COARSE * noise_at(yy, xx, 40, 402))
        dy = tp * (WARP_FINE * noise_at(yy, xx, 12, 403) + WARP_COARSE * noise_at(yy, xx, 40, 404))
        sy = np.clip(np.rint(yy + dy), 0, H - 1).astype(np.int64); sx = np.clip(np.rint(xx + dx), 0, W - 1).astype(np.int64)
        v = src[sy, sx]; o = canvas[y0:y1]
        wr = (tp > 0) & (v != o)
        o[wr] = v[wr]; n += int(wr.sum())
    log(f"warp: {n:,} px")
    return n


def h2_fix(canvas, I, C, log=print):
    """Only if a group is over FLAT_MTN_MAX (hex-centre measure): mountain px on flat passable CELLS of that group
    (slope band <= 1, not impassable; pixel level, so the edge follows the slope contour, not the hex staircase) take
    the value of the nearest non-mountain natural px (keeps the neighbours' patch shapes)."""
    f, gc, H, W = I["f"], I["gc"], I["H"], I["W"]
    flat = (f["terr"] == 0) & (f["imp"] == 0) & (I["s5"] < FLAT_SLOPE)
    Bh = canvas[I["py"], I["px"]]
    fixed = 0
    for g in (HEXI, NOMAD, KNE):
        m = flat & (gc == g)
        if not m.any(): continue
        pct = 100 * float(np.isin(Bh[m], [4, 5, 6, 7]).mean())
        log(f"  flat mountain ground {GNAME[g]}: {pct:.1f}% (limit {FLAT_MTN_MAX}%)")
        if pct <= FLAT_MTN_MAX: continue
        cm = (C["gcq"] == g) & (C["sbin"] <= 1) & ~C["imp"]
        rr, _ = np.nonzero(cm)
        for ya in range(Q * int(rr.min()), min(H, Q * int(rr.max()) + Q), 512):
            yb = min(H, ya + 512); a0, a1 = max(0, ya - 32), min(H, yb + 32)
            blk = canvas[a0:a1]
            yy = np.minimum(np.arange(a0, a1) // Q, C["Hq"] - 1); xx = np.minimum(np.arange(W) // Q, C["Wq"] - 1)
            sel = cm[yy][:, xx] & (FAM[blk] == 2)
            sel[:ya - a0] = False; sel[yb - a0:] = False
            if not sel.any(): continue
            src = (FAM[blk] > 0) & (FAM[blk] != 2)
            if not src.any(): continue
            _, (iy, ix) = ndi.distance_transform_edt(~src, return_indices=True)
            blk[sel] = blk[iy[sel], ix[sel]]; fixed += int(sel.sum())
    return fixed


# ------------------------------------------------------------------------------------------------------------ metrics
def _runs_ge(e, L):
    """count of runs of True of length >= L along axis 1 of a 2-D bool array."""
    d = np.diff(np.pad(e.astype(np.int8), ((0, 0), (1, 1))), axis=1)
    s = np.nonzero(d == 1); t = np.nonzero(d == -1)
    return int(((t[1] - s[1]) >= L).sum())


def metrics(B, I, sample_windows=True):
    """per group (+ vanilla): transitions per land hex, hex-border share, flat-mountain share, long straight boundary runs
    per 1000 hexes, class histogram distance to vanilla same climate, patch size / shape statistics."""
    H, W, w, h, f, gc = I["H"], I["W"], I["w"], I["h"], I["f"], I["gc"]
    land = f["terr"] == 0
    G = list(DOMAIN) + [VAN]
    ng = 8
    trans = np.zeros(ng); hexb = np.zeros(ng); tot_h = np.zeros(ng); runs = np.zeros(ng)
    hist = np.zeros((ng, 5, 256))
    TILE = 256; L = 40
    for y0 in range(0, H - 1, TILE):
        y1 = min(H - 1, y0 + TILE)
        blk = B[y0:y1 + 1]
        yy, xx = np.mgrid[y0:y1, 0:W]
        r, c = px_hex(yy, xx, H, w, h)
        g = gc[r, c]; cl = f["climate"][r, c]; ld = land[r, c]
        dh = np.zeros((y1 - y0, W), bool); dh[:, 1:] = blk[:-1, 1:] != blk[:-1, :-1]
        dv = blk[1:] != blk[:-1]
        trans += np.bincount(g[ld & dh], minlength=ng) + np.bincount(g[ld & dv], minlength=ng)
        ondiv = (xx % 8 == 0) & dh
        hexb += np.bincount(g[ld & ondiv], minlength=ng); tot_h += np.bincount(g[ld & dh], minlength=ng)
        b = blk[:-1]
        np.add.at(hist, (g[ld], np.minimum(cl[ld], 4), b[ld]), 1)
        # long straight boundaries: horizontal boundary runs (between rows) and vertical (between columns), by group
        for gg in G:
            m = (g == gg) & ld
            if not m.any(): continue
            runs[gg] += _runs_ge(dv & m, L) + _runs_ge((dh & m).T, L)
    nh = np.bincount(gc[land], minlength=ng).astype(float)
    out = {}
    vhist = hist[VAN]
    for gg in G:
        d = dict(land_hexes=int(nh[gg]))
        if nh[gg] == 0: out[GNAME[gg]] = d; continue
        d["transitions_per_hex"] = round(float(trans[gg] / nh[gg]), 2)
        d["hex_border_pct"] = round(float(100 * hexb[gg] / max(tot_h[gg], 1)), 1)
        d["straight_runs_per_1k_hex"] = round(float(1000 * runs[gg] / nh[gg]), 2)
        dist = {}
        for cl in range(5):
            a = hist[gg, cl]; v = vhist[cl]
            if a.sum() < 64 * 2000 or v.sum() == 0: continue
            dist[cl] = round(float(np.abs(a / a.sum() - v / v.sum()).sum() / 2), 3)       # total variation 0..1
        d["class_tv_vs_vanilla_by_climate"] = dist
        out[GNAME[gg]] = d
    # flat mountain (hex centres, blend_polish's measure)
    Bh = B[I["py"], I["px"]]
    flat = land & (f["imp"] == 0) & (I["s5"] < FLAT_SLOPE)
    for gg in G:
        m = flat & (gc == gg)
        if m.sum() > 50: out[GNAME[gg]]["flat_mountain_pct"] = round(100 * float(np.isin(Bh[m], [4, 5, 6, 7]).mean()), 1)
    if sample_windows:
        for gg in G:
            if nh[gg] == 0: continue
            out[GNAME[gg]].update(patch_stats(B, I, gg))
    return out


def sample_windows(I, g, n=24, S=256, seed=3):
    H, W, w, h, gc, f = I["H"], I["W"], I["w"], I["h"], I["gc"], I["f"]
    rng = np.random.default_rng(seed)
    rr, cc = np.nonzero(gc == g)
    if not len(rr): return []
    wins = []; tries = 0
    while len(wins) < n and tries < 4000:
        tries += 1
        k = rng.integers(len(rr)); r, c = rr[k], cc[k]
        y0 = H - 8 * r - S // 2; x0 = 8 * c - S // 2
        if y0 < 0 or x0 < 0 or y0 + S > H or x0 + S > W: continue
        ys = np.arange(y0, y0 + S, 16); xs = np.arange(x0, x0 + S, 16)
        r2, c2 = px_hex(ys[:, None], xs[None, :], H, w, h)
        if (gc[r2, c2] == g).mean() < 0.95: continue
        if any(abs(y0 - a) < S and abs(x0 - b) < S for a, b in wins): continue
        wins.append((y0, x0))
    return wins


def patch_stats(B, I, g, S=256):
    """same-class connected patches (4-conn) in sampled 256 px windows fully inside the group: size (hexes), shape
    index P / (4 sqrt A) (1 = square; larger = more ragged), fractal dimension D from log P ~ D/2 log A."""
    sizes, perims = [], []
    for y0, x0 in sample_windows(I, g, S=S):
        blk = B[y0:y0 + S, x0:x0 + S]
        for k in np.unique(blk):
            m = blk == k
            lab, nl = ndi.label(m)
            if nl == 0: continue
            sz = np.bincount(lab.ravel())[1:]
            # perimeter: count of 4-neighbour edges to other classes (incl. window border not counted)
            pe = np.zeros(nl + 1)
            e1 = m[:, 1:] != m[:, :-1]; e2 = m[1:] != m[:-1]
            np.add.at(pe, lab[:, 1:][e1], 1); np.add.at(pe, lab[:, :-1][e1], 1)
            np.add.at(pe, lab[1:][e2], 1); np.add.at(pe, lab[:-1][e2], 1)
            pe = pe[1:]
            touch = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
            keep = np.ones(nl, bool); keep[touch[touch > 0] - 1] = False
            sizes.append(sz[keep]); perims.append(pe[keep])
    if not sizes: return {}
    A = np.concatenate(sizes).astype(float); Pm = np.concatenate(perims)
    big = A >= 16
    D = float(2 * np.polyfit(np.log(A[big]), np.log(np.maximum(Pm[big], 1)), 1)[0]) if big.sum() > 20 else None
    # area-weighted size (what the eye sees): the patch size a random px lies in
    return dict(patch_px_median=float(np.median(A)), patch_hex_area_weighted=round(float((A * A).sum() / A.sum() / 64), 2),
                patch_shape_index=round(float(np.median(Pm[big] / (4 * np.sqrt(A[big])))), 2) if big.any() else None,
                fractal_dim=None if D is None else round(D, 3), patches_per_hex=round(float(len(A) / (len(sizes) and 1) / 1), 1))


# ------------------------------------------------------------------------------------------------------------ previews
BASE = {"arid": (214, 170, 110), "cold": (150, 110, 100), "grain": (200, 190, 90), "rice": (120, 170, 90), "tea": (80, 140, 70),
        "road": (90, 90, 90), "mud": (110, 90, 60), "shroud": (60, 60, 60), "steppe": (150, 170, 90), "subtrop": (70, 140, 60),
        "temperate": (100, 160, 90), "wetlands": (60, 120, 130)}
_F = ["arid"] * 4 + ["cold"] * 4 + ["grain"] * 2 + ["rice"] * 2 + ["tea", "road", "mud"] + ["shroud"] * 4 + ["steppe"] * 4 + ["subtrop"] * 4 + ["temperate"] * 4 + ["wetlands"]
_IDX = [0, 1, 2, 3, 0, 1, 2, 3, 0, 1, 0, 1, 0, 0, 0, 0, 1, 2, 3, 0, 1, 2, 3, 0, 1, 2, 3, 0, 1, 2, 3, 0]
LUT = np.zeros((256, 3), np.uint8)
for _i in range(32): LUT[_i] = np.clip(np.array(BASE[_F[_i]], float) * (1.15 - 0.12 * _IDX[_i]), 0, 255)
LUT[4:8] = [(205, 95, 80), (185, 85, 75), (165, 75, 70), (145, 65, 65)]


def render(B, hgt, y0, y1, x0, x1, step):
    b = B[y0:y1:step, x0:x1:step]; hh = hgt[y0:y1:step, x0:x1:step].astype(np.float32)
    gy, gx = np.gradient(hh); shade = np.clip(1 + (-gx + gy) / (250 * step), 0.5, 1.3)
    rgb = LUT[b].astype(np.float32) * shade[..., None]
    rgb[hh < 14219] = (40, 70, 120)
    return np.clip(rgb, 0, 255).astype(np.uint8)


def world_px(x, z):
    return int((874.18 - z) / 0.0964), int(x / 0.0834)


def preview_crops(I):
    names, reg, H = I["names"], I["f"]["region"], I["H"]
    rows, cols = np.indices(reg.shape)
    def centre(sel):
        r, c = rows[sel].mean(), cols[sel].mean(); return int(H - 8 * r), int(8 * c)
    ids = lambda *ks: np.isin(reg, [i for i, n in enumerate(names) if any(n.startswith("ironic_region_" + k + "_") for k in ks)])
    hexi_c = centre(I["gc"] == HEXI)
    ey = I["edge_y"]
    # (centre y, centre x, vanilla reference centre, label)
    van_arid = world_px(362.5, 695.0)        # vanilla Shuofang (3k_main_shoufang_resource_2, arid steppe)
    van_temp = world_px(560, 600)            # vanilla Hebei (the user's reference shot)
    van_ne = world_px(743.6, 708.2)          # vanilla Liaodong (3k_dlc06_liaodong_capital)
    return {"ordos_430_705": (*world_px(430, 705), van_arid), "north_480_760": (*world_px(480, 760), van_arid),
            "steppe_north_band": (ey - 60, 7300, van_temp), "korea_ne_buyeo_hyunto": (*centre(ids("buyeo", "hyunto")), van_ne),
            "hexi_corridor": (*hexi_c, van_arid), "padding_nw": (ey + 300, 900, van_arid),
            "comb_old_edge": (ey, 5400, van_arid)}


def previews(Bcur, B1, I, crops, out_dir=None, size=(800, 1100), step=2):
    out_dir = out_dir or OUT
    from PIL import ImageDraw
    out_dir.mkdir(parents=True, exist_ok=True)
    H, W, hgt = I["H"], I["W"], I["hgt"]
    files = []
    for name, (cy, cx, (vy, vx)) in crops.items():
        hh, ww = size
        def box(y, x):
            y0 = int(np.clip(y - hh // 2, 0, H - hh)); x0 = int(np.clip(x - ww // 2, 0, W - ww)); return y0, y0 + hh, x0, x0 + ww
        a = render(Bcur, hgt, *box(vy, vx), step) if vy is not None else None
        b0 = box(cy, cx)
        b = render(Bcur, hgt, *b0, step); c = render(B1, hgt, *b0, step)
        sep = np.full((b.shape[0], 6, 3), 255, np.uint8)
        im = Image.fromarray(np.concatenate([a, sep, b, sep, c], 1))
        d = ImageDraw.Draw(im)
        d.text((6, 4), "VANILLA reference (same scale)", fill=(255, 255, 255))
        d.text((b.shape[1] + 12, 4), f"CURRENT (in game)  {name}  px y{b0[0]}-{b0[1]} x{b0[2]}-{b0[3]}  1:{step}", fill=(255, 255, 255))
        d.text((2 * b.shape[1] + 18, 4), "V2 (quilted from vanilla)", fill=(255, 255, 255))
        p = out_dir / f"v2_{name}.png"; im.save(p, optimize=True); files.append(p.name)
        # 1:1 zoom of the centre (vanilla | current | v2), 360 x 360 px each
        zy, zx = (b0[0] + b0[1]) // 2 - 180, (b0[2] + b0[3]) // 2 - 180
        vy0, vx0 = int(np.clip(vy - 180, 0, H - 360)), int(np.clip(vx - 180, 0, W - 360))
        z = [render(Bcur, hgt, vy0, vy0 + 360, vx0, vx0 + 360, 1), render(Bcur, hgt, zy, zy + 360, zx, zx + 360, 1),
             render(B1, hgt, zy, zy + 360, zx, zx + 360, 1)]
        sep = np.full((360, 6, 3), 255, np.uint8)
        Image.fromarray(np.concatenate([z[0], sep, z[1], sep, z[2]], 1)).save(out_dir / f"v2_{name}_zoom1to1.png", optimize=True)
    return files


def overview(Bcur, B1, I, out_dir=None):
    out_dir = out_dir or OUT
    H, W = I["H"], I["W"]
    hgt = I["hgt"]
    y1 = min(H, I["edge_y"] + 8 * 420)
    a = render(Bcur, hgt, 0, y1, 0, W, 8); b = render(B1, hgt, 0, y1, 0, W, 8)
    sep = np.full((6, a.shape[1], 3), 255, np.uint8)
    Image.fromarray(np.concatenate([a, sep, b], 0)).save(out_dir / "v2_overview_north_current_vs_v2.png", optimize=True)


# ------------------------------------------------------------------------------------------------------------ main
def tiff_tags(path_or_buf):
    im = Image.open(path_or_buf)
    return im.mode, im.size, len(im.getpalette() or []), {k: v for k, v in im.tag_v2.items() if k not in (273, 279)}


def main(dry=False):
    if MARK.exists() and not dry:
        print("blend v2 already applied:", MARK.read_text()); return
    if not dry and (BACKUP / BLEND.name).exists():
        print(f"backup {BACKUP / BLEND.name} exists but no marker: restore or delete it first"); return
    t0 = time.time()
    I = load_inputs()
    Bcur = np.array(Image.open(BLEND))
    print(f"loaded {I['W']}x{I['H']} (pre-polish input), {I['w']}x{I['h']} hexes, old north edge y={I['edge_y']} ({time.time() - t0:.0f}s)")
    B1, stats = synthesize(I)
    # protected / non-domain px must equal the INPUT (pre-polish); report where the current file differs outside
    H, w, h = I["H"], I["w"], I["h"]
    dom_h = np.isin(I["gc"], DOMAIN)
    chg_out = 0; cur_out = 0
    for y0 in range(0, H, 512):
        yy, xx = np.mgrid[y0:min(H, y0 + 512), 0:I["W"]]
        r, c = px_hex(yy, xx, H, w, h); nd = ~dom_h[r, c]
        chg_out += int((nd & (B1[y0:y0 + 512] != I["B0"][y0:y0 + 512])).sum())
        cur_out += int((nd & (Bcur[y0:y0 + 512] != I["B0"][y0:y0 + 512])).sum())
    print(f"outside the domain: changed vs input {chg_out} px (must be 0); current file differs from the pre-polish input "
          f"there on {cur_out:,} px (blend_polish edits outside v2's domain, reverted by v2)")
    assert chg_out == 0
    print("metrics ...")
    m_pre = metrics(I["B0"], I); m_cur = metrics(Bcur, I); m_new = metrics(B1, I)
    rep = dict(pre_polish=m_pre, current_in_game=m_cur, v2=m_new, stats=stats, outside_domain_current_vs_pre_px=cur_out,
               ts=time.strftime("%Y%m%d_%H%M%S"), params=dict(P=P, OV=OV, K=K, TOL=TOL, W=(W_OV, W_G, W_D, W_RE),
                                                            NPOLD_ROW=NPOLD_ROW, FEATHER=FEATHER, SEED=SEED))
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump(rep, open(OUT / ("metrics_dry.json" if dry else "metrics_applied.json"), "w"), indent=1, default=str)
    print_table(m_pre, m_cur, m_new, OUT / ("metrics_dry.txt" if dry else "metrics_applied.txt"))
    res = Image.fromarray(B1, "P"); res.putpalette(I["pal"])
    buf = io.BytesIO(); res.save(buf, format="TIFF", compression="tiff_lzw"); buf.seek(0)
    t_in, t_out = tiff_tags(BLEND), tiff_tags(buf)
    same = t_in == t_out
    print("TIFF format identical:", same, "" if same else f"\n  in  {t_in}\n  out {t_out}")
    files = previews(Bcur, B1, I, preview_crops(I)); overview(Bcur, B1, I)
    print("previews:", files)
    if dry:
        print(f"dry run: nothing written outside {OUT} ({time.time() - t0:.0f}s)"); return rep
    assert same, "TIFF format would change"
    BACKUP.mkdir(exist_ok=True); shutil.copy2(BLEND, BACKUP / BLEND.name)
    BLEND.write_bytes(buf.getvalue())
    MARK.write_text(json.dumps(dict(ts=rep["ts"], input=str(SRC), stats={k: v for k, v in stats.items() if k != "donor_regions"})))
    print("wrote", BLEND, "backup", BACKUP, "marker", MARK, f"({time.time() - t0:.0f}s)")
    return rep


def print_table(a, b, c, path):
    keys = ("transitions_per_hex", "hex_border_pct", "straight_runs_per_1k_hex", "flat_mountain_pct", "patch_hex_area_weighted",
            "patch_shape_index", "fractal_dim")
    lines = [f"{'group':16s} {'metric':26s} {'pre-polish':>10s} {'current':>10s} {'v2':>10s}   vanilla"]
    for g in a:
        if g == "vanilla": continue
        for k in keys:
            if k not in a[g] and k not in c[g]: continue
            fm = lambda d: f"{d.get(k)}" if d.get(k) is not None else "-"
            lines.append(f"{g:16s} {k:26s} {fm(a[g]):>10s} {fm(b[g]):>10s} {fm(c[g]):>10s}   {fm(c['vanilla'])}")
        lines.append(f"{g:16s} {'class TV vs vanilla/clim':26s} {str(a[g].get('class_tv_vs_vanilla_by_climate')):>10s} -> "
                     f"{str(c[g].get('class_tv_vs_vanilla_by_climate'))}")
    txt = "\n".join(lines); print(txt); Path(path).write_text(txt + "\n", encoding="utf-8")


REGION = None
if __name__ == "__main__":
    if "--region" in sys.argv:
        REGION = tuple(int(v) for v in sys.argv[sys.argv.index("--region") + 1].split(","))
        assert "--dry" in sys.argv, "--region is a dry-run tuning aid"
        OUT = OUT / "_region"
    main(dry="--dry" in sys.argv)
