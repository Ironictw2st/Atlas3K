#!/usr/bin/env python3
"""Whole-North polish plan (user 2026-10-02: "what about the rest of the North ... the steppe"): the Xianbei / Wuhuan /
Xiongnu steppe, the non-playable 'Land Beyond' backdrop north of it, and the Korean north, in one sketch.

The steppe is open country: it reads well through GROUND VARIETY + a few strong landmarks + sparse dressing, not forest.
Zones (from our DEM-based hex heights, position and water; real-world reference in brackets):
  desert_steppe  west / south-west low plateau  [Gobi edge, Ordos]           tan ground, scree, rare poplars
  grass_steppe   the open plateau                [Xilingol, Hulunbuir]        open grass, yurt camps, rock outcrops
  meadow_steppe  the wetter east                 [Horqin, Khingan foothills]  greener grass, elm/poplar groves
  river_woods    2 hexes along rivers / lake shores                           poplar + willow galleries
  mountain_rock  high relief, south / west       [Yin Shan, Daqing]           arid / cold ridge props, scree
  mountain_forest high relief, east / north      [Greater Khingan]            fir / larch forest, cold peaks
  korea_forest   the Korean north (north_plan.py covers it in detail)
Outputs korea_ref/steppe_plan.png + steppe_plan.json (zone per hex RLE, camp / outcrop / grove / ridge prop sites with
vanilla models, climate suggestion per zone, prop shopping list)."""
import json, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage as ndi
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
import town_fix as T
from hexgrid import neighbour_arrays, HX, HZ
from regions_carve import hex_blend_and_height
from class_fill import smooth_noise

COL = {"desert_steppe": (214, 190, 130), "grass_steppe": (178, 182, 104), "meadow_steppe": (134, 166, 84),
       "river_woods": (78, 128, 66), "mountain_rock": (140, 118, 96), "mountain_forest": (46, 88, 60), "korea_forest": (64, 112, 70)}
CLIMATE = {"desert_steppe": "arid", "grass_steppe": "cold", "meadow_steppe": "temperate", "river_woods": "temperate",
           "mountain_rock": "arid", "mountain_forest": "cold", "korea_forest": "cold"}
PROPS = {
    "camp": ["rigidmodels/campaign/settlements/tent_%d.wsmodel" % i for i in range(8)] + ["rigidmodels/campaign/props/194/194_bandit_tent.wsmodel"],
    "outcrop": ["rigidmodels/campaign/rocks/general/general_rock_large_1.wsmodel", "rigidmodels/campaign/rocks/general/general_rock_medium_1.wsmodel",
                "rigidmodels/campaign/rocks/general/general_rock_scree_1.wsmodel"],
    "grove": ["rigidmodels/campaign/vegetation/arid/arid_tree_poplar_medium_1.wsmodel", "rigidmodels/campaign/vegetation/arid/arid_tree_poplar_large_1.wsmodel"],
    "ridge_rock": ["rigidmodels/campaign/mountains/arid/arid_mountain_0%d.wsmodel" % i for i in (1, 3, 5)],
    "ridge_forest": ["rigidmodels/campaign/mountains/cold/cold_ridge_small_1.wsmodel", "rigidmodels/campaign/mountains/cold/cold_peak_1.wsmodel"],
}


def main():
    _, _, w, h, _, f, names = T.load(str(HERE / "hex" / "map.hex"))
    nj = json.load(open(HERE / "regions_new.json", encoding="utf-8"))
    prov = {m: pv["key"] for pv in nj["all_provinces"] for m in pv["members"]}
    disp = {}
    for line in open(HERE / "source" / "text" / "db" / "regions.loc.tsv", encoding="utf-8"):
        a = line.rstrip("\n").split("\t")
        if a[0].startswith("regions_onscreen_"): disp[a[0][17:]] = a[1]
    for p in nj["provinces"].values(): disp.update(p.get("names", {}))
    disp.update({k: v for k, v in nj.get('renames', {}).items() if isinstance(v, str)})
    NA = neighbour_arrays(h, w)
    reg, land = f["region"], f["terr"] == 0
    NP = names.index("3k_main_reg_non_playable")
    pk = np.array([prov.get(n, "") for n in names] + [""])[np.clip(reg, -1, len(names) - 1)]
    nomad = np.char.find(pk.astype(str), "nomad") >= 0
    korea_n = np.isin(pk, ["3k_ironic_province_north_buyeo", "3k_ironic_province_north_okjeo", "3k_ironic_province_goguryeo"])
    rows, cols = np.mgrid[0:h, 0:w]
    backdrop = (reg == NP) & (rows >= 900) & (cols >= 540) & (cols < 1250)
    area = (nomad | korea_n | backdrop) & (f["terr"] != 1)
    _, hh = hex_blend_and_height(w, h)
    hs = ndi.uniform_filter(hh.astype(float), 7)
    rel = ndi.uniform_filter(np.abs(hh.astype(float) - hs), 7)
    e = hs[area]; rel_hi = np.percentile(rel[area], 90); e_hi = np.percentile(e, 90)
    noise = smooth_noise((h, w), 14, 101); noise = (noise - noise.min()) / (np.ptp(noise) + 1e-9)
    redge = f["river"] > 0
    for d, (nr, nc, v) in enumerate(NA):
        mm = v & (((f["river"] >> d) & 1) > 0); redge[nr[mm], nc[mm]] = True
    def grow(m, k):
        for _ in range(k):
            g = m.copy()
            for nr, nc, v in NA: g |= v & m[nr, nc]
            m = g
        return m
    water = (f["terr"] == 1) & grow(area, 3)
    east = cols + 60 * noise
    zone = np.full((h, w), "", object)
    zone[area] = "grass_steppe"
    zone[area & (east < 760) & (rows < 1010)] = "desert_steppe"
    zone[area & (east > 960)] = "meadow_steppe"
    town0 = (f["slot"] >= 0) | (f["sprawl"] > 0)
    tclear = town0.copy()
    for _ in range(6):
        g_ = tclear.copy()
        for nr, nc, v in NA: g_ |= v & tclear[nr, nc]
        tclear = g_
    high = area & ((rel > rel_hi) | (hs > e_hi)) & ~tclear
    zone[high] = "mountain_rock"
    zone[high & ((east > 940) | (rows > 1060))] = "mountain_forest"
    zone[area & grow(redge | water, 2) & ~high & land] = "river_woods"
    zone[korea_n] = "korea_forest"
    # sites
    town = (f["slot"] >= 0) | (f["sprawl"] > 0)
    keep_off = grow(town, 4) | (f["road"] > 0)
    rng = np.random.default_rng(7)
    sites = []
    def pick(mask, n, spacing, kind, models):
        rr, cc = np.nonzero(mask & ~keep_off & land)
        order = rng.permutation(len(rr)); chosen = []
        for i in order:
            r, c = int(rr[i]), int(cc[i])
            if all((c - pc) ** 2 + (r - pr) ** 2 > spacing ** 2 for pc, pr in chosen):
                chosen.append((c, r))
                sites.append(dict(kind=kind, hex=[c, r], x=round(c * HX, 2), z=round(r * HZ + (c & 1) * HZ / 2, 2),
                                  model=models[len(chosen) % len(models)], rot_y=int(rng.integers(0, 360))))
                if len(chosen) >= n: break
    near_water = grow(redge | water, 4)
    steppe_open = np.isin(zone, ["grass_steppe", "meadow_steppe"]) & ~backdrop
    pick(steppe_open & near_water, 30, 14, "camp", PROPS["camp"])
    pick(steppe_open, 40, 14, "camp", PROPS["camp"])
    tops = (hh >= ndi.maximum_filter(hh, 9)) & np.isin(zone, ["grass_steppe", "desert_steppe", "meadow_steppe"])
    pick(tops, 90, 10, "outcrop", PROPS["outcrop"])
    pick(zone == "river_woods", 140, 6, "grove", PROPS["grove"])
    ridge = (hs >= ndi.maximum_filter(hs, 9) - 20)
    pick(ridge & (zone == "mountain_rock"), 40, 14, "ridge_rock", PROPS["ridge_rock"])
    pick(ridge & (zone == "mountain_forest"), 40, 14, "ridge_forest", PROPS["ridge_forest"])
    # json
    rle = {}
    for r in range(h):
        out = []; c = 0
        while c < w:
            if zone[r, c]:
                s = c
                while c < w and zone[r, c] == zone[r, s]: c += 1
                out.append([s, c - s, zone[r, s]])
            else: c += 1
        if out: rle[r] = out
    counts = {z: int((zone == z).sum()) for z in COL}
    json.dump(dict(zone_rle=rle, zone_hexes=counts, climate_suggestion=CLIMATE, sites=sites,
                   site_counts={k: sum(1 for s in sites if s["kind"] == k) for k in PROPS}, prop_models=PROPS),
              open(HERE / "korea_ref" / "steppe_plan.json", "w", encoding="utf-8"), indent=0, ensure_ascii=False)
    # sketch
    rs, cs = np.nonzero(area)
    r0, r1, c0, c1 = rs.min() - 4, min(h, rs.max() + 4), cs.min() - 4, min(w, cs.max() + 4)
    S = 2
    img = np.zeros((r1 - r0, c1 - c0, 3), np.float32); img[...] = (150, 145, 130)
    sub = zone[r0:r1, c0:c1]
    for z, col in COL.items(): img[sub == z] = col
    img[(f["terr"][r0:r1, c0:c1] == 1)] = (70, 100, 150)
    shade = np.clip((hs[r0:r1, c0:c1] - np.percentile(e, 5)) / (np.ptp(e) + 1e-9), 0, 1)[..., None]
    img = img * (0.8 + 0.35 * shade)
    bd = np.zeros((h, w), bool)
    for nr, nc, v in NA: bd |= v & (reg[nr, nc] != reg) & (f["terr"] != 1) & (reg != NP) & (reg[nr, nc] != NP)
    img[bd[r0:r1, c0:c1]] = (40, 40, 40)
    img[backdrop[r0:r1, c0:c1]] = img[backdrop[r0:r1, c0:c1]] * 0.82
    img[(f["river"][r0:r1, c0:c1] > 0)] = (40, 150, 230)
    img[(f["road"][r0:r1, c0:c1] > 0)] = (150, 85, 35)
    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)[::-1]).resize(((c1 - c0) * S, (r1 - r0) * S), Image.NEAREST)
    d = ImageDraw.Draw(im)
    try: fnt = ImageFont.truetype("arial.ttf", 13); big = ImageFont.truetype("arialbd.ttf", 16)
    except Exception: fnt = big = None
    XY = lambda c, r: ((c - c0) * S, (r1 - 1 - r) * S)
    sym = {"camp": ((255, 255, 255), "o"), "outcrop": ((90, 80, 70), "^"), "grove": ((30, 90, 40), "*"),
           "ridge_rock": ((110, 70, 40), "M"), "ridge_forest": ((20, 60, 35), "M")}
    for s in sites:
        x, y = XY(*s["hex"]); col, ch = sym[s["kind"]]
        if ch == "o": d.ellipse((x - 4, y - 4, x + 4, y + 4), fill=col, outline=(0, 0, 0))
        elif ch == "*": d.ellipse((x - 3, y - 3, x + 3, y + 3), fill=col)
        elif ch == "^": d.polygon([(x, y - 4), (x - 4, y + 3), (x + 4, y + 3)], fill=col)
        else: d.polygon([(x - 7, y + 5), (x - 3, y - 6), (x, y), (x + 3, y - 6), (x + 7, y + 5)], fill=col, outline=(0, 0, 0))
    for k in np.unique(reg[(f["slot"] == 0) & area]):
        rr, cc = np.nonzero((f["slot"] == 0) & (reg == k)); x, y = XY(int(cc.mean()), int(rr.mean()))
        d.rectangle((x - 3, y - 3, x + 3, y + 3), fill=(255, 255, 255), outline=(0, 0, 0))
        d.text((x + 5, y - 7), disp.get(names[k], names[k]), fill=(0, 0, 0), font=fnt, stroke_width=2, stroke_fill=(255, 255, 255))
    items = [(z.replace("_", " ") + f" ({CLIMATE[z]})", COL[z]) for z in COL] + [("Land Beyond backdrop = darker", (120, 116, 104)),
             ("o yurt camp", (255, 255, 255)), ("^ rock outcrop", (90, 80, 70)), ("* grove", (30, 90, 40)), ("M ridge props", (110, 70, 40))]
    d.rectangle((6, 6, 280, 12 + 19 * len(items)), fill=(255, 255, 255), outline=(0, 0, 0))
    for i, (t, c) in enumerate(items):
        d.rectangle((12, 12 + i * 19, 26, 24 + i * 19), fill=c, outline=(0, 0, 0)); d.text((32, 11 + i * 19), t, fill=(0, 0, 0), font=fnt)
    im.save(HERE / "korea_ref" / "steppe_plan.png")
    print("zones", counts); print("sites", {k: sum(1 for s in sites if s["kind"] == k) for k in PROPS}); print("image", im.size)


if __name__ == "__main__":
    main()
