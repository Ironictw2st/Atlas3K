#!/usr/bin/env python3
"""Campaign tree map for the x15 map from the DECODED vanilla tree map (user 2026-10-02: "decoded vanilla map and then you
adjust, removing trees around roads, rivers, etc so the map looks nice").

Source: output/trees_decoded/3k_dlc07_main_map.tree.tif (Trees session: regenerates vanilla's list exactly; palette =
sorted campaign_tree_ids colours, 19 = no tree; BOB samples one pixel per hex at (2c, H - 2r - 1 - (c & 1))).
 1. per hex: the vanilla hex under the x1.5 scale warp (col = (c - west) / 1.5, row = r / 1.5); the Hexi / steppe new
    land, the pads and hexes that were sea / coast in vanilla but are land here keep the current 190E-based raster
 1b. polish (trees_polish.py, 2026-10-04): H4 subtropical -> climate species in the north, M1 de-speckle / steppe
    thinning / Korea lowland fir -> katsura; only hexi / nomad / korea_ne / np_new hexes
 2. clean-up (vanilla thins trees around features: town 8%, road 13%, river 23%, beach 9%; the user wants it cleaner):
    none on towns + 2 rings, roads, bridges, river-edge hexes (both sides), beach / cliff / sea;
    thinned (stable per-hex hash) on the ring around roads and rivers (keep 30%) and land next to the coast (25%)
 3. written as the AK CampaignTree raster (terrain/<TREE> + the kit's raw terrain copy, tree_new too), 2x2 px per hex
`python trees_x15.py --dry` writes before/after metrics + previews to output/polish/trees only.
Then `TerryClone.Cli build-campaign --steps rasters,trees` builds trees.campaign_tree_list (extras_main.trees())."""
import sys
from pathlib import Path
import numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
import town_fix as T
from hexgrid import neighbour_arrays
from warp import current
import x15_land

DECODED = Path(r"Z:/Claude/TerryClone/output/trees_decoded/3k_dlc07_main_map.tree.tif")
VAN_HEX = Path(r"Z:/Claude/TerryClone/output/caime_upscaler/Templates/3k_dlc07_main_map/map.hex")
TREE = "3k_dlc07_main_map.tree.191fd7dc12fe7e4.tif"
KIT = Path(r"C:/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/assembly_kit_190E/raw_data/terrain/campaigns/3k_190e_expanded_map")
NO_TREE = 19
KEEP_NEAR_LINE, KEEP_NEAR_COAST = 0.30, 0.25


def hexvals(a, w, h):
    H = a.shape[0]
    cols = np.arange(w)[None, :].repeat(h, 0); rows = np.arange(h)[:, None].repeat(w, 1)
    return a[H - 2 * rows - 1 - (cols & 1), 2 * cols]


def grow(m, NA, k):
    for _ in range(k):
        g = m.copy()
        for nr, nc, v in NA: g |= v & m[nr, nc]
        m = g
    return m

# 2026-10-03 (user: new regions to the stock standard; stock tree share ~35%): top-up targets per plan zone
ZONE_TARGET = {"mountain_forest": 0.5, "korea_forest": 0.5, "river_woods": 0.5, "qilian_foothill": 0.5, "xiping_plateau": 0.45,
               "oasis": 0.4, "meadow_steppe": 0.2, "grass_steppe": 0.12, "corridor_steppe": 0.12,
               "desert_steppe": 0.03, "gobi": 0.03, "juyan": 0.03, "mountain_rock": 0.03, "qilian_peaks": 0.03}
OTHER_TARGET = 0.35


def topup(out, f, names, w, h, cols, rows, skip=None, log=print):
    """Only adds trees, on land of the new regions, up to each zone's share; tree type = the zone's commonest tree.
    skip: hexes whose cover the 1b polish manages (nomad arid steppe) - no top-up there, else each build re-adds trees."""
    import json
    stock = set()
    for line in open(HERE / "source" / "db" / "region_to_province_junctions_tables" / "data__.tsv", encoding="utf-8"):
        a = line.split("	")
        if len(a) >= 3 and not a[0].startswith(("#", "province")): stock.add(a[1])
    newk = [i for i, n in enumerate(names) if (n not in stock and not n.startswith("3k_"))] + sorted(x15_land._new_ids(names))
    newr = np.isin(f["region"], newk) & (f["terr"] == 0) & (f["imp"] == 0)
    if skip is not None: newr &= ~skip
    Z = np.full((h, w), "", object)
    for pf in ("steppe_plan.json", "hexi_plan.json"):
        for r, runs in json.load(open(HERE / "korea_ref" / pf, encoding="utf-8"))["zone_rle"].items():
            for s0, n, z in runs: Z[int(r), s0:s0 + n] = z
    from scipy import ndimage as ndi
    noise = ndi.gaussian_filter(np.random.default_rng(5).random((h, w)), 2.5)   # clumped woods, stable
    land_tree = out[(f["terr"] == 0) & (out != NO_TREE)]
    glob_mode = int(np.bincount(land_tree).argmax()) if land_tree.size else NO_TREE
    added = {}
    for z in set(Z[newr].tolist()):
        for cl in np.unique(f["climate"][newr & (Z == z)]):
            m = newr & (Z == z) & (f["climate"] == cl)
            tgt = ZONE_TARGET.get(z, OTHER_TARGET)
            have = float((out[m] != NO_TREE).mean())
            if have >= tgt or m.sum() < 50: continue
            trees = out[m & (out != NO_TREE)]
            kind = int(np.bincount(trees).argmax()) if trees.size else glob_mode
            empty = m & (out == NO_TREE)
            k = int(round((tgt - have) * m.sum()))
            if k <= 0: continue
            thr = np.sort(noise[empty])[-k] if k < empty.sum() else -1
            fill = empty & (noise >= thr)
            out = np.where(fill, kind, out); key = f"{z or 'other'}/{int(cl)}"; added[key] = int(fill.sum())
    log("tree top-up (new regions):", added)
    return out


def clean_mask(f, NA, cols, rows):
    """Step 2 mask (hexes the clean-up empties): towns + 2 rings, roads, bridges, river edges, coast / sea, village sites;
    thinned rings around roads / rivers (keep 30%) and the coast (keep 25%) by a stable per-hex hash."""
    town = (f["slot"] >= 0) | (f["sprawl"] > 0)
    road = f["road"] > 0; bridge = f["bridge"] > 0
    redge = f["river"] > 0
    for d, (nr, nc, v) in enumerate(NA):
        m = v & (((f["river"] >> d) & 1) > 0); redge[nr[m], nc[m]] = True
    coast = f["terr"] != 0
    none_ = grow(town, NA, 2) | road | bridge | redge | coast
    vh = HERE / "korea_ref" / "village_hexes.npy"              # village_dress.py sites (2026-10-03 polish)
    if vh.exists() and np.load(vh).shape == none_.shape: none_ |= np.load(vh)
    line_ring = grow(road | redge | bridge, NA, 1) & ~none_
    coast_ring = grow(coast, NA, 1) & ~none_ & ~line_ring
    rnd = ((cols * 73856093) ^ (rows * 19349663)) % 1000 / 1000.0            # stable per-hex
    return none_, none_ | (line_ring & (rnd >= KEEP_NEAR_LINE)) | (coast_ring & (rnd >= KEEP_NEAR_COAST))


def build(polish=True, cur_hex=None, log=print):
    """Steps 1, 1b, 2 in memory -> dict(out = per-hex classes, pal, w, h, f, names, NA, ...). Writes nothing.
    cur_hex: optional per-hex array to use instead of the current terrain/<TREE> raster (dry idempotence check)."""
    _, _, w, h, _, f, names = T.load(str(HERE / "hex" / "map.hex")); NA = neighbour_arrays(h, w)
    _, _, vw, vh, _, fv, _ = T.load(str(VAN_HEX))
    dec = Image.open(DECODED); pal = dec.getpalette(); V = hexvals(np.array(dec), vw, vh)
    cur_im = Image.open(HERE / "terrain" / TREE); assert cur_im.getpalette()[:60] == pal[:60]
    cur_a = np.array(cur_im); W, H = cur_a.shape[1], cur_a.shape[0]
    assert (W, H) == (2 * w, 2 * h + 1), ((W, H), (w, h))
    cur = hexvals(cur_a, w, h) if cur_hex is None else cur_hex
    # 1. vanilla under the warp
    wp = current()
    cols = np.arange(w)[None, :].repeat(h, 0); rows = np.arange(h)[:, None].repeat(w, 1)
    sc, sr = wp.inverse(cols, rows)
    sc = np.rint(sc).astype(int); sr = np.rint(sr).astype(int)
    inside = (sc >= 0) & (sc < vw) & (sr >= 0) & (sr < vh)
    scc, src = np.clip(sc, 0, vw - 1), np.clip(sr, 0, vh - 1)
    out = np.where(inside, V[src, scc], cur)
    M = x15_land.masks(w, h)
    newland = (M["hexi_play"] | M["steppe_play"] | M["hexi_desert"] | M["hexi_mountain"] | M["steppe_mountain"]) if M else np.zeros((h, w), bool)
    van_water = inside & (fv["terr"][src, scc] != 0)
    keep_cur = ~inside | newland | (van_water & (f["terr"] == 0))
    out = np.where(keep_cur, cur, out)
    log(f"from vanilla {int((~keep_cur).sum()):,} hexes, from the current raster {int(keep_cur.sum()):,} "
        f"(new land {int(newland.sum()):,}, pads {int((~inside).sum()):,}, vanilla water now land {int((van_water & (f['terr'] == 0)).sum()):,})")
    none_, cut = clean_mask(f, NA, cols, rows)
    pinfo = None
    if not polish:
        out = topup(out, f, names, w, h, cols, rows)
    else:
        # 1b. 2026-10-04 polish (docs/proposals/new_areas_lookover.md H4 + M1, trees_polish.py): no bamboo / castanopsis
        #     in the north-west and north (climate species instead), 7-hex majority de-speckle of the new-land forests,
        #     nomad arid steppe thinned to ~18.5% cover (no top-up there), Korea lowland fir half to katsura. Only hexi /
        #     nomad / korea_ne / np_new hexes change; all choices use stable per-hex hashes (deterministic).
        #     The top-up and the majority filter pull against each other, and the next build reads this output back in
        #     as the current raster, so top-up + polish are repeated here on the would-be next-build input until that
        #     input stops changing: the written raster is then a fixed point (re-running the build changes nothing).
        import trees_polish
        skip = trees_polish.topup_skip(f, names, w, h); base = out
        for k in range(12):
            o = topup(out, f, names, w, h, cols, rows, skip=skip, log=log if k == 0 else (lambda *a: None))
            o, pinfo = trees_polish.polish(o, f, names, w, h, NA, cut, log=log if k == 0 else (lambda *a: None))
            nxt = np.where(keep_cur, np.where(cut, NO_TREE, o), base)          # what the next build would start from
            if (nxt == out).all(): break
            out = nxt
        pinfo = dict(pinfo, fixed_point_rounds=k + 1, fixed_point=bool((nxt == out).all()))
        log(f"trees_polish: fixed point after {k + 1} round(s): {pinfo['fixed_point']}")
        out = o
    before = int((out != NO_TREE).sum())
    # 2. clean-up
    out = np.where(cut, NO_TREE, out)
    land = f["terr"] == 0
    log(f"trees {before:,} -> {int((out != NO_TREE).sum()):,}; land tree share {float((out != NO_TREE)[land].mean()):.1%} "
        f"(vanilla 49.8%); cleared: town+2 / road / bridge / river / coast {int((none_ & (out == NO_TREE)).sum()):,}")
    return dict(out=out, pal=pal, w=w, h=h, W=W, H=H, f=f, names=names, NA=NA, keep_cur=keep_cur, cut=cut, polish=pinfo)


def raster(out, w, h, W, H, pal):
    """3. every pixel takes its hex's value (2x2 per hex, the sampled pixel maps back to its own hex)."""
    ys, xs = np.mgrid[0:H, 0:W]
    pc = np.minimum(xs // 2, w - 1); pr = np.clip((H - 1 - ys - (pc & 1)) // 2, 0, h - 1)
    ras = out[pr, pc].astype(np.uint8)
    assert (hexvals(ras, w, h) == out).all()
    img = Image.fromarray(ras, "P"); img.putpalette(pal)
    return img


def main():
    B = build(polish=True)
    img = raster(B["out"], B["w"], B["h"], B["W"], B["H"], B["pal"])
    kt = TREE.replace("3k_dlc07_main_map", KIT.name)
    for d, n in ((HERE / "terrain", TREE), (KIT, kt), (KIT, kt.replace(".tree.", ".tree_new."))):
        if d == KIT and not (d / n).exists(): continue
        img.save(d / n, compression="tiff_lzw")
    print("wrote", HERE / "terrain" / TREE, "and the kit copy")


def dry(out_dir=Path(r"Z:/Claude/TerryClone/output/polish/trees")):
    """--dry: before (no polish) / after (polish) / after-of-after (idempotence) in memory; metrics + previews to
    out_dir only. Never writes terrain/ or the kit."""
    import trees_polish
    out_dir.mkdir(parents=True, exist_ok=True)
    quiet = lambda *a: None
    A0 = build(polish=False); A1 = build(polish=True)
    chain = [A1]                                                           # the next builds read the previous output back in
    for _ in range(3): chain.append(build(polish=True, cur_hex=chain[-1]["out"], log=quiet))
    base = [A0, build(polish=False, cur_hex=A0["out"], log=quiet)]         # same check for the unpolished pipeline
    trees_polish.report(A0, A1, chain, base, out_dir)


if __name__ == "__main__":
    dry() if "--dry" in sys.argv else main()
