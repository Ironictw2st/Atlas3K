#!/usr/bin/env python3
"""Heightmap polish for the new areas: H1 + M4 + the height part of M5 of docs/proposals/new_areas_lookover.md.

terrain/3k_dlc07_main_map.height.191fd803c1a801d.tif: u16, 8 px / hex, row 0 = north, sea level 14219.
Pixel -> hex as the proposal's step detector (py/steps.py): c = x // 8, r = (H - 1 - y - 4 (c & 1)) // 8.

Passes (in this order, each a tiled pass over the raster with a halo, so memory stays < ~1.5 GB):
  M5  knee   np_new (non-playable padding, terrain/pad_mask.png) heights above K (= np_new land p85) are soft-kneed
             K + A (1 - exp(-(v - K) / A)), A = 65535 - MARGIN - K (slope 1 at K, never reaches 65535). The flat tops
             at 65535 (dem_fill's quantile map clamps every DEM metre above ~4600 m) first get their relief back:
             v = 65535 + S (m - m0), m = the DEM metres under the pixel (dem_fill.mosaic / sample), m0 = the median
             metres on the plateau's rim, S = the slope of dem_fill's metre -> u16 map at the top (Q-Q fit on the
             padding). Weight ramps 0 -> 1 over KNEE_IN px inside np_new, so playable / np_old ground is untouched.
  H1  steps  masked Gaussian (sigma SIG, ITERS iterations, surrounding ground as the boundary condition, feathered over
             FEATHER px) on: isolated one-pixel steps (the step detector, |d| > 150 with both neighbouring diffs
             < |d| / 8) grown by STEP_GROW px outside vanilla 3k_* regions, the hexi_geo ramp band (0 < w < 1), the
             Hexi zone edge (+-EDGE px; the hard rectangle), then a lighter pass (BAND_SIG) over the
             old 190E north edge band (hex rows 1040-1075 +-10 px), then a clean-up pass on any step left.
  M5  west   the west edge is blended toward the inner ground mirrored about x = WEST (lightly smoothed): weight 1 up to
             WEST_FULL px (14 hex columns), smoothstep to 0 at WEST px (20 columns); no hard clamp, no edge-parallel
             streaks. Wider than the proposal's 12 columns: there the Hexi zone starts at hex column 3 and its whole
             12-hex ramp band (columns 3-15) is two-projection artefact, so 12 columns left a straight ridge at ~px 100-140.
  M4  rivers river hexes of hexi / korea_ne (land, map.hex river edges): depth per hex = hex mean - p25 of the non-river
             land within 3 hexes, capped at CAP, smoothed along the river, faded out over MOUTH hexes at river mouths
             (sea / lake), where the river leaves hexi / korea_ne, and next to towns. Pixels: full depth on the rounded
             river band (hex mask blurred, iso 0.5), a smoothstep profile PROF px (2 hexes) out from it, Gaussian 5 px;
             never below sea + 400.
Never touched (all passes; feathered): pixels below sea + 300, sea / beach hex pixels (coast_carve's work), the
3k_main_sea_lake hexes + LAKE_RING hexes (kit_edits lake-build reshapes them), Tamna (kit_edits terrain-scale disc,
TAMNA_R world units around (869.0, 489.52)). H1 never RAISES river-hex pixels outside the ramp band / zone edge /
north band (lower-only, feathered 6 px; inside those artefact zones the river beds are waffle too, and keeping them
left jagged hex-staircase trenches), and the hexi / korea_ne river hexes that M4 carves right after are
smoothed freely (else their 1-px steps survive inside the new valley floor).

ONE-OFF, in place (marker hex/.terrain_polish); backup terrain/_pre_terrain_polish/. Refuses to run twice.
  python terrain_polish.py --dry   metrics + previews to output/polish/terrain/, nothing written in terrain/ or hex/
  python terrain_polish.py         apply (relief_build.sh then copies the height into the kit; kit_edits.py replays
                                   lake-build and the Tamna x0.6 on top)
If the terrain chain (terrain_main -> dem_fill -> coast_carve -> ... -> ranges_relief) is ever rerun, delete the
marker and run this again (hexi_geo.weight / dem_fill.sample now remove the cause of H1, but M4 / M5 still apply)."""
import json, shutil, sys, time
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
Image.MAX_IMAGE_PIXELS = None
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent, HERE.parent.parent / "output" / "pylibs"): sys.path.insert(0, str(p))
HEIGHT = HERE / "terrain" / "3k_dlc07_main_map.height.191fd803c1a801d.tif"
PAD = HERE / "terrain" / "pad_mask.png"
MARK = HERE / "hex" / ".terrain_polish"
BACKUP = HERE / "terrain" / "_pre_terrain_polish"
OUT = HERE.parent.parent / "output" / "polish" / "terrain"

SEA = 14219; GUARD = SEA + 300; FLOOR = SEA + 400
TS = 1024                                                   # tile core size (px)
# H1
STEP_THR, STEP_GROW, EDGE, FEATHER = 150, 8, 24, 12
SIG, ITERS, BAND_SIG, BAND_ITERS = 7.0, 3, 5.0, 2
NB_HEX_ROWS, NB_PAD = (1040, 1075), 10
PROT_FEATHER, ZONE_FEATHER = 6, 16
# protected zones
LAKE_REGION, LAKE_RING = "3k_main_sea_lake", 3
TAMNA, TAMNA_R = (869.0, 489.52), 27.0                      # world; kit_edits terrain-scale radius 25 (+2)
# M4
CAP, PROF, MOUTH, NEIGH = 1500, 16, 3, 3
# M5
KNEE_PCT, MARGIN, KNEE_IN, WEST, WEST_FULL, WEST_SIG = 85, 200, 80, 160, 112, 24.0
HX, HZ = 0.668, 0.772


def ss(t):
    t = np.clip(t, 0, 1); return t * t * (3 - 2 * t)


def group_of(n):
    if n.startswith('ironic_hexi_'): return 'hexi'
    if n.startswith('ironic_nomad_'): return 'nomad'
    if n.startswith('ironic_central_'): return 'central'
    if n.startswith('ironic_south_'): return 'south'
    if n.startswith('ironic_sea_'): return 'sea'
    if n.startswith('ironic_region_'):
        if any(n.startswith('ironic_region_' + k) for k in ('hanyang', 'xi_', 'wuwei', 'xiping')): return 'hexi'
        if n.startswith('ironic_region_wuyuan'): return 'nomad'
        return 'korea_ne'
    return 'vanilla'


GROUPS = ['vanilla', 'np_old', 'np_new', 'hexi', 'nomad', 'central', 'korea_ne', 'south']


def edt_or(mask, big=1e4):
    """distance (px) to the nearest True of mask; big where mask has no True."""
    if not mask.any(): return np.full(mask.shape, big, np.float32)
    return ndi.distance_transform_edt(~mask).astype(np.float32)


def step_pixels(A):
    """the proposal's step detector (py/steps.py) on array A (int32): both axes, bool at the first pixel of the jump."""
    out = np.zeros(A.shape, bool)
    for ax in (0, 1):
        a = np.abs(np.diff(A, axis=ax))
        if ax == 1:
            l = np.pad(a[:, :-1], ((0, 0), (1, 0))); r = np.pad(a[:, 1:], ((0, 0), (0, 1)))
            s = (a > STEP_THR) & (l < a / 8) & (r < a / 8); out[:, :-1] |= s
        else:
            l = np.pad(a[:-1], ((1, 0), (0, 0))); r = np.pad(a[1:], ((0, 1), (0, 0)))
            s = (a > STEP_THR) & (l < a / 8) & (r < a / 8); out[:-1] |= s
    return out


class Ctx:
    def __init__(self):
        import town_fix as T
        from hexgrid import neighbour_arrays
        _, _, w, h, _, f, names = T.load(str(HERE / "hex" / "map.hex"))
        self.w, self.h, self.f, self.names = w, h, f, names
        self.Hm = np.array(Image.open(HEIGHT)); self.H, self.W = self.Hm.shape
        assert self.Hm.dtype == np.uint16 and self.H >= 8 * h and self.W == 8 * w
        reg = f["region"]; land = f["terr"] == 0
        gn = np.array([group_of(n) for n in names] + ['sea'], dtype=object)
        G = gn[np.where(reg >= 0, reg, len(names))].copy()
        npk = names.index('3k_main_reg_non_playable')
        self.pad = np.array(Image.open(PAD)) > 0
        padhex = self.sample_hex(self.pad)
        G[(reg == npk) & padhex] = 'np_new'; G[(reg == npk) & ~padhex] = 'np_old'
        self.G, self.land, self.npk = G, land, npk
        self.NA = neighbour_arrays(h, w)
        lake = reg == names.index(LAKE_REGION)
        ring = self.grow(lake, LAKE_RING)
        cc, rr = np.meshgrid(np.arange(w), np.arange(h))
        hx, hz = cc * HX, rr * HZ + (cc & 1) * HZ / 2
        tam = np.hypot(hx - TAMNA[0], hz - TAMNA[1]) <= TAMNA_R
        self.hx_lake, self.hx_lakering, self.hx_tamna = lake, ring, tam
        self.hx_zone = ring | tam
        self.hx_river = (f["river"] > 0)
        # H1 keeps every river hex except the M4 carve rivers (hexi / korea_ne land): M4 reshapes those anyway, and
        # protecting them left the 1-px steps inside the Hexi river beds that the carve then kept
        self.hx_carve = self.hx_river & land & np.isin(G, ['hexi', 'korea_ne'])
        self.hx_river_keep = self.hx_river & ~self.hx_carve
        self.hx_sea = f["terr"] != 0                        # sea / beach / cliff hexes: coast_carve's ground
        self.hx_vanilla = G == 'vanilla'
        self.hx_town = (f["slot"] >= 0) | (f["sprawl"] > 0)
        import hexi_geo
        zw = hexi_geo._zone()["w"]; assert zw.shape == (h, w)
        self.hx_w = zw
        # Tamna disc in pixels
        self.tam_px = (TAMNA[0] / HX * 8 + 4, self.H - TAMNA[1] / HZ * 8 - 4, TAMNA_R / HX * 8)
        self.stats = {}

    def grow(self, m, k):
        for _ in range(k):
            g = m.copy()
            for nr, nc, v in self.NA: g |= v & m[nr, nc]
            m = g
        return m

    def sample_hex(self, arr):
        rr, cc = np.indices((self.h, self.w)); H = arr.shape[0]
        px = 8 * cc + 4; py = H - 8 * rr - 4 - 4 * (cc & 1)
        return arr[np.clip(py, 0, H - 1), np.clip(px, 0, arr.shape[1] - 1)]

    def rc(self, y0, y1, x0, x1):
        c = np.clip(np.arange(x0, x1) // 8, 0, self.w - 1)[None, :]
        r = np.clip((self.H - 1 - np.arange(y0, y1)[:, None] - 4 * (c & 1)) // 8, 0, self.h - 1)
        return r, np.broadcast_to(c, r.shape)

    def tamna_px(self, y0, y1, x0, x1):
        cx, cy, R = self.tam_px
        return np.hypot(np.arange(x0, x1)[None, :] - cx, np.arange(y0, y1)[:, None] - cy) <= R

    def protect(self, T, y0, y1, x0, x1, rivers=True, extra=None):
        """0..1 'keep' weight: 1 on protected px, feathered."""
        r, c = self.rc(y0, y1, x0, x1)
        hard = (T < GUARD) | self.hx_sea[r, c]
        if rivers: hard |= self.hx_river_keep[r, c]
        if extra is not None: hard |= extra
        zone = self.hx_zone[r, c] | self.tamna_px(y0, y1, x0, x1)
        return np.maximum(1 - ss(edt_or(hard) / PROT_FEATHER), 1 - ss(edt_or(zone) / ZONE_FEATHER))

    def tiles(self, src, fn, halo, name, x_max=None):
        """dst = src with fn's result on every tile core. fn(T float32 tile incl. halo, y0, y1, x0, x1) -> tile or None."""
        t0 = time.time(); dst = src.copy(); H, W = src.shape; n = 0
        for ty in range(0, H, TS):
            for tx in range(0, W if x_max is None else min(W, x_max), TS):
                y0, y1 = max(0, ty - halo), min(H, ty + TS + halo); x0, x1 = max(0, tx - halo), min(W, tx + TS + halo)
                T = src[y0:y1, x0:x1].astype(np.float32)
                res = fn(T, y0, y1, x0, x1)
                if res is None: continue
                cy0, cx0 = ty - y0, tx - x0; cy1, cx1 = cy0 + min(TS, H - ty), cx0 + min(TS, W - tx)
                dst[ty:ty + (cy1 - cy0), tx:tx + (cx1 - cx0)] = np.clip(np.rint(res[cy0:cy1, cx0:cx1]), 0, 65535).astype(np.uint16)
                n += 1
        ch = int((dst != src).sum())
        print(f"  {name}: {n} tiles, {ch:,} px changed ({time.time() - t0:.0f} s)")
        self.stats[name] = dict(tiles=n, px_changed=ch)
        return dst

    # ------------------------------------------------------------------ metrics
    def step_count_hex(self, A):
        cnt = np.zeros((self.h, self.w), np.int64); H = A.shape[0]
        for y0 in range(0, H, 1024):
            y1 = min(H, y0 + 1024); ya, yb = max(0, y0 - 2), min(H, y1 + 2)
            B = A[ya:yb].astype(np.int32)
            for ax in (0, 1):
                a = np.abs(np.diff(B, axis=ax))
                if ax == 1:
                    l = np.pad(a[:, :-1], ((0, 0), (1, 0))); r = np.pad(a[:, 1:], ((0, 0), (0, 1)))
                else:
                    l = np.pad(a[:-1], ((1, 0), (0, 0))); r = np.pad(a[1:], ((0, 1), (0, 0)))
                s = (a > STEP_THR) & (l < a / 8) & (r < a / 8)
                ys, xs = np.nonzero(s); ys = ys + ya
                if ax == 0:      # interior chunk rows: neighbours exist across the overlap
                    ok = (ys >= y0) & (ys < y1) & ((ys - ya > 0) | (ya == 0)) & ((ys - ya < a.shape[0] - 1) | (yb == H))
                else:
                    ok = (ys >= y0) & (ys < y1)
                ys, xs = ys[ok], xs[ok]
                c = np.clip(xs // 8, 0, self.w - 1); rr = np.clip((H - 1 - ys - 4 * (c & 1)) // 8, 0, self.h - 1)
                np.add.at(cnt, (rr, c), 1)
        return cnt

    def steps_by_group(self, cnt):
        out = {}
        for g in GROUPS:
            m = (self.G == g) & self.land
            out[g] = round(1000 * float(cnt[m].sum()) / max(int(m.sum()), 1), 1)
        return out

    def neigh_offsets(self, k):
        from hexgrid import to_cube
        offs = []
        for p in (0, 1):
            base = (100 + p, 50); q0, r0, s0 = to_cube(*base); o = []
            for dc in range(-k, k + 1):
                for dr in range(-k - 1, k + 2):
                    q, r, s = to_cube(base[0] + dc, base[1] + dr)
                    d = max(abs(q - q0), abs(r - r0), abs(s - s0))
                    if 0 < d <= k: o.append((dc, dr))
            offs.append(o)
        return offs

    def neigh_vals(self, vals, valid, cs, rs, k):
        """(n, m) values of the hexes within k of (cs, rs); NaN where invalid / off-map."""
        offs = self.neigh_offsets(k); m = max(len(offs[0]), len(offs[1]))
        out = np.full((len(cs), m), np.nan, np.float64)
        for p in (0, 1):
            sel = np.nonzero((cs & 1) == p)[0]
            for j, (dc, dr) in enumerate(offs[p]):
                nc, nr = cs[sel] + dc, rs[sel] + dr
                ok = (nc >= 0) & (nc < self.w) & (nr >= 0) & (nr < self.h)
                ncc, nrr = np.clip(nc, 0, self.w - 1), np.clip(nr, 0, self.h - 1)
                v = np.where(ok & valid[nrr, ncc], vals[nrr, ncc], np.nan)
                out[sel, j] = v
        return out

    def river_high_share(self, A, groups=('hexi', 'korea_ne', 'nomad', 'central', 'vanilla')):
        hh = self.sample_hex(A).astype(np.float64)
        riv = self.hx_river & self.land
        out = {}
        for g in groups:
            rs, cs = np.nonzero(riv & (self.G == g))
            nv = self.neigh_vals(hh, self.land & ~self.hx_river, cs, rs, 3)
            with np.errstate(all='ignore'):
                mu = np.nanmean(nv, 1)
            ok = np.isfinite(mu)
            out[g] = round(100 * float((hh[rs, cs][ok] > mu[ok]).mean()), 1)
        return out

    def npnew_px(self, y0, y1, x0, x1):
        r, c = self.rc(y0, y1, x0, x1)
        return self.pad[y0:y1, x0:x1] & (self.f["region"][r, c] == self.npk)

    def sat_share(self, A):
        n = s = s2 = 0
        for y0 in range(0, self.H, 1024):
            y1 = min(self.H, y0 + 1024); m = self.npnew_px(y0, y1, 0, self.W) & (A[y0:y1] > GUARD)
            v = A[y0:y1][m]; n += v.size; s += int((v == 65535).sum()); s2 += int((v >= 65000).sum())
        return dict(sat_65535_pct=round(100 * s / max(n, 1), 3), ge_65000_pct=round(100 * s2 / max(n, 1), 3))

    def zone_change(self, A0, A1):
        """|change| (u16) on the lake hexes, the lake ring and Tamna."""
        out = {}
        for nm, hxm in (('lake_hexes', self.hx_lake), ('lake_ring3', self.hx_lakering), ('tamna_hexes', self.hx_tamna)):
            rs, cs = np.nonzero(hxm)
            if not len(rs): continue
            y0 = max(0, self.H - 8 * (rs.max() + 2)); y1 = min(self.H, self.H - 8 * (rs.min() - 1))
            x0, x1 = max(0, 8 * cs.min() - 8), min(self.W, 8 * cs.max() + 16)
            r, c = self.rc(y0, y1, x0, x1); m = hxm[r, c]
            d = np.abs(A1[y0:y1, x0:x1].astype(np.int32) - A0[y0:y1, x0:x1].astype(np.int32))[m]
            out[nm] = dict(px=int(m.sum()), max=int(d.max()), median=float(np.median(d)), mean=round(float(d.mean()), 2),
                           changed_px=int((d > 0).sum()))
        cx, cy, R = self.tam_px; y0, y1, x0, x1 = int(cy - R), int(cy + R) + 1, int(cx - R), int(cx + R) + 1
        m = self.tamna_px(y0, y1, x0, x1) & (A0[y0:y1, x0:x1] > SEA)
        d = np.abs(A1[y0:y1, x0:x1].astype(np.int32) - A0[y0:y1, x0:x1].astype(np.int32))[m]
        out['tamna_disc_land'] = dict(px=int(m.sum()), max=int(d.max()) if d.size else 0, median=float(np.median(d)) if d.size else 0.0)
        return out


# ---------------------------------------------------------------------------------------------- passes
def smooth_masked(T, M, P, sig, iters, LO=None):
    """masked Gaussian inside M (feathered FEATHER px), boundary = the ground around; P = keep weight;
    LO = 0..1 'lower only' weight (river hexes: the smoothing may lower them but never raise them)."""
    F = np.where(M, 1.0, 1 - ss(edt_or(M) / FEATHER)).astype(np.float32)
    F *= (1 - P)
    U = F > 0
    if not U.any(): return None
    V = (T >= GUARD).astype(np.float32)
    den = ndi.gaussian_filter(V, sig)
    X = T.copy()
    for _ in range(iters):
        num = ndi.gaussian_filter(X * V, sig)
        S = num / np.maximum(den, 1e-6)
        X = np.where(U & (den > 0.2), S, X)
    out = T + (X - T) * F
    if LO is not None: out = out * (1 - LO) + np.minimum(out, T) * LO
    return out


def pass_h1(ctx, src, kind):
    def fn(T, y0, y1, x0, x1):
        r, c = ctx.rc(y0, y1, x0, x1)
        landpx = T >= GUARD
        if not landpx.any(): return None
        wz = ctx.hx_w[r, c]; zone = wz > 0
        if zone.any() and not zone.all():
            edge = (zone & (edt_or(~zone) <= EDGE)) | (~zone & (edt_or(zone) <= EDGE))
        else:
            edge = np.zeros_like(zone)
        art = (zone & (wz < 1)) | edge                     # known artefact zones: ramp band + zone edge
        if kind == 'band':
            ys = np.arange(y0, y1)[:, None]
            yb0 = ctx.H - 8 * (NB_HEX_ROWS[1] + 1) - NB_PAD; yb1 = ctx.H - 1 - 8 * NB_HEX_ROWS[0] + NB_PAD
            M = np.broadcast_to((ys >= yb0) & (ys <= yb1), T.shape) & landpx
            art = art | M
            sig, it = BAND_SIG, BAND_ITERS
        else:
            st = step_pixels(T.astype(np.int32)) & landpx & ~ctx.hx_vanilla[r, c]
            st = ndi.binary_dilation(st, iterations=1)
            M = st if not st.any() else (edt_or(st) <= STEP_GROW)
            if kind == 'strong': M = M | art
            M = M & landpx
            sig, it = SIG, ITERS
        if not M.any(): return None
        P = ctx.protect(T, y0, y1, x0, x1, rivers=False)
        # river hexes: lower-only, except inside the artefact zones (there the river bed values are the waffle too;
        # keeping its minima left a jagged trench along the river)
        riv = ctx.hx_river_keep[r, c] & ~art
        LO = (1 - ss(edt_or(riv) / PROT_FEATHER)) if riv.any() else None
        return smooth_masked(T, M, P, sig, it, LO)
    halo = int(4 * SIG) * ITERS + EDGE + FEATHER + STEP_GROW + 4      # exact cores: 3 x the Gaussian reach
    return ctx.tiles(src, fn, halo, f"H1 {kind}")


def pass_west(ctx, src):
    """blend the outer WEST px toward the inner ground MIRRORED about x = WEST (smoothed, sigma WEST_SIG / 3): continuous
    at x = WEST, no edge-parallel ridge (a plain blur across the old strip made one) and no x-constant streaks."""
    def fn(T, y0, y1, x0, x1):
        if x0 > 0: return None
        V = (T >= GUARD).astype(np.float32); sg = WEST_SIG / 3
        S = ndi.gaussian_filter(T * V, sg) / np.maximum(ndi.gaussian_filter(V, sg), 1e-6)
        xs = np.arange(x0, x1)
        mir = np.clip(2 * WEST - xs, 0, x1 - x0 - 1)
        tgt = np.where(xs[None, :] < WEST, S[:, mir], T)
        wgt = np.broadcast_to(ss((WEST - xs) / (WEST - WEST_FULL))[None, :], T.shape).astype(np.float32)
        P = ctx.protect(T, y0, y1, x0, x1, rivers=True)
        wgt = wgt * (1 - P) * (V > 0) * (tgt >= GUARD)
        return T + (tgt - T) * wgt
    return ctx.tiles(src, fn, int(4 * WEST_SIG) + 8, "M5 west edge", x_max=TS)


def m4_depth(ctx, A):
    """per-hex carve depth (u16) for the hexi / korea_ne river hexes."""
    f, h, w = ctx.f, ctx.h, ctx.w
    # hex mean heights
    s = np.zeros(h * w); n = np.zeros(h * w)
    for y0 in range(0, ctx.H, 1024):
        y1 = min(ctx.H, y0 + 1024); r, c = ctx.rc(y0, y1, 0, ctx.W); idx = (r * w + c).ravel()
        s += np.bincount(idx, A[y0:y1].ravel().astype(np.float64), h * w); n += np.bincount(idx, minlength=h * w)
    hm = (s / np.maximum(n, 1)).reshape(h, w)
    car = ctx.hx_river & ctx.land & np.isin(ctx.G, ['hexi', 'korea_ne'])
    rs, cs = np.nonzero(car)
    nv = ctx.neigh_vals(hm, ctx.land & ~ctx.hx_river, cs, rs, NEIGH)
    with np.errstate(all='ignore'):
        p25 = np.nanpercentile(nv, 25, axis=1)
    D = np.zeros((h, w)); D[rs, cs] = np.clip(np.nan_to_num(hm[rs, cs] - p25, nan=0.0), 0, CAP)
    # smooth along the river (2 x mean with the carve neighbours)
    for _ in range(2):
        acc = D.copy(); cnt = car.astype(np.float64)
        for nr, nc, v in ctx.NA:
            ok = v & car[nr, nc]; acc += np.where(ok, D[nr, nc], 0); cnt += ok
        D = np.where(car, acc / np.maximum(cnt, 1), 0)
    water = f["terr"] == 1
    d_water = ndi.distance_transform_edt(~water)
    d_other = ndi.distance_transform_edt(~(ctx.hx_river & ~car))           # where the river leaves hexi / korea_ne
    d_town = ndi.distance_transform_edt(~ctx.hx_town)
    d_zone = ndi.distance_transform_edt(~ctx.hx_zone)
    fade = ss((d_water - 1) / MOUTH) * ss((d_other - 0.5) / MOUTH) * ss((d_town - 1) / 2) * ss((d_zone - 1) / 2)
    D = np.minimum(D * fade, CAP)
    ctx.stats["M4 hexes"] = dict(river_hexes=int(car.sum()), carved=int((D > 50).sum()),
                                 depth_mean=round(float(D[car].mean()), 1), depth_p90=round(float(np.percentile(D[car], 90)), 1),
                                 depth_max=round(float(D.max()), 1))
    print(f"  M4: {int(car.sum())} hexi/korea_ne river hexes, {int((D > 50).sum())} carved > 50, "
          f"mean {D[car].mean():.0f}, max {D.max():.0f} u16")
    return D


def pass_m4(ctx, src, D):
    def fn(T, y0, y1, x0, x1):
        r, c = ctx.rc(y0, y1, x0, x1)
        Dp = D[r, c]
        if not (Dp > 0).any(): return None
        core = ndi.gaussian_filter((Dp > 0).astype(np.float32), 5) > 0.5     # rounded river band (no hex staircase)
        if not core.any(): core = Dp > 0
        d, idx = ndi.distance_transform_edt(~core, return_indices=True)
        Dsrc = ndi.maximum_filter(Dp, 9)                                    # depth reaching the rounded core edge
        Dn = Dsrc[idx[0], idx[1]] * (1 - ss(d / PROF))
        depth = ndi.gaussian_filter(Dn.astype(np.float32), 5)
        P = ctx.protect(T, y0, y1, x0, x1, rivers=False, extra=ctx.hx_town[r, c])
        depth = depth * (1 - P)
        out = T - depth
        return np.maximum(out, np.minimum(T, FLOOR))
    return ctx.tiles(src, fn, PROF + 40, "M4 river carve")


def m5_prepare(ctx, A):
    """u16 'extra height above 65535' for the saturated np_new px (DEM relief), and K."""
    import terrain_main as TM, dem_fill as DF
    t0 = time.time()
    vals = []
    for y0 in range(0, ctx.H, 512):
        y1 = min(ctx.H, y0 + 512); m = ctx.npnew_px(y0, y1, 0, ctx.W) & (A[y0:y1] > GUARD)
        vals.append(A[y0:y1][m][::7])
    vals = np.concatenate(vals); K = float(np.percentile(vals, KNEE_PCT))
    sat = np.zeros(A.shape, bool)
    for y0 in range(0, ctx.H, 512):
        y1 = min(ctx.H, y0 + 512); sat[y0:y1] = ctx.npnew_px(y0, y1, 0, ctx.W) & (A[y0:y1] == 65535)
    ys, xs = np.nonzero(sat)
    extra = np.zeros(A.shape, np.uint16)
    if not len(ys): return K, extra, 0.0
    by0, by1, bx0, bx1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    print(f"  M5: K (np_new p{KNEE_PCT}) = {K:.0f}; {len(ys):,} saturated np_new px; loading DEM mosaic ...")
    mos = DF.mosaic()
    met = np.full((by1 - by0, bx1 - bx0), np.nan, np.float32)
    fit_m, fit_v = [], []
    for y0 in range(0, ctx.H, 256):
        y1 = min(ctx.H, y0 + 256)
        need_sat = y1 > by0 and y0 < by1
        sx, sy = TM.src_xy(TM.FULL, (7136, 5620), y0, y1)
        wx = (sx + 0.5) / 7136 * TM.OW; wz = (1 - (sy + 0.5) / 5620) * TM.OH
        a = A[y0:y1]; npn = ctx.npnew_px(y0, y1, 0, ctx.W)
        fm = npn & (a >= 56000) & (a < 65500)
        fm &= (np.arange(y0, y1)[:, None] % 4 == 0) & (np.arange(ctx.W)[None, :] % 4 == 0)
        if fm.any():
            fit_m.append(DF.sample(mos, wx[fm], wz[fm])); fit_v.append(a[fm].astype(np.float64))
        if need_sat:
            sm = sat[y0:y1]
            if sm.any():
                yy, xx = np.nonzero(sm)
                met[yy + y0 - by0, xx - bx0] = DF.sample(mos, wx[sm], wz[sm])
    del mos
    fm = np.concatenate(fit_m); fv = np.concatenate(fit_v); ok = np.isfinite(fm)
    q = np.linspace(0.05, 0.95, 19)
    S = float(np.polyfit(np.quantile(fm[ok], q), np.quantile(fv[ok], q), 1)[0])
    S = float(np.clip(S, 5, 60))
    satc = sat[by0:by1, bx0:bx1]
    lab, nlab = ndi.label(satc)
    rim = satc & ~ndi.binary_erosion(satc, border_value=1)
    rl = np.where(rim & np.isfinite(met), lab, 0)
    idx = np.arange(1, nlab + 1)
    m0 = np.array(ndi.median(np.nan_to_num(met), rl, idx), np.float64) if nlab else np.zeros(0)
    gm0 = float(np.nanmedian(met[rim])) if rim.any() else 0.0
    has = np.array(ndi.sum(rl > 0, rl, idx)) > 0 if nlab else np.zeros(0, bool)
    m0 = np.where(has & np.isfinite(m0), m0, gm0)
    lut = np.concatenate([[0.0], m0])
    ex = S * np.clip(np.nan_to_num(met - lut[lab], nan=0.0), 0, None)
    ex = np.where(satc, ex, 0)
    # light smoothing inside the plateaus (the DEM is already blurred; this only removes the per-pixel noise)
    num = ndi.gaussian_filter(ex.astype(np.float32), 2); den = ndi.gaussian_filter(satc.astype(np.float32), 2)
    ex = np.where(satc, num / np.maximum(den, 1e-6), 0)
    extra[by0:by1, bx0:bx1] = np.clip(np.rint(ex), 0, 65535).astype(np.uint16)
    print(f"  M5: DEM slope {S:.1f} u16/m, {nlab} plateaus, rim metres median {gm0:.0f}, "
          f"extra p50/p99/max {np.percentile(ex[satc], [50, 99]).round()} / {ex.max():.0f} ({time.time() - t0:.0f} s)")
    ctx.stats["M5 knee"] = dict(K=round(K), slope_u16_per_m=round(S, 2), plateaus=int(nlab), sat_px=int(len(ys)),
                                extra_p50=float(np.percentile(ex[satc], 50)), extra_max=float(ex.max()))
    return K, extra, S


def pass_m5_knee(ctx, src, K, extra):
    A_ = 65535 - MARGIN - K

    def fn(T, y0, y1, x0, x1):
        if T.max() <= K: return None
        npn = ctx.npnew_px(y0, y1, x0, x1)
        if not npn.any(): return None
        wgt = ss(edt_or(~npn) / KNEE_IN)                       # 0 at the np_new edge -> 1 KNEE_IN px inside
        V = T + extra[y0:y1, x0:x1].astype(np.float32)
        Fv = np.where(V > K, K + A_ * (1 - np.exp(-(V - K) / A_)), V)
        P = ctx.protect(T, y0, y1, x0, x1, rivers=False)
        return T + (Fv - T) * wgt * (1 - P)
    return ctx.tiles(src, fn, KNEE_IN + 8, "M5 knee")


# ---------------------------------------------------------------------------------------------- previews
def hillshade(A, z=0.02):
    A = A.astype(np.float32)
    gy, gx = np.gradient(A * z)
    sh = np.clip(150 - (gx + gy) * 35, 0, 255)
    return sh


def shade_rgb(A, sea_mask=None):
    sh = hillshade(A)
    v = np.clip((A.astype(np.float32) - SEA) / (65535 - SEA), 0, 1)
    rgb = np.stack([sh * (0.75 + 0.25 * v), sh * (0.8 + 0.1 * v), sh * (0.85 - 0.1 * v)], -1)
    if sea_mask is not None: rgb[sea_mask] = (90, 120, 170)
    return np.clip(rgb, 0, 255).astype(np.uint8)


def label(img, text):
    from PIL import ImageDraw
    d = ImageDraw.Draw(img); d.rectangle([0, 0, 8 * len(text) + 8, 16], fill=(0, 0, 0)); d.text((4, 2), text, fill=(255, 255, 0))
    return img


def previews(ctx, A0, A1, crops, D):
    OUT.mkdir(parents=True, exist_ok=True)
    k = 8
    def down(A):
        Hc = A.shape[0] // k * k; return A[:Hc].reshape(Hc // k, k, A.shape[1] // k, k).mean((1, 3))
    a0, a1 = down(A0), down(A1)
    sea = a0 < SEA
    Image.fromarray(shade_rgb(a1, sea)).save(OUT / "overview_after.png", optimize=True)
    Image.fromarray(shade_rgb(a0, sea)).save(OUT / "overview_before.png", optimize=True)
    d = a1 - a0; s = np.clip(np.abs(d) / 1500, 0, 1)
    rgb = np.full(d.shape + (3,), 235, np.float32)
    rgb[d < 0] = np.stack([235 * (1 - s), 235 * (1 - s), 235 * (1 - s) + 235 * s], -1)[d < 0]   # lowered: blue
    rgb[d > 0] = np.stack([235 * (1 - s) + 235 * s, 235 * (1 - s), 235 * (1 - s)], -1)[d > 0]   # raised: red
    rgb[sea] = (200, 210, 225)
    label(Image.fromarray(rgb.astype(np.uint8)), "change (blue lower / red higher, full at 1500 u16)").save(OUT / "overview_change.png", optimize=True)
    for nm, (y0, y1, x0, x1, ds) in crops.items():
        y0, x0 = max(0, y0), max(0, x0); y1, x1 = min(ctx.H, y1), min(ctx.W, x1)
        b, a = A0[y0:y1, x0:x1], A1[y0:y1, x0:x1]
        sea_m = b < SEA
        r, c = ctx.rc(y0, y1, x0, x1); riv = ctx.hx_river[r, c] & ~sea_m
        ib, ia = shade_rgb(b, sea_m), shade_rgb(a, sea_m)
        for im in (ib, ia):
            e = riv & ~ndi.binary_erosion(riv)
            im[e] = (40, 90, 230)
        if ds > 1:
            ib, ia = ib[::ds, ::ds], ia[::ds, ::ds]
        gap = np.full((ib.shape[0], 6, 3), 255, np.uint8)
        img = Image.fromarray(np.hstack([ib, gap, ia]))
        label(img, f"{nm}: before | after   px y {y0}-{y1} x {x0}-{x1}" + (f" (1/{ds})" if ds > 1 else ""))
        img.save(OUT / f"crop_{nm}.png", optimize=True)


def crop_boxes(ctx, D):
    names, f = ctx.names, ctx.f
    def centre_of(prefix):
        ids = [i for i, n in enumerate(names) if n.startswith(prefix)]
        rs, cs = np.nonzero(np.isin(f["region"], ids))
        return int(ctx.H - 8 * rs.mean() - 4), int(8 * cs.mean() + 4)
    def box(yx, half, ds=1): y, x = yx; return (y - half, y + half, x - half, x + half, ds)
    out = {}
    (ya, xa), (yb, xb) = centre_of("ironic_region_xiping"), centre_of("ironic_central_longxi")
    out["xiping_longxi"] = box(((ya + yb) // 2, (xa + xb) // 2), 560, 1)
    out["ordos_budugen"] = box(centre_of("ironic_nomad_budugen_resource_2"), 480, 1)
    out["wuyuan"] = box(centre_of("ironic_region_wuyuan"), 420, 1)
    out["north_band"] = (430, 830, 2900, 4500, 1)
    out["north_band_e"] = (430, 830, 6900, 8500, 1)
    out["sw_seam"] = (3300, 3750, 1100, 2700, 1)
    out["west_edge"] = (600, 3000, 0, 480, 2)
    for g in ("hexi", "korea_ne"):
        m = (D > 0) & (ctx.G == g)
        if m.any():
            Dm = ndi.uniform_filter(np.where(m, D, 0), 9)
            r, c = np.unravel_index(np.argmax(Dm), D.shape)
            out[f"river_{g}"] = box((int(ctx.H - 8 * r - 4), int(8 * c + 4)), 360, 1)
    return out


# ---------------------------------------------------------------------------------------------- main
def main(dry=False):
    if MARK.exists() and not dry:
        print("terrain polish already applied", MARK.read_text()); return
    t0 = time.time()
    ctx = Ctx(); A0 = ctx.Hm
    print(f"height {A0.shape}, map.hex {ctx.w}x{ctx.h}")
    cnt0 = ctx.step_count_hex(A0)
    # M5 knee first (pointwise on the original values; the H1 smoothing then works on the kneed tops)
    K, extra, S = m5_prepare(ctx, A0)
    A = pass_m5_knee(ctx, A0, K, extra); del extra
    A = pass_h1(ctx, A, 'strong')
    A = pass_h1(ctx, A, 'band')
    A = pass_west(ctx, A)
    D = m4_depth(ctx, A)
    A = pass_m4(ctx, A, D)
    A = pass_h1(ctx, A, 'cleanup')
    cnt1 = ctx.step_count_hex(A)
    metrics = dict(
        steps_per_1000_land_hexes=dict(before=ctx.steps_by_group(cnt0), after=ctx.steps_by_group(cnt1)),
        step_px_on_river_hexes=dict(before=int(cnt0[ctx.hx_river].sum()), after=int(cnt1[ctx.hx_river].sum())),
        river_higher_than_surroundings_pct=dict(before=ctx.river_high_share(A0), after=ctx.river_high_share(A)),
        np_new_saturation=dict(before=ctx.sat_share(A0), after=ctx.sat_share(A)),
        protected_zone_change_u16=ctx.zone_change(A0, A),
        total_px_changed=int((A != A0).sum()),
        passes=ctx.stats, params=dict(WEST_FULL=WEST_FULL, SIG=SIG, ITERS=ITERS, BAND_SIG=BAND_SIG, STEP_GROW=STEP_GROW, EDGE=EDGE,
                                      FEATHER=FEATHER, CAP=CAP, PROF=PROF, KNEE_PCT=KNEE_PCT, WEST=WEST))
    dd = np.abs(A.astype(np.int32) - A0.astype(np.int32))
    for g in GROUPS:                                 # mean / p99 |change| per group (land hexes, hex-centre samples)
        m = (ctx.G == g) & ctx.land
        v = ctx.sample_hex(dd)[m]
        metrics.setdefault("abs_change_hex_centre", {})[g] = dict(mean=round(float(v.mean()), 1), p99=float(np.percentile(v, 99)))
    del dd
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump(metrics, open(OUT / ("metrics_dry.json" if dry else "metrics_applied.json"), "w"), indent=1)
    print(json.dumps({k: metrics[k] for k in ("steps_per_1000_land_hexes", "step_px_on_river_hexes",
                                              "river_higher_than_surroundings_pct", "np_new_saturation",
                                              "protected_zone_change_u16", "total_px_changed")}, indent=1))
    if dry:
        previews(ctx, A0, A, crop_boxes(ctx, D), D)
        img = np.full((ctx.h, ctx.w, 3), 255, np.uint8); img[ctx.land] = (225, 225, 225); img[ctx.f["terr"] == 1] = (170, 190, 215)
        b = img.copy(); b[cnt0 > 0] = (220, 0, 0); a = img.copy(); a[cnt1 > 0] = (220, 0, 0)
        Image.fromarray(np.hstack([b[::-1], np.full((ctx.h, 8, 3), 0, np.uint8), a[::-1]])).save(OUT / "step_hexes_before_after.png", optimize=True)
        print(f"dry run: previews in {OUT} ({time.time() - t0:.0f} s); nothing written in terrain/ or hex/")
        return metrics
    BACKUP.mkdir(exist_ok=True); shutil.copy2(HEIGHT, BACKUP / HEIGHT.name)
    Image.fromarray(A).save(HEIGHT, compression="tiff_lzw")
    MARK.write_text(json.dumps(dict(ts=time.strftime("%Y%m%d_%H%M%S"), K=round(K), px_changed=metrics["total_px_changed"],
                                    steps_after=metrics["steps_per_1000_land_hexes"]["after"])))
    print("wrote", HEIGHT, f"({time.time() - t0:.0f} s); backup in {BACKUP}")
    return metrics


if __name__ == "__main__":
    main(dry="--dry" in sys.argv)
