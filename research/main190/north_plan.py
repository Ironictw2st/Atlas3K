#!/usr/bin/env python3
"""North polish plan (user 2026-10-02): a sketch of what North Buyeo / North Okjeo / Goguryeo (+ the Xuantu / East Okjeo
edges) should look like - trees and pathways - before any tile / prop / tree edits.

From our own data only (read-only): hex/map.hex (regions, towns, roads, rivers, coast) and the hex heights
(regions_carve.hex_blend_and_height, the DEM-based lf). Output:
  korea_ref/north_plan.png   labelled top-down sketch (forest types, clearings, paths, ranges, towns)
  korea_ref/north_plan.json  the spec: biome per hex (RLE by row), proposed paths (hex lists), mountain-range prop
                             placements (world x, z, vanilla model, scale, rotation) and a prop shopping list.
Biomes (real-world reference: Changbai / Zhangguangcai highlands = mixed conifer-broadleaf forest; NE coast = taiga;
Songnen / Liao plain = forest-steppe with riverine woods):
  highland   relief / elevation in the top band            -> dense conifer forest, ranges get mountain props
  taiga      the north-east coast belt                        -> dense conifer
  mixed      valleys and hills between                        -> mixed forest with clearings
  steppe     the low flat plain (North Buyeo west)           -> grassland, groves + river woods only"""
import heapq, json, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
import town_fix as T
from hexgrid import neighbour_arrays, HX, HZ
from regions_carve import hex_blend_and_height
from class_fill import smooth_noise

PROVS = {"3k_ironic_province_north_buyeo": "North Buyeo", "3k_ironic_province_north_okjeo": "North Okjeo",
         "3k_ironic_province_goguryeo": "Goguryeo", "3k_ironic_province_hyunto": "Xuantu", "3k_ironic_province_dongokjeo": "East Okjeo"}
CORE = {"3k_ironic_province_north_buyeo", "3k_ironic_province_north_okjeo", "3k_ironic_province_goguryeo"}
COL = {"steppe": (196, 196, 120), "mixed": (84, 140, 70), "highland": (40, 92, 56), "taiga": (30, 74, 66)}


def main():
    _, _, w, h, _, f, names = T.load(str(HERE / "hex" / "map.hex"))
    nj = json.load(open(HERE / "regions_new.json", encoding="utf-8"))
    disp = {}
    for line in open(HERE / "source" / "text" / "db" / "regions.loc.tsv", encoding="utf-8"):
        a = line.rstrip("\n").split("\t")
        if a[0].startswith("regions_onscreen_"): disp[a[0][17:]] = a[1]
    for p in nj["provinces"].values(): disp.update(p.get("names", {}))
    disp.update({k: v for k, v in nj.get("renames", {}).items() if isinstance(v, str)})
    prov_of = {m: pv["key"] for pv in nj["all_provinces"] for m in pv["members"]}
    NA = neighbour_arrays(h, w)
    reg = f["region"]; land = f["terr"] == 0
    regkey = np.array([prov_of.get(n, "") for n in names] + [""])
    pk = regkey[np.clip(reg, -1, len(names) - 1)]
    area = np.isin(pk, list(PROVS)) & (f["terr"] != 1)
    core = np.isin(pk, list(CORE)) & land
    _, hh = hex_blend_and_height(w, h)
    rel = np.zeros((h, w), np.float32)
    for nr, nc, v in NA: rel = np.maximum(rel, np.where(v, np.abs(hh[nr, nc] - hh), 0))
    # smooth elevation (local average) to read massifs, not single hexes
    from scipy import ndimage as ndi
    hs = ndi.uniform_filter(hh.astype(float), 9)
    e_core = hs[area]; lo, hi = np.percentile(e_core, 25), np.percentile(e_core, 80)
    rows, cols = np.mgrid[0:h, 0:w]
    noise = smooth_noise((h, w), 10, 91); noise = (noise - noise.min()) / (np.ptp(noise) + 1e-9)
    biome = np.full((h, w), "", object)
    biome[area & (hs >= hi)] = "highland"
    biome[area & (hs < hi) & (hs >= lo)] = "mixed"
    biome[area & (hs < lo)] = "steppe"
    biome[area & (cols > 1380 + 40 * noise) & (hs >= lo)] = "taiga"                  # the north-east coast belt (North Okjeo)
    # trees: density by biome + noise; clearings around towns / along roads and river banks
    town = (f["slot"] >= 0) | (f["sprawl"] > 0)
    def grow(m, k):
        for _ in range(k):
            g = m.copy()
            for nr, nc, v in NA: g |= v & m[nr, nc]
            m = g
        return m
    redge = f["river"] > 0
    for d, (nr, nc, v) in enumerate(NA):
        mm = v & (((f["river"] >> d) & 1) > 0); redge[nr[mm], nc[mm]] = True
    clear = grow(town, 3) | grow(f["road"] > 0, 1) | redge
    dens = {"highland": 0.85, "taiga": 0.8, "mixed": 0.55, "steppe": 0.08}
    tree = np.zeros((h, w), bool)
    for b, d in dens.items():
        tree |= (biome == b) & (noise < d)
    tree |= (biome == "steppe") & grow(redge, 2) & ~redge & (noise < 0.6)   # riverine woods on the plain
    tree &= land & ~clear
    # proposed paths: towns in the core without a road link to a neighbour province town get a valley path
    towns = {}
    for k in np.unique(reg[f["slot"] == 0]):
        if pk[f["slot"] == 0][0] is None: pass
        rr, cc = np.nonzero((f["slot"] == 0) & (reg == k))
        if area[int(rr.mean()), int(cc.mean())]: towns[names[k]] = (int(cc.mean()), int(rr.mean()))
    cost = 1.0 + 6.0 * (rel / (np.percentile(rel[area], 95) + 1e-9)).clip(0, 1) + 2.0 * noise + 3.0 * (f["road"] > 0) * 0
    paths = []
    tk = list(towns)
    pairs = set()
    for a in tk:                                                           # each town to its 2 nearest towns
        ca, ra = towns[a]
        near = sorted(tk, key=lambda b: (towns[b][0] - ca) ** 2 + (towns[b][1] - ra) ** 2)[1:3]
        for b in near: pairs.add(tuple(sorted((a, b))))
    for a, b in sorted(pairs):
        (ca, ra), (cb, rb) = towns[a], towns[b]
        dist = {(ra, ca): 0.0}; prev = {(ra, ca): None}; q = [(0.0, (ra, ca))]
        while q:
            d, u = heapq.heappop(q)
            if u == (rb, cb): break
            if d > dist[u]: continue
            for nr, nc, v in NA:
                if not v[u]: continue
                x = (int(nr[u]), int(nc[u]))
                if not land[x] or f["imp"][x] and not core[x]: continue
                nd = d + float(cost[x])
                if nd < dist.get(x, 1e18): dist[x] = nd; prev[x] = u; heapq.heappush(q, (nd, x))
        if (rb, cb) not in prev: continue
        path = [(rb, cb)]
        while prev[path[-1]] is not None: path.append(prev[path[-1]])
        on_road = sum(1 for p in path if f["road"][p] > 0) / len(path)
        paths.append(dict(a=disp.get(a, a), b=disp.get(b, b), hexes=[[int(p[1]), int(p[0])] for p in path], existing_road_share=round(on_road, 2)))
    # mountain ranges for props: highland ridge hexes (local maxima of smoothed elevation along the massif), spaced
    ridge = (biome == "highland") & core & (hs >= ndi.maximum_filter(hs, 5) - 30) & ~grow(town, 6) & ~grow(f["road"] > 0, 3)
    rr, cc = np.nonzero(ridge)
    placed = []
    for r, c in sorted(zip(rr.tolist(), cc.tolist()), key=lambda p: -hs[p]):
        if all((c - pc) ** 2 + (r - pr) ** 2 > 9 ** 2 for pc, pr, *_ in placed):
            big = hs[r, c] > np.percentile(e_core, 93)
            placed.append((c, r, "rigidmodels/campaign/mountains/cold/" + ("cold_peak_2.wsmodel" if big else "cold_ridge_small_1.wsmodel"),
                           0.16 if big else 0.12, int(noise[r, c] * 360)))
    props = [dict(x=round(c * HX, 2), z=round(r * HZ + (c & 1) * HZ / 2, 2), hex=[c, r], model=m, scale=s, rot_y=rot) for c, r, m, s, rot in placed]
    # biome RLE per row (core + edges)
    rle = {}
    for r in range(h):
        row = biome[r]; out = []; c = 0
        while c < w:
            if row[c]:
                s = c
                while c < w and row[c] == row[s]: c += 1
                out.append([s, c - s, row[s]])
            else: c += 1
        if out: rle[r] = out
    shop = {"trees": {"highland": "vegetation/cold (pine / larch groups)", "taiga": "vegetation/cold (spruce / pine)",
                      "mixed": "vegetation/temperate + cold (birch, oak, pine)", "steppe": "vegetation/arid poplar groves, river willows"},
            "mountains": {"cold_peak_2.wsmodel": sum(1 for p in props if "peak" in p["model"]),
                          "cold_ridge_small_1.wsmodel": sum(1 for p in props if "ridge" in p["model"])},
            "custom": "1 test range mesh (Blender, DEM ridge of Changbai) - korea_ref/north_test.blend"}
    json.dump(dict(biome_rle=rle, paths=paths, mountain_props=props, shopping_list=shop,
                   tree_hexes=int(tree.sum()), area_hexes=int(area.sum())),
              open(HERE / "korea_ref" / "north_plan.json", "w", encoding="utf-8"), indent=0, ensure_ascii=False)
    # ---- sketch
    rs, cs = np.nonzero(area)
    r0, r1, c0, c1 = rs.min() - 6, min(h, rs.max() + 6), cs.min() - 6, min(w, cs.max() + 6)
    S = 3
    img = np.zeros((r1 - r0, c1 - c0, 3), np.float32); img[...] = (150, 145, 130)
    sea = f["terr"][r0:r1, c0:c1] == 1; img[sea] = (70, 100, 150)
    b_ = biome[r0:r1, c0:c1]
    for b, col in COL.items(): img[b_ == b] = col
    t_ = tree[r0:r1, c0:c1]; img[t_] = img[t_] * 0.62
    # shading from relief
    shade = np.clip((hs[r0:r1, c0:c1] - lo) / (hi - lo + 1e-9), 0, 1)[..., None]
    img = img * (0.85 + 0.25 * shade)
    cl = clear[r0:r1, c0:c1] & area[r0:r1, c0:c1] & ~sea; img[cl] = img[cl] * 0.5 + np.array([235, 225, 170]) * 0.5
    bd = np.zeros((h, w), bool)
    for nr, nc, v in NA: bd |= v & (reg[nr, nc] != reg) & (f["terr"] != 1)
    img[bd[r0:r1, c0:c1]] = (35, 35, 35)
    img[(f["river"][r0:r1, c0:c1] > 0)] = (40, 150, 230)
    img[(f["road"][r0:r1, c0:c1] > 0)] = (150, 85, 35)
    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)[::-1]).resize(((c1 - c0) * S, (r1 - r0) * S), Image.NEAREST)
    d = ImageDraw.Draw(im)
    try: fnt = ImageFont.truetype("arial.ttf", 15); big = ImageFont.truetype("arialbd.ttf", 22)
    except Exception: fnt = big = None
    XY = lambda c, r: ((c - c0) * S + 1, (r1 - 1 - r) * S + 1)
    for p in paths:
        pts = [XY(c, r) for c, r in p["hexes"]]
        for i in range(0, len(pts) - 1, 2): d.line([pts[i], pts[i + 1]], fill=(255, 235, 120), width=2)
    for p in props:
        x, y = XY(*p["hex"]); s = 9 if "peak" in p["model"] else 6
        d.polygon([(x, y - s), (x - s, y + s), (x + s, y + s)], fill=(120, 110, 100), outline=(30, 30, 30))
    for k, (c, r) in towns.items():
        x, y = XY(c, r); d.rectangle((x - 4, y - 4, x + 4, y + 4), fill=(255, 255, 255), outline=(0, 0, 0))
        d.text((x + 7, y - 9), disp.get(k, k), fill=(0, 0, 0), font=fnt, stroke_width=2, stroke_fill=(255, 255, 255))
    for key, label in PROVS.items():
        m = (pk == key) & land
        if not m.any(): continue
        rr_, cc_ = np.nonzero(m); x, y = XY(int(np.median(cc_)), int(np.median(rr_)) + 12)
        d.text((x, y), label.upper(), fill=(255, 255, 255), font=big, stroke_width=3, stroke_fill=(0, 0, 0))
    # legend
    lx, ly = 12, 12
    items = [("Highland conifer forest", COL["highland"]), ("Taiga (NE coast)", COL["taiga"]), ("Mixed forest", COL["mixed"]),
             ("Forest-steppe / grassland", COL["steppe"]), ("Darker = trees", (60, 60, 60)), ("Clearing (towns, roads, banks)", (220, 210, 160)),
             ("Road (existing)", (150, 85, 35)), ("Proposed path", (255, 235, 120)), ("River", (40, 150, 230)), ("Mountain prop site", (120, 110, 100))]
    d.rectangle((lx - 6, ly - 6, lx + 260, ly + 22 * len(items) + 4), fill=(255, 255, 255), outline=(0, 0, 0))
    for i, (t, c) in enumerate(items):
        d.rectangle((lx, ly + i * 22, lx + 16, ly + i * 22 + 14), fill=c, outline=(0, 0, 0)); d.text((lx + 24, ly + i * 22), t, fill=(0, 0, 0), font=fnt)
    im.save(HERE / "korea_ref" / "north_plan.png")
    print(f"area {int(area.sum())} hexes, trees {int(tree.sum())}, paths {len(paths)}, mountain prop sites {len(props)} -> korea_ref/north_plan.png")


if __name__ == "__main__":
    main()
