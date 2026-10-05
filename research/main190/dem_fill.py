#!/usr/bin/env python3
"""Fill the west/north padding of the warped 190E height rasters with real elevation (Copernicus GLO-90).

Run after terrain_main.py. Per output pixel: new raster px -> 190E source px (warp inverse, any warp) -> lon/lat
(rubber.py: georef.json's affine + a correction onto 190E's own town positions) -> DEM metres (bilinear on a 240 px/deg mosaic).
Metres -> 190E height values by quantile mapping fitted on every land pixel inside the 190E footprint (the map is
stylised, so a per-pixel regression is meaningless; matching the distributions keeps plains/plateau/peaks looking
like the rest of the map). The DEM is box-blurred (~1.5 hex) to match 190E's smooth relief.
Seam: the DEM keeps its texture; the offset (190E - DEM) measured INSET px inside the 190E edge is added back and
decays away from the edge - its along-edge smooth part over FEATHER, its detail over SHORT - so there is no step and
no edge-extrusion streaks. 190E's own rim (north edge sea falloff, <= 28 px) is replaced.
Sea rasters: padding = the flat 190E sea surface. The warp-only rasters are kept in terrain/_warp_only/.
"""
import os, sys, json, glob, shutil
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "guandu")); sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "output", "pylibs"))
import tifffile
from tiff16 import write_gray16
from terrain_main import src_xy, FULL, HALF, OW, OH, SRC as SRC190
import rubber

T = os.path.join(HERE, "terrain"); KEEP = os.path.join(T, "_warp_only"); DEM = os.path.join(HERE, "dem")
HEIGHTS = ["3k_dlc07_main_map.height.191fd803c1a801d.tif", "lf_heights.tif"]
SEAS = ["3k_dlc07_main_map.sea_height.191fd804ab3801e.tif", "lf_sea_heights.tif"]
SRC_W, SRC_H = 7136, 5620
PPD, LON0, LON1, LAT1 = 240, 84, 136, 47   # mosaic: px per degree, west / east lon, north lat (round 6: wider map)
FEATHER = 20 * 8                       # px (20 hexes)
SHORT = 4 * 8                          # px, decay of the high-frequency part of the seam offset
EDGE_SMOOTH = 5 * 8                    # px, along-edge box radius for the smooth offset
BLUR = 12                              # mosaic px box radius (x3 passes ~ gaussian)
INSET = 32                             # px of 190E edge rim to replace
SEA_SCALE = 44217 / 65535              # 190E sea source -> correct (vanilla) sea source scale
SEA_LEVEL = 14220                      # flat 190E sea surface (sea_height mode)
LIANG_LON, LIANG_LAT, LIANG_RAMP = 103.9, 35.3, 0.8   # degrees: DEM terrain west/north of this inside 190E (Hexi)
ALXA_LON, ALXA_LAT = 105.3, 37.6                        # and west of the Helan range north of the Zhongwei bend

M = np.array(json.load(open(os.path.join(HERE, "..", "guandu", "georef.json")))["M"])
MINV = np.linalg.inv(M[:2])


def mosaic():
    nr, nc = (LAT1 - 14) * PPD, (LON1 - LON0) * PPD
    mos = np.full((nr, nc), np.nan, np.float32)
    ds = 1200 // PPD
    for f in glob.glob(os.path.join(DEM, "*.tif")):
        b = os.path.basename(f).split("_")
        lat, lon = int(b[4][1:]), int(b[6][1:])
        a = tifffile.imread(f).astype(np.float32)
        a = a.reshape(PPD, ds, PPD, ds).mean(axis=(1, 3))       # all tiles < 50N are 1200 x 1200
        r0, c0 = (LAT1 - lat - 1) * PPD, (lon - LON0) * PPD
        mos[r0:r0 + PPD, c0:c0 + PPD] = a
    for line in open(os.path.join(DEM, "missing.txt")):                  # 404 = open ocean
        b = line.split()[0].split("_"); lat, lon = int(b[4][1:]), int(b[6][1:])
        r0, c0 = (LAT1 - lat - 1) * PPD, (lon - LON0) * PPD
        mos[r0:r0 + PPD, c0:c0 + PPD] = 0.0
    ok = np.isfinite(mos)
    num, den = box3(np.where(ok, mos, 0), BLUR), box3(ok.astype(np.float32), BLUR)
    return np.where(den > 0.5, num / np.maximum(den, 1e-6), np.nan).astype(np.float32)


def box(a, r, axis):
    """Box mean of radius r along axis (edge-clamped)."""
    a = np.moveaxis(a, axis, 0)
    p = np.concatenate([np.repeat(a[:1], r + 1, 0), a, np.repeat(a[-1:], r, 0)]).astype(np.float64)
    c = np.cumsum(p, 0)
    return np.moveaxis(((c[2 * r + 1:] - c[:-2 * r - 1]) / (2 * r + 1)).astype(np.float32), 0, axis)


def box3(a, r):
    for _ in range(3):
        for ax in range(a.ndim): a = box(a, r, ax)
    return a


def sample(mos, wx, wz):
    """Bilinear DEM metres at old-world (x, z) through the rubber-sheet georef; NaN where no tile.
    Hexi mode (warp.is_hexi): inside the west zone lon/lat come from the Guzang projection (hexi_geo)."""
    import warp
    if warp.is_hexi():
        # 2026-10-04 (new_areas_lookover H1 root cause): blend the DEM METRES sampled under both georefs, not the
        # lon/lat (blending positions across the RAMP seam sampled the DEM from a point between two places, which
        # with the stepped weight gave 1-px steps). Where one side has no tile, the other is used.
        import hexi_geo
        w = np.broadcast_to(np.asarray(hexi_geo.weight(wx, wz), float), np.broadcast(np.asarray(wx), np.asarray(wz)).shape)
        v0 = _bilinear(mos, *rubber.to_lonlat(wx, wz))
        if not np.any(w > 0): return v0
        v1 = _bilinear(mos, *hexi_geo.proj_lonlat(wx, wz))
        v0f, v1f = np.where(np.isfinite(v0), v0, v1), np.where(np.isfinite(v1), v1, v0)
        return np.where(w <= 0, v0, np.where(w >= 1, v1, v0f * (1 - w) + v1f * w))
    return _bilinear(mos, *rubber.to_lonlat(wx, wz))


def _bilinear(mos, lon, lat):
    """Bilinear mosaic metres at lon/lat; NaN outside the mosaic."""
    r = (LAT1 - lat) * PPD - 0.5; c = (lon - LON0) * PPD - 0.5
    r0 = np.floor(r).astype(np.int64); c0 = np.floor(c).astype(np.int64); fr = r - r0; fc = c - c0
    ok = (r0 >= 0) & (c0 >= 0) & (r0 < mos.shape[0] - 1) & (c0 < mos.shape[1] - 1)
    r0 = np.clip(r0, 0, mos.shape[0] - 2); c0 = np.clip(c0, 0, mos.shape[1] - 2)
    v = (mos[r0, c0] * (1 - fr) * (1 - fc) + mos[r0, c0 + 1] * (1 - fr) * fc
         + mos[r0 + 1, c0] * fr * (1 - fc) + mos[r0 + 1, c0 + 1] * fr * fc)
    return np.where(ok, v, np.nan)


def liang_weight(wx, wz):
    """1 where the terrain should be real DEM inside 190E's footprint: Liangzhou / the Hexi corridor west of
    LIANG_LON and north of LIANG_LAT (190E's own terrain there is stylised and does not show the corridor)."""
    import warp
    if warp.is_hexi(): return __import__("hexi_geo").weight(wx, wz)          # x1.5 + west pad: the Hexi zone is DEM
    if warp.is_scale(): return np.zeros(np.broadcast(np.asarray(wx), np.asarray(wz)).shape)   # base 190E x1.5: no Liang DEM
    lon, lat = rubber.to_lonlat(wx, wz)
    sm = lambda t: np.clip(t, 0, 1) ** 2 * (3 - 2 * np.clip(t, 0, 1))
    wa = sm((LIANG_LON - lon) / LIANG_RAMP) * sm((lat - LIANG_LAT) / LIANG_RAMP)
    # + Alxa (west of the Helan range, north of the Zhongwei bend): 190E's terrain there is flat filler too
    wb = sm((ALXA_LON - lon) / LIANG_RAMP) * sm((lat - ALXA_LAT) / LIANG_RAMP)
    return np.maximum(wa, wb)


def main():
    # input: terrain_main.py's fresh output (terrain/ -> _warp_only/ every run; round 6: never reuse a stale copy)
    os.makedirs(KEEP, exist_ok=True)
    fresh = os.path.join(T, "_fresh_warp")
    if os.path.exists(fresh):                            # terrain/ holds terrain_main's fresh output: take it as input
        for n in HEIGHTS + SEAS: shutil.copy2(os.path.join(T, n), os.path.join(KEEP, n))
        os.remove(fresh)
    else:                                                # terrain/ holds an earlier dem_fill / coast_carve result: reuse _warp_only
        print("terrain/ is not fresh from terrain_main - using the warp-only copies in _warp_only/")
        for n in HEIGHTS + SEAS: assert os.path.exists(os.path.join(KEEP, n)), "run terrain_main.py first"
    mos = mosaic()
    print(f"mosaic {mos.shape}, covered {np.isfinite(mos).mean():.1%}")
    SW, SH = SRC_W, SRC_H
    lo_x, hi_x, lo_y, hi_y = INSET, SW - 1 - INSET, INSET, SH - 1 - INSET
    sworld = lambda sx, sy: ((sx + 0.5) / SW * OW, (1 - (sy + 0.5) / SH) * OH)
    same = None
    for n in HEIGHTS:
        h = tifffile.imread(os.path.join(KEEP, n)); hs = tifffile.imread(os.path.join(SRC190, n)).astype(np.float32)
        if same is None:
            # quantile fit in 190E source space (stride 8, inside the inset, outside the Liang zone)
            gy, gx = np.mgrid[lo_y:hi_y:8, lo_x:hi_x:8].astype(np.float32)
            wx, wz = sworld(gx, gy); dem = sample(mos, wx, wz); hv = hs[gy.astype(int), gx.astype(int)]
            land = (hv > SEA_LEVEL + 300) & np.isfinite(dem) & (dem > 5) & (liang_weight(wx, wz) < 0.01)
            q = np.linspace(0, 1, 1001)
            qm, qv = np.quantile(dem[land], q), np.quantile(hv[land], q)
            seabed = float(np.median(hv[hv < SEA_LEVEL]))
            print(f"fit on {land.sum()} px: m {qm[[10, 250, 500, 750, 990]].round()} -> v {qv[[10, 250, 500, 750, 990]].round()}; seabed {seabed:.0f}")
            same = True
        mapv = lambda dem: np.where(dem > 0, np.interp(np.nan_to_num(dem), qm, qv), seabed)

        def eff(sx, sy):
            """190E value with the Liang zone replaced by DEM (what the footprint looks like after this pass)."""
            wx, wz = sworld(sx, sy); wl = liang_weight(wx, wz)
            base = hs[np.clip(np.rint(sy).astype(int), 0, SH - 1), np.clip(np.rint(sx).astype(int), 0, SW - 1)]
            v = mapv(sample(mos, wx, wz)); v = np.where(np.isfinite(v), v, base)
            return base * (1 - wl) + v * wl
        # seam offsets on the inset ring, in source space: N/S rows over all columns, W/E columns over all rows
        ring = {}
        ax_x, ax_y = np.arange(SW, dtype=np.float32), np.arange(SH, dtype=np.float32)
        for key, (sx, sy) in {"N": (np.clip(ax_x, lo_x, hi_x), np.full(SW, lo_y, np.float32)),
                              "S": (np.clip(ax_x, lo_x, hi_x), np.full(SW, hi_y, np.float32)),
                              "W": (np.full(SH, lo_x, np.float32), np.clip(ax_y, lo_y, hi_y)),
                              "E": (np.full(SH, hi_x, np.float32), np.clip(ax_y, lo_y, hi_y))}.items():
            off = eff(sx, sy) - mapv(sample(mos, *sworld(sx, sy)))
            okk = np.isfinite(off)
            sm = box(np.where(okk, off, 0), EDGE_SMOOTH, 0) / np.maximum(box(okk.astype(np.float32), EDGE_SMOOTH, 0), 1e-6)
            ring[key] = (np.where(okk, off, 0).astype(np.float32), sm.astype(np.float32))
        out = h.copy(); CH = 256; n_liang = 0
        for r0 in range(0, FULL[1], CH):
            r1 = min(FULL[1], r0 + CH)
            sx, sy = src_xy(FULL, (SW, SH), r0, r1)
            dx = np.maximum(np.maximum(lo_x - sx, sx - hi_x), 0); dy = np.maximum(np.maximum(lo_y - sy, sy - hi_y), 0)
            d = np.maximum(dx, dy)
            wx, wz = sworld(sx, sy)
            v = mapv(sample(mos, wx, wz))
            cx = np.clip(np.rint(sx), lo_x, hi_x).astype(int); cy = np.clip(np.rint(sy), lo_y, hi_y).astype(int)
            top = sy < SH / 2; west = sx < SW / 2
            raw = np.where(dy > 0, np.where(top, ring["N"][0][cx], ring["S"][0][cx]), np.where(west, ring["W"][0][cy], ring["E"][0][cy]))
            sm = np.where(dy > 0, np.where(top, ring["N"][1][cx], ring["S"][1][cx]), np.where(west, ring["W"][1][cy], ring["E"][1][cy]))
            tl = np.clip(d / FEATHER, 0, 1); tl = tl * tl * (3 - 2 * tl)
            ts = np.clip(d / SHORT, 0, 1); ts = ts * ts * (3 - 2 * ts)
            pad_val = v + sm * (1 - tl) + (raw - sm) * (1 - ts)
            base = h[r0:r1].astype(np.float32)
            wl = liang_weight(wx, wz); n_liang += int(((d == 0) & (wl > 0.5)).sum())
            inside = base * (1 - wl) + np.where(np.isfinite(v), v, base) * wl
            val = np.where(d > 0, np.where(np.isfinite(pad_val), pad_val, base), inside)
            out[r0:r1] = np.clip(np.rint(val), 0, 65535).astype(np.uint16)
        write_gray16(os.path.join(T, n), out)
        os.makedirs(os.path.join(T, "_pre_carve"), exist_ok=True)
        write_gray16(os.path.join(T, "_pre_carve", n), out)                  # coast_carve.py's input
        print(f"{n}: Liang zone {n_liang:,} footprint px now DEM; value pct {np.percentile(out[::8, ::8], [5, 50, 95])}")
    # 190E's sea source is unscaled: vanilla x 65535/44217 (checked: ratio 1.4822 everywhere). Correct source =
    # compiled value x 44217/65535 (docs + memory vanilla-ak-project-fixes); unscaled, the compiled sea/river surface
    # sits too high and shows as raised walls along coasts and the big rivers in game. Scale after the padding.
    for n in SEAS:
        s = tifffile.imread(os.path.join(KEEP, n)).astype(np.float64); H_, W_ = s.shape
        for r0 in range(0, H_, 512):
            r1 = min(H_, r0 + 512); sx, sy = src_xy((W_, H_), (SW // 2, SH // 2), r0, r1)
            pad = (sx < INSET / 2) | (sx > SW // 2 - 1 - INSET / 2) | (sy < INSET / 2) | (sy > SH // 2 - 1 - INSET / 2)
            blk = s[r0:r1]; blk[pad] = SEA_LEVEL; s[r0:r1] = blk
        s = np.rint(s * SEA_SCALE).astype(np.uint16)
        write_gray16(os.path.join(T, n), s)
        os.makedirs(os.path.join(T, "_pre_carve"), exist_ok=True)
        write_gray16(os.path.join(T, "_pre_carve", n), s)                    # coast_carve.py's input
        print(f"{n}: padding -> {SEA_LEVEL}, scaled x{SEA_SCALE:.5f} -> max {s.max()}, sea level {round(SEA_LEVEL * SEA_SCALE)}")


if __name__ == "__main__":
    main()
