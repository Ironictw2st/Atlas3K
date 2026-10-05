#!/usr/bin/env python3
"""Hexi corridor + Xiping polish plan (user 2026-10-02: "keep going with the Hexi corridor and Xiping area"), the same
approach as steppe_plan.py: zones -> climate / ground, a few landmarks, sparse dressing; all vanilla props.

Zones (real-world reference in brackets), built on the carve's own masks (proposal_x15/build_masks.npz via x15_land):
  qilian_peaks     the Qilian wall's high crest              snow peaks: cold peak / ridge props
  qilian_foothill  the wall's lower slopes + Xiping rims      alpine meadow, spruce patches on the slopes
  oasis            3 hexes around the corridor rivers / towns [Ganzhou, Suzhou, Dunhuang oases]  farmland, poplar/elm groves
  corridor_steppe  the rest of the playable corridor          dry grass steppe
  gobi             the desert north of the corridor          [Badain Jaran edge, Beishan] gravel + scree, rare rocks
  juyan            the Juyan delta (Xihai) lakes and banks   reeds, poplar galleries
  xiping_plateau   the Xiping / Huangshui basins              high grassland, Qiang camps, valley farmland
Landmark: the Han frontier wall + beacon line along the corridor's desert edge (Dunhuang -> Guzang) with vanilla
great_wall pieces; Yumen / Yang pass sites west of Dunhuang.
Outputs korea_ref/hexi_plan.png + hexi_plan.json."""
import json, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage as ndi
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
import town_fix as T, x15_land
from hexgrid import neighbour_arrays, HX, HZ
from regions_carve import hex_blend_and_height
from class_fill import smooth_noise

COL = {"qilian_peaks": (225, 225, 230), "qilian_foothill": (120, 140, 96), "oasis": (70, 132, 62), "corridor_steppe": (186, 178, 110),
       "gobi": (205, 180, 128), "juyan": (96, 150, 96), "xiping_plateau": (150, 170, 100)}
CLIMATE = {"qilian_peaks": "cold", "qilian_foothill": "cold", "oasis": "temperate", "corridor_steppe": "arid", "gobi": "arid",
           "juyan": "arid", "xiping_plateau": "cold"}
PROPS = {
    "peak": ["rigidmodels/campaign/mountains/cold/cold_peak_1.wsmodel", "rigidmodels/campaign/mountains/cold/cold_peak_2.wsmodel",
             "rigidmodels/campaign/mountains/cold/cold_ridges_1.wsmodel"],
    "grove": ["rigidmodels/campaign/vegetation/arid/arid_tree_poplar_medium_1.wsmodel", "rigidmodels/campaign/vegetation/arid/arid_tree_poplar_large_1.wsmodel"],
    "camp": ["rigidmodels/campaign/settlements/tent_%d.wsmodel" % i for i in range(8)],
    "outcrop": ["rigidmodels/campaign/rocks/general/general_rock_scree_1.wsmodel", "rigidmodels/campaign/rocks/general/general_rock_medium_1.wsmodel"],
    "wall": ["rigidmodels/campaign/area_of_interest/great_wall/great_wall_broken_diag_1_up.wsmodel"],
    "spruce": ["rigidmodels/campaign/vegetation/cold/cold_tree_fir_medium_1.wsmodel"],
}
PROVS = ("3k_ironic_province_hanyang", "3k_ironic_province_zhangye_sg", "3k_main_province_wuwei", "3k_ironic_province_xiping", "3k_main_province_jincheng")


def main():
    _, _, w, h, _, f, names = T.load(str(HERE / "hex" / "map.hex"))
    nj = json.load(open(HERE / "regions_new.json", encoding="utf-8"))
    prov = {m: pv["key"] for pv in nj["all_provinces"] for m in pv["members"]}
    disp = {}
    for line in open(HERE / "source" / "text" / "db" / "regions.loc.tsv", encoding="utf-8"):
        a = line.rstrip("\n").split("\t")
        if a[0].startswith("regions_onscreen_"): disp[a[0][17:]] = a[1]
    for p in nj["provinces"].values(): disp.update(p.get("names", {}))
    disp.update({k: v for k, v in nj.get("renames", {}).items() if isinstance(v, str)})
    NA = neighbour_arrays(h, w)
    reg, land = f["region"], f["terr"] == 0
    NP = names.index("3k_main_reg_non_playable")
    pk = np.array([prov.get(n, "") for n in names] + [""])[np.clip(reg, -1, len(names) - 1)]
    rows, cols = np.mgrid[0:h, 0:w]
    M = x15_land.masks(w, h)
    ours = np.isin(pk, PROVS)
    area = (f["terr"] != 1) & (cols < 480) & (rows > 690) & (ours | (reg == NP))
    _, hh = hex_blend_and_height(w, h)
    hs = ndi.uniform_filter(hh.astype(float), 5)
    noise = smooth_noise((h, w), 12, 111); noise = (noise - noise.min()) / (np.ptp(noise) + 1e-9)
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
    town = (f["slot"] >= 0) | (f["sprawl"] > 0)
    mtn = (M["hexi_mountain"] if M else np.zeros((h, w), bool)) | ((reg == NP) & (hs > np.percentile(hs[area], 75)))
    play = M["hexi_play"] if M else np.zeros((h, w), bool)
    desert = M["hexi_desert"] if M else np.zeros((h, w), bool)
    zone = np.full((h, w), "", object)
    zone[area] = "gobi"
    zone[area & (play | ours)] = "corridor_steppe"
    zone[area & np.isin(pk, ["3k_ironic_province_xiping", "3k_main_province_jincheng"])] = "xiping_plateau"
    m_area = area & mtn
    crest = m_area & (hs > np.percentile(hs[m_area], 55) if m_area.any() else False)
    zone[m_area] = "qilian_foothill"; zone[crest] = "qilian_peaks"
    zone[area & desert & ~mtn] = "gobi"
    zone[area & grow(redge | town, 3) & ~mtn & land & (np.isin(zone, ["corridor_steppe", "gobi", "xiping_plateau"]))] = "oasis"
    zone[area & grow(water, 3) & (rows > 960) & ~mtn] = "juyan"
    # sites
    keep_off = grow(town, 4) | (f["road"] > 0)
    rng = np.random.default_rng(11); sites = []
    def add(kind, c, r, models, n):
        sites.append(dict(kind=kind, hex=[int(c), int(r)], x=round(c * HX, 2), z=round(r * HZ + (c & 1) * HZ / 2, 2),
                          model=models[n % len(models)], rot_y=int(rng.integers(0, 360))))
    def pick(mask, n, spacing, kind, models):
        rr, cc = np.nonzero(mask & ~keep_off & (f["terr"] != 1))
        chosen = []
        for i in rng.permutation(len(rr)):
            r, c = int(rr[i]), int(cc[i])
            if all((c - pc) ** 2 + (r - pr) ** 2 > spacing ** 2 for pc, pr in chosen):
                chosen.append((c, r)); add(kind, c, r, models, len(chosen))
                if len(chosen) >= n: break
    ridge = hs >= ndi.maximum_filter(hs, 9) - 30
    pick(ridge & (zone == "qilian_peaks"), 45, 12, "peak", PROPS["peak"])
    pick((zone == "qilian_foothill") & (noise < 0.45), 60, 6, "spruce", PROPS["spruce"])
    pick(zone == "oasis", 120, 5, "grove", PROPS["grove"])
    pick(zone == "juyan", 30, 5, "grove", PROPS["grove"])
    pick((zone == "xiping_plateau") | (zone == "qilian_foothill") & (noise > 0.6), 22, 14, "camp", PROPS["camp"])
    pick(zone == "gobi", 60, 12, "outcrop", PROPS["outcrop"])
    # the Han frontier wall: the corridor hexes touching the desert, west -> east, every ~7 hexes
    edge = (zone == "corridor_steppe") | (zone == "oasis")
    nd = np.zeros((h, w), bool)
    for nr, nc, v in NA: nd |= v & (zone[nr, nc] == "gobi")
    wall_line = edge & nd & ~keep_off
    wall = []
    for c in range(0, 480, 7):
        rr = np.nonzero(wall_line[:, c])[0]
        if len(rr): wall.append((c, int(rr.max())))                    # the northernmost corridor/desert contact in the column
    for i, (c, r) in enumerate(wall): add("wall", c, r, PROPS["wall"], i)
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
              open(HERE / "korea_ref" / "hexi_plan.json", "w", encoding="utf-8"), indent=0, ensure_ascii=False)
    # sketch
    rs, cs = np.nonzero(area)
    r0, r1, c0, c1 = rs.min() - 3, min(h, rs.max() + 3), max(0, cs.min() - 3), min(w, cs.max() + 3)
    S = 3
    img = np.zeros((r1 - r0, c1 - c0, 3), np.float32); img[...] = (150, 145, 130)
    sub = zone[r0:r1, c0:c1]
    for z, col in COL.items(): img[sub == z] = col
    img[(f["terr"][r0:r1, c0:c1] == 1)] = (70, 110, 160)
    e = hs[area]
    shade = np.clip((hs[r0:r1, c0:c1] - np.percentile(e, 5)) / (np.ptp(e) + 1e-9), 0, 1)[..., None]
    img = img * (0.78 + 0.3 * shade)
    img[((reg == NP) & area)[r0:r1, c0:c1]] *= 0.85
    bd = np.zeros((h, w), bool)
    for nr, nc, v in NA: bd |= v & (reg[nr, nc] != reg) & (f["terr"] != 1) & (reg != NP) & (reg[nr, nc] != NP)
    img[bd[r0:r1, c0:c1]] = (40, 40, 40)
    img[(f["river"][r0:r1, c0:c1] > 0)] = (40, 150, 230)
    img[(f["road"][r0:r1, c0:c1] > 0)] = (150, 85, 35)
    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)[::-1]).resize(((c1 - c0) * S, (r1 - r0) * S), Image.NEAREST)
    d = ImageDraw.Draw(im)
    try: fnt = ImageFont.truetype("arial.ttf", 14)
    except Exception: fnt = None
    XY = lambda c, r: ((c - c0) * S + 1, (r1 - 1 - r) * S + 1)
    if len(wall) > 1: d.line([XY(c, r) for c, r in wall], fill=(120, 60, 40), width=3)
    for s in sites:
        x, y = XY(*s["hex"]); k = s["kind"]
        if k == "peak": d.polygon([(x - 7, y + 5), (x, y - 8), (x + 7, y + 5)], fill=(250, 250, 255), outline=(60, 60, 70))
        elif k in ("grove", "spruce"): d.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(30, 90, 40) if k == "grove" else (20, 60, 50))
        elif k == "camp": d.ellipse((x - 4, y - 4, x + 4, y + 4), fill=(255, 255, 255), outline=(0, 0, 0))
        elif k == "outcrop": d.polygon([(x, y - 4), (x - 4, y + 3), (x + 4, y + 3)], fill=(110, 95, 80))
        elif k == "wall": d.rectangle((x - 3, y - 3, x + 3, y + 3), fill=(150, 70, 40), outline=(0, 0, 0))
    for k in np.unique(reg[(f["slot"] == 0) & area]):
        rr, cc = np.nonzero((f["slot"] == 0) & (reg == k)); x, y = XY(int(cc.mean()), int(rr.mean()))
        d.rectangle((x - 4, y - 4, x + 4, y + 4), fill=(255, 255, 255), outline=(0, 0, 0))
        d.text((x + 6, y - 8), disp.get(names[k], names[k]), fill=(0, 0, 0), font=fnt, stroke_width=2, stroke_fill=(255, 255, 255))
    items = [(z.replace("_", " ") + f" ({CLIMATE[z]})", COL[z]) for z in COL] + [("Han frontier wall + beacons", (150, 70, 40)),
             ("snow peak props", (250, 250, 255)), ("grove / spruce", (30, 90, 40)), ("camp", (255, 255, 255)), ("gobi outcrop", (110, 95, 80))]
    d.rectangle((6, 6, 250, 12 + 19 * len(items)), fill=(255, 255, 255), outline=(0, 0, 0))
    for i, (t, c) in enumerate(items):
        d.rectangle((12, 12 + i * 19, 26, 24 + i * 19), fill=c, outline=(0, 0, 0)); d.text((32, 11 + i * 19), t, fill=(0, 0, 0), font=fnt)
    im.save(HERE / "korea_ref" / "hexi_plan.png")
    print("zones", counts); print("sites", {k: sum(1 for s in sites if s["kind"] == k) for k in PROPS}); print("image", im.size)


if __name__ == "__main__":
    main()
