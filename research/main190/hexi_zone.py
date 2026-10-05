"""[Atlas3K main190, map-only] Copy of the other session's hexi_x15.py mask code: builds the Hexi /
Xiping west-zone masks and the Guzang projection on the padded grid and saves them for the terrain build
(dem_fill / class_fill via hexi_geo.py). No region data is written.

Original docstring: Hexi corridor proposal (mockup only, no writes to hex/): make Hexi look like the Hexi corridor.

User (2026-10-01): west pad, corridor at ~1.3x the core's compression (core ~2.0 km/hex -> Hexi KMH km/hex).
* grid: PAD columns added on the west (1338 -> 1338+PAD); every existing hex/town moves +PAD cols (startpos rule:
  add the left padding to x).
* layout: a local equirectangular projection anchored on Guzang (Wuwei capital, unchanged), KMH km per hex.
* corridor = Zhou's AD 262 Liangzhou commandery polygons (Dunhuang, Jiuquan, Zhangye, Xihai/Juyan, Wuwei west of
  Guzang; km_han.npy) through that projection: the narrow Qilian-front strip, the Juyan spur up the Ruo, the desert
  bay between Juyan and Wuwei. Existing non-Hexi regions (Xiping/Qinghai, Wuwei capital, Jincheng, ...) keep their land.
* cleared: the land of the relocated 190E Hexi regions (Dunhuang, Jiuquan, Lude, Xihai, Rile) outside the new corridor
  becomes desert (non-playable).
* Qilian wall: a band (QILIAN hexes) on the south side of the corridor -> impassable mountain; north of it = desert.
* lakes: research_r6/hexi_lakes.json (Dunhuang, Yuanquan, Juyan); rivers: Kongming rivers (km_river_ll.npz).
* towns: relocated Hexi towns at their real seats (snapped into the corridor); fill = Han Hexi counties greedily while a
  gap >= FILL walking steps remains (same rule as the final proposal).
Writes hexi_x15.json + previews/hexi_x15_before.png / _after.png.
"""
import json, csv, math, collections, sys
from pathlib import Path
import numpy as np
from scipy import ndimage as ndi
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent / "proposal_x15"; M190 = HERE.parent
import sys as _sys; _sys.path.insert(0, str(HERE))
import geo_x15 as G
from hexgrid import centre, nearest_hex, neighbour_arrays, neighbour
from km_georef_lib import px2ll
from km_identity import han_of
from regions_carve import route
import plan_x15

PAD = 140
KMH = 2.6                    # km per hex in Hexi (core ~2.0 -> 1.3x)
QILIAN = 7
WIDTH = 32                   # playable corridor: hexes north of the Qilian wall (~85 km at 2.6 km/hex)
SPUR = 12                    # Juyan spur: hexes either side of the Ruo river / around the lakes
FILL = 30
HEXI_KEYS = ["dunhuang", "jiuquan", "zhangye", "zhangye_sg", "juyan", "wuwei"]
RELOCATE = ["ironic_region_hanyang_capital", "ironic_region_hanyang_resource_1", "ironic_region_xi_capital",
            "ironic_region_xi_resource_1", "ironic_region_wuwei_resource_3"]
ANCHOR = ("3k_main_wuwei_capital", 37.93, 102.64)   # Guzang stays where it is
# Xiping (190E ironic_region_xiping_*): new site (lat, lon, what it stands for). Nan'an / Huandao are 190E names for
# Qiang-plateau regions (the real Nan'an commandery and its seat Huandao are in Longxi, east) - kept, flagged
XIPING = {"ironic_region_xiping_capital": (36.62, 101.78, "Xidu = Xining (Han Xiping seat)"),
          "ironic_region_xiping_resource_1": (36.28, 100.62, "Gonghe basin south of Qinghai Lake (Qiang lands, Han Xihai frontier)"),
          "ironic_region_xiping_resource_2": (36.03, 101.43, "Heyuan / Guide on the upper Yellow River")}
XP_ELEV = 3450               # m: playable valleys / basins below this
QINGHAI_LAKE = [(37.15, 99.6), (37.22, 100.0), (37.12, 100.5), (36.97, 100.78), (36.68, 100.72), (36.55, 100.3),
                (36.63, 99.85), (36.85, 99.58)]   # (lat, lon)
DEM_DIRS = [Path(__file__).parents[1] / "dem", Path(__file__).parents[1] / "research_r6" / "north" / "dem"]


def dem_sample(lon, lat):
    """Copernicus GLO-90 metres at lon/lat (nearest, 1200 px/deg tiles), NaN where no tile; tiles cached."""
    import tifffile
    out = np.full(np.shape(lon), np.nan, np.float32)
    ilon = np.floor(lon).astype(int); ilat = np.floor(lat).astype(int)
    for la_, lo_ in set(zip(ilat.ravel().tolist(), ilon.ravel().tolist())):
        p = next((d / f"Copernicus_DSM_COG_30_N{la_:02d}_00_E{lo_:03d}_00_DEM.tif" for d in DEM_DIRS
                  if (d / f"Copernicus_DSM_COG_30_N{la_:02d}_00_E{lo_:03d}_00_DEM.tif").exists()), None)
        if p is None: continue
        a = tifffile.imread(str(p)).astype(np.float32); n, m = a.shape
        sel = (ilat == la_) & (ilon == lo_)
        rr = np.clip(((la_ + 1 - lat[sel]) * n).astype(int), 0, n - 1); cc = np.clip(((lon[sel] - lo_) * m).astype(int), 0, m - 1)
        out[sel] = a[rr, cc]
    return out
def main():
    f, names, w, h = G.hexmap(); W2 = w + PAD
    NP = names.index("3k_main_reg_non_playable")
    S = G.settlements(f, names)
    inv = {r["key"]: r for r in csv.DictReader(open(M190 / "research_r6" / "inventory.csv", encoding="utf-8"))}
    # shifted base layers
    def shift(a, fill):
        o = np.full((h, W2), fill, a.dtype); o[:, PAD:] = a; return o
    reg = shift(f["region"], NP); terr = shift(f["terr"], 0); imp = shift(f["imp"], 1); river = shift(f["river"], 0)
    road = shift(f["road"], 0)
    gc, gr = S[ANCHOR[0]]; xg, zg = centre(gc + PAD, gr)
    kw = 0.72 / KMH; cl = math.cos(math.radians(39.0))
    def ll2hex(lat, lon):
        x = xg + (np.asarray(lon, float) - ANCHOR[2]) * cl * 111.2 * kw
        z = zg + (np.asarray(lat, float) - ANCHOR[1]) * 111.2 * kw
        c, r = nearest_hex(np.ravel(x), np.ravel(z), W2, h); return np.asarray(c), np.asarray(r)
    # corridor from the Kongming polygons
    H = np.load(HERE / "km_han.npy"); keys = json.load(open(HERE / "cmd_keys.json"))
    idx = [keys.index(k) for k in HEXI_KEYS]
    yy, xx = np.nonzero(np.isin(H, idx))
    lon, lat = px2ll(xx * 4 + 2, yy * 4 + 2)
    west = (H[yy, xx] != keys.index("wuwei")) | (lon < ANCHOR[2] + 0.2)
    c, r = ll2hex(lat[west], lon[west])
    ok = (c >= 0) & (c < W2) & (r >= 0) & (r < h)
    corr = np.zeros((h, W2), bool); corr[r[ok], c[ok]] = True
    corr = ndi.binary_closing(corr, iterations=2)
    relocate_ids = [names.index(k) for k in RELOCATE]
    keep_play = (reg >= 0) & (reg != NP) & (terr != 1) & ~np.isin(reg, relocate_ids + [names.index(k) for k in XIPING])
    corr &= ~keep_play & (terr != 1) | (corr & np.isin(reg, relocate_ids))
    corr &= ~keep_play
    # lakes
    lakes = np.zeros((h, W2), bool)
    for nm_, poly in json.load(open(M190 / "research_r6" / "hexi_lakes.json", encoding="utf-8")).items():
        if nm_.startswith("_"): continue
        cs, rs = ll2hex([p[0] for p in poly], [p[1] for p in poly])
        im = Image.new("1", (W2, h), 0); ImageDraw.Draw(im).polygon(list(zip(cs.tolist(), rs.tolist())), fill=1, outline=1)
        lakes |= np.array(im, bool)
    corr &= ~lakes
    # per column: the polygon's southern edge = the Qilian front. Corridor = WIDTH hexes north of it (+ the Juyan spur
    # along the Ruo / around the lakes); Qilian wall = QILIAN hexes south of it; desert = the rest north of it.
    poly = corr.copy()
    rows = np.arange(h)[:, None]
    valid = poly.any(0)
    se = np.where(valid, np.argmax(poly, 0), 0).astype(float)          # lowest (south-most) row per column
    se_m = se.copy()
    for c_ in np.nonzero(valid)[0]:                                     # median over +-7 valid columns (smooth front)
        win = [x for x in range(c_ - 7, c_ + 8) if 0 <= x < W2 and valid[x]]
        se_m[c_] = np.median(se[win])
    se_m = np.round(se_m).astype(int)
    R0 = np.load(HERE / "km_river_ll.npz")
    m0 = (R0["lon"] < ANCHOR[2]) & (R0["lat"] > 38.6) & (R0["lon"] > 99.0)          # Ruo river and the Juyan lakes
    sc, sr = ll2hex(R0["lat"][m0], R0["lon"][m0]); ok0 = (sc >= 0) & (sc < W2) & (sr >= 0) & (sr < h)
    ruo = np.zeros((h, W2), bool); ruo[sr[ok0], sc[ok0]] = True
    dr = ndi.distance_transform_edt(~(ruo | lakes))
    strip = valid[None] & (rows >= se_m[None]) & (rows <= se_m[None] + WIDTH)
    corr = (strip | (poly & (dr <= SPUR))) & ~keep_play & (terr != 1) & ~lakes
    lab_c, n_c = ndi.label(corr)
    sz = ndi.sum(corr, lab_c, range(1, n_c + 1)); corr &= np.isin(lab_c, 1 + np.nonzero(sz >= 400)[0])   # drop fragments
    gcol = gc + PAD
    qilian = valid[None] & (rows < se_m[None]) & (rows >= se_m[None] - QILIAN) & ~keep_play & (terr != 1) & ~lakes
    qilian[:, gcol - 3:] = False
    desert = valid[None] & (rows > se_m[None]) & ~corr & ~keep_play & (terr != 1) & ~lakes
    cols_ = np.arange(W2)[None]
    desert |= (reg == NP) & (rows > gr) & (cols_ >= gcol) & (cols_ < 470 + PAD) & (terr != 1)    # Badain Jaran / Tengger
    desert[:, 470 + PAD:] = False
    cleared = np.isin(reg, relocate_ids) & ~corr
    road[cleared] = 0
    # ---- Xiping / Qinghai (DEM-driven, same Guzang projection): the Huangshui valley (Xining), the Qinghai Lake basin
    #      and the upper Yellow River valleys are playable below XP_ELEV m; ridges next to them are impassable mountain;
    #      the high plateau beyond stays non-playable; Qinghai Lake is a lake.
    RR, CC = np.mgrid[0:h, 0:W2]; XX, ZZ = centre(CC, RR)
    LON = ANCHOR[2] + (XX - xg) / (cl * 111.2 * kw); LAT = ANCHOR[1] + (ZZ - zg) / (111.2 * kw)
    elev = dem_sample(LON, LAT)
    xp_ids = [names.index(k) for k in XIPING]
    zone0 = ~keep_play & (terr != 1) & ((reg == NP) | np.isin(reg, relocate_ids + xp_ids)) & (LON > 97.0) & (LON < 104.6) & (LAT > 33.6) & (LAT < 38.2)
    zone = zone0 & (LON < 103.8)
    thr = XP_ELEV - np.clip((35.6 - LAT) / 0.5, 0, 1) * 1300.0   # south of ~35.6N the bar drops: the edge follows contours
    ql = Image.new("1", (W2, h), 0)
    qc, qr = ll2hex([p[0] for p in QINGHAI_LAKE], [p[1] for p in QINGHAI_LAKE])
    ImageDraw.Draw(ql).polygon(list(zip(qc.tolist(), qr.tolist())), fill=1, outline=1)
    lakes |= np.array(ql, bool) & zone
    V = zone & (elev < thr) & ~lakes & ~corr & ~qilian
    labV, nV = ndi.label(V)
    seeds = set()
    for k, (la_, lo_, _) in XIPING.items():
        c0, r0 = (int(a[0]) for a in ll2hex(la_, lo_)); seeds.add(int(labV[r0, c0]))
    touch = set(np.unique(labV[ndi.binary_dilation(keep_play, iterations=1) & V]).tolist())
    szV = ndi.sum(V, labV, range(1, nV + 1))
    V &= np.isin(labV, [i for i in range(1, nV + 1) if (i in seeds or i in touch) and szV[i - 1] >= 150])
    dV = ndi.distance_transform_edt(~(V | corr))
    mtn = zone0 & ~V & ~lakes & ~corr & (dV <= 10)
    qilian = (qilian | mtn) & ~V
    desert &= ~V & ~mtn
    corr_x = corr | V                                   # all new playable land in the west
    cleared = np.isin(reg, relocate_ids + xp_ids) & ~corr_x
    road[cleared] = 0
    out = dict(corr=corr_x, qilian=qilian, desert=desert, lakes=lakes, cleared=cleared, pad=np.zeros((h, W2), bool),
               W2=W2, h=h, PAD=PAD, xg=xg, zg=zg, kw=kw, cl=cl, anchor_lat=ANCHOR[1], anchor_lon=ANCHOR[2])
    out["pad"][:, :PAD] = True
    np.savez_compressed(M190 / "research_r6" / "hexi_zone.npz", **out)
    print("hexi zone:", {k: int(v.sum()) for k, v in out.items() if isinstance(v, np.ndarray) and v.dtype == bool},
          "grid", W2, h, "Guzang world", round(xg, 3), round(zg, 3))


if __name__ == "__main__":
    main()
