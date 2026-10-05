# main190: culling the northern mountains for new tribal provinces

**Status: analysis and proposal only.** Nothing in the pipeline has been changed: no edits to `regions_carve6.py`, `hex/*.hex`, `research_r6/candidates.json`, `terrain/`, the assembly kit or any pack.

**Request (user):** "I want to cull some of the mountains and props in the Northern side, so we can add some more northern provinces for the Northern Tribes."

**Where the work lives:** `research/main190/research_r6/north/`. The analysis ran on a snapshot of `hex/map.hex` (`map_snapshot.hex`, taken 2026-09-30 13:21) because another carve6 run was rewriting the live file. Spacing was re-checked against the live map as of 13:32 (`map_live_1332.hex`).

## 1. Findings

### The georef is badly off in the north-east

`geo_hex` (rubber + warp) puts real seats far from 190E's own towns in the north-east, because 190E's map is stylised there. This is the first reason earlier nomad candidates failed: carve6 searched 30 hexes around a point that was 50 to 70 hexes from where the towns actually are.

| Region | Offset from its real seat |
|---|---|
| Liucheng, Xiangping (Liaoxi / Liaodong) | about 60–65 hexes (~220 km) |
| Gungnae, Pyongyang, Jiuyuan (Wuyuan) | about 50–63 hexes |
| Tuyin, Linyu, Zhuolu, Yinguan, Fanzhi (Youbeiping / Dai / Yanmen) | about 20–30 hexes |
| Ji, Lunu, Nanpi | under 6 hexes (the georef is fine here) |

The fix used here is a town-anchored correction: a Gaussian IDW of the residuals at 17 anchor towns (`anchors.json`, sigma 40 hexes). It brings every anchor to within about 5–20 hexes. All real-terrain comparisons below use this corrected mapping. Each proposed town also carries a `carve_latlon`: a lat/lon that carve6's uncorrected `geo_hex` maps onto the chosen site, so the towns work with carve6 as it is.

### The non-playable (NP) land is impassable everywhere

All NP land north of 38.5N is impassable: 213,855 hexes, 100 %. carve6's nomad placement requires `ok_site`, which needs `imp == 0`, so no nomad town could ever sit on NP land. This is the second reason the Meiji, Yunzhong, Juyong and Yuyang candidates failed, together with the georef offset.

Unlike the Hexi padland, the north has no step that makes NP land passable according to the mountain mask.

### About half of the northern "mountains" sit on real lowland

The analysis area is 198,224 land hexes: corrected lat ≥ 38.5 and 106–128E. 57,630 of them carry a mountain blend class (4–7). The real terrain comes from Copernicus GLO-90, using local relief (max minus min elevation within ±4 km):

| Real terrain under the mountain-class hexes | Hexes | Share |
|---|---|---|
| Flat (relief under 180 m) | 28,513 | 49 % |
| Hills (180–350 m) | 13,692 | 24 % |
| Real mountains (350 m or more) | 15,425 | 27 % |

At the same time, 16,888 hexes that sit on real ranges are *not* painted as mountains. 190E puts its mountains in the wrong places as well as painting too many of them.

The worst areas:
- **Liao river plain:** 83 % flat in reality, but 5,562 of 6,752 hexes are mountain class. The Hyunto and Liaodong regions are painted as a mountain block.
- **Bashang steppe** (Tanshihuai's and Kebineng's land): 73 % flat, but 6,817 of 11,209 hexes are mountain and all of it is impassable NP.
- **Songhua / Nenjiang fringe** (Buyeo): 85 % flat, with 9,036 mountain hexes.
- **Tumed plain** (Yunzhong / Dingxiang): 54 % flat, with 2,060 mountain hexes and 4,110 impassable.
- **Sanggan basin** (Pingcheng / Dai): 31 % flat and 28 % hill, with 1,541 mountain hexes, and 76 % of it is NP.

The 190E "northern frame" is a brown band 40–60 hexes deep that runs from the Yin shan to the Songhua. Its heights are mostly a smooth plateau, so the mountains there are mostly texture plus the impassable flag. The game heightmap relief is about the same under mountain and non-mountain classes.

Real ranges that should stay, and the terrain under them:

| Range | Real terrain |
|---|---|
| Yan shan | 62 % real mountain |
| Taihang / Heng / Wutai | 70 % |
| Chengde / Luan hills | 72 % |
| Yanqing–Huailai–Xuanhua | 71 % (at a ±4 km scale its narrow basins read as mountain) |
| Changbai / Goguryeo hills | 53 % |

The Yin shan is a thin ridge (13 %) inside a much wider painted band.

### Props

There are few mountain or rock props in the north. Across the whole map there are 2,364 unique mountain/rock props; only 107 lie north of 38.5N (cold peaks and ridges, arid mountains, rocks). Most of them are in the NP frame. Their footprint mask covers 2,368 hexes.

Most of the northern "prop clutter" is vegetation: about 5,100 unique arid and temperate tree props. Each tree appears as 5 seasonal variants, so that is about 1,000 trees. There are also tree-raster classes.

The AK folder holds 543 layer files, but the `.terry` project references only 266. Every prop exists in two layer files, a referenced one and an unreferenced copy. carve6's `prop_mask` globs all of them.

## 2. Cull proposal

### Rules

**Area.** The rules apply in the analysis area (corrected lat ≥ 38.5, 106–128E), and only inside existing playable regions plus the NP land handed to the tribal regions (below). The rest of the NP frame stays as it is.

**Ranges kept (`keep_range`).** A hex is kept as mountain where the real relief is 350 m or more, after a 1-hex morphological close and after dropping specks smaller than 8 hexes. Hexes where 190E sculpted a peak (game height relief of 3,000 units or more) that is at least a real hill are kept too. This leaves the Yin, Yan, Taihang, Heng/Wutai, Greater Khingan and Changbai as ranges at roughly their real widths, with the valleys and passes between them open.

**Blend cull (`cull_blend`).** Mountain classes 4–7 outside `keep_range` are repainted:
- real flat, west of 120E → class 20 (steppe);
- real flat, east of 120E → class 21 (grass);
- real hill → class 27 (light forest / hill).

Mountain specks smaller than 6 hexes that are left inside the area go as well.

**Impassable cull (`cull_imp_playable`).** Inside existing regions, impassable hexes that are not mountain after the cull and not in `keep_range` become passable. Forest classes 29/30 stay impassable only on real hills. The forest painted over the flat Horqin sands (Changli region) goes.

**Opened land (`zone_open`).** This is NP land that the tribal regions' territories take: a noisy Dijkstra from all towns, with existing towns starting 10 behind, and each tribal region capped at 2,800 hexes. It becomes playable, and impassable is set equal to the post-cull mountain mask, the same rule carve6 uses for the Hexi padland. Buyeo also needs a 102-hex link corridor, which opens 48 NP hexes.

**Props.** Mountain and rock props on culled or opened hexes that are not in `keep_range` are removed. Vegetation props within 2 hexes of the new town footprints are also removed; this is the same rule as `tree_clear`'s `TOWN_RING`.

### Hex counts (final masks)

| What | Hexes / entities |
|---|---|
| Mountain class in the area, before → after | 57,630 → 31,797 |
| **Blend cull total** | **25,830** |
| … of it inside existing regions | 12,283 |
| … of it in the opened NP land | 13,547 |
| … repainted as flat (steppe or grass) | 19,140 |
| … repainted as hill | 6,690 |
| … also needing optional height smoothing (tier 2) | 1,665 |
| Impassable → passable inside existing regions | 9,260 |
| NP opened for the tribes | 32,039 (26,709 passable after the cull) |
| Impassable in the area, before → after | 155,895 → 119,926 |
| Mountain and rock props removed | 26 of 107 in the north (prop-mask footprint 2,368 → 1,731 hexes) |
| Vegetation props removed near new towns | 280 entities (including seasonal variants) |

### Per zone

Zones are boxes in corrected real lat/lon, from `nc.ZONES`. The mountain and impassable counts cover all land in each box. "NP opened" counts the hexes the tribal regions take.

| Zone | Land hexes | Real flat / hill / mountain | Mountain class before → after | Impassable before → after | NP opened |
|---|---|---|---|---|---|
| Hetao plain (Shuofang/Wuyuan) | 2,622 | 79% / 10% / 11% | 35 → 32 | 1,077 → 730 | 0 |
| Tumed plain (Yunzhong/Dingxiang) | 4,876 | 54% / 20% / 27% | 2,060 → 949 | 4,110 → 1,442 | 2,506 |
| Ordos edge (Meiji / Shang) | 9,464 | 84% / 15% / 1% | 560 → 218 | 767 → 394 | 30 |
| Sanggan basin (Dai/Pingcheng) | 3,662 | 31% / 28% / 41% | 1,541 → 616 | 2,856 → 925 | 1,918 |
| Yanqing-Huailai-Xuanhua (Shanggu) | 1,415 | 10% / 18% / 71% | 846 → 809 | 781 → 725 | 31 |
| Bashang steppe (Xianbei Danhan) | 11,209 | 73% / 18% / 9% | 6,817 → 2,645 | 11,209 → 4,659 | 6,550 |
| Chengde / Luan valleys (Baitan) | 2,827 | 2% / 26% / 72% | 2,032 → 1,924 | 2,446 → 1,705 | 731 |
| Daling / Liucheng (Liaoxi Wuhuan) | 3,378 | 41% / 47% / 12% | 1,108 → 654 | 2,351 → 766 | 1,064 |
| Liao river plain | 6,752 | 83% / 10% / 7% | 5,562 → 481 | 524 → 4 | 0 |
| Liaodong peninsula | 1,787 | 59% / 20% / 21% | 972 → 326 | 69 → 2 | 0 |
| Songhua / Nenjiang fringe (Buyeo) | 21,571 | 85% / 9% / 6% | 9,036 → 4,365 | 21,497 → 15,780 | 4,803 |
| Yin shan (range kept) | 8,091 | 67% / 20% / 13% | 4,740 → 3,226 | 7,775 → 5,484 | 1,934 |
| Yan shan (range kept) | 2,971 | 15% / 23% / 62% | 2,057 → 1,801 | 1,599 → 1,443 | 1 |
| Taihang / Heng / Wutai (range kept) | 3,782 | 15% / 15% / 70% | 881 → 647 | 1,214 → 961 | 42 |
| Greater Khingan south (range kept) | 12,192 | 55% / 29% / 15% | 67 → 53 | 12,192 → 9,068 | 2,174 |
| Changbai / Goguryeo hills (range kept) | 17,619 | 18% / 30% / 53% | 11,568 → 8,885 | 11,711 → 9,801 | 377 |

Pictures:
- `research/main190/previews/north_cull_before.png`
- `research/main190/previews/north_cull_after.png` (the green outline marks the repainted mountain; pale yellow is opened NP land)

### How it would be done in the pipeline

The pipeline order is: `terrain_main → dem_fill → coast_carve → class_fill → korea_fix → tilemap_main → ak_main → regions_carve6 → tree_clear → regions_db → extras_main`. The changes, in the order they would run:

1. **Blend and tree rasters.** Add a new step, e.g. `north_cull_apply.py`, after `class_fill.py` and before `korea_fix` and `tilemap_main`.
   - Load `research_r6/north/cull_blend.npy`, which holds hex (col,row) pairs.
   - In `terrain/3k_dlc07_main_map.blend.*.tif`, repaint the class 4–7 pixels whose hex is in the mask (quarter raster, 2 px per hex, as in `class_fill`). Use ranked smooth noise over class_fill's STEPPE / GRASS / FOREST mixes rather than one flat class, so the result looks like patches.
   - Redraw the tree raster for those pixels from the 190E per-class tree distribution, exactly as `class_fill` does.
   - Because `hex_blend_and_height()` reads this raster, carve6's `mountain` mask and `ok_site` follow automatically.
   - Optional tier 2: smooth the height raster in `height_flag.npy` (1,665 hexes).
   - Keep the originals in `terrain/_warp_only/`, as class_fill does.
2. **Impassable, ground and opened land in `regions_carve6.py`.** carve6 reads `map_korea.hex`, so the flags belong in carve6, next to the Liang-zone step:
   - `f["imp"][cull_imp_playable] = 0`
   - `f["imp"][zone_open] = mountain[zone_open]`
   - ground type `GROUND_BY_BLEND[hb]` for culled hexes
   - climate / attr / aoi copied from the nearest playable hex for opened land (step 8 `conv`)
   - nomad `allowed = ok_site & (zone_open | playable)`
   - territory `area = playable | padland | zone_open`
   - unclaimed zone land → NP with impassable set
   - a size cap (2,800) for nomad regions, like `MAX_FRONTIER`
   - add the tribal labels to `KEY_GROUP` as `"nomad"`
   - extend the 6b valley bridge (or `LINKS`) to nomad regions, for Buyeo's link
   - use each town's `carve_latlon` (or put the anchor IDW into `geo_hex`)
3. **Props in `ak_main.py`.** In `do_layer`, drop the 26 mountain/rock entities listed in `north_cull.json → prop_cull.entities`, matched on warped position and model, in both layer copies. Also drop the 280 vegetation entities near the new towns, or extend `tree_clear.py` to cover AK vegetation entities as well as the tree list. BOB then rebuilds `global_props.bin`. carve6's `prop_mask` should read only the layers the `.terry` references.
4. **After the carve.** Run `tree_clear.py` (trees near towns and roads). `regions_db.py` needs DB rows for `3k_ironic_province_<key>` and the regions. `extras_main.py` already draws borders for the `ironic_nomad_` prefix. The painted overlay and minimap in the 190E part still show 190E's painted mountains; repainting them is a separate, optional task.

## 3. Proposed tribal provinces

The proposal has **7 provinces and 19 regions**: 4 core provinces (11 regions) and 3 optional ones (8 regions). Each town was placed with carve6's own rules on the post-cull map:
- 30-hex search around the corrected seat;
- `ok_site` with blocked share under 0.2 within about 4 hexes;
- template footprints, `sprawl_ok`, no river under a slot;
- resource 24–60 walking steps from its capital, on the capital's real side.

Spacing is at least **20 walking steps** from every town. It was checked with a BFS over post-cull passability against:
- the snapshot's towns;
- the live 13:32 map's towns (including the round-7 Zhuo / Hejian / Quyang placements);
- the not-yet-placed `candidates.json` seats north of 38N;
- each other.

Names are checked against `research_r6/name_registry.json` (190E and vanilla, regions and provinces) and against `candidates.json`. None of them clash, and none of the keys exist in the hex. Taken names that were avoided: Liucheng, Yangle, Changli, Gaoliu, Xuantu and Wuyuan are 190E regions, and "Liaoxi" is the Yu province's name.

| Province (tier) | Region key | Town | Real seat lat, lon | Site hex (col,row) | Hexes | Nearest town (steps) | To capital (steps) |
|---|---|---|---|---|---|---|---|
| Southern Xiongnu (core) | `ironic_nomad_xiongnu_capital` | Meiji | 39.85, 111.0 | (655, 694) | 1,532 | 38 (Heyin, Shuofang capital) | - |
| Southern Xiongnu (core) | `ironic_nomad_xiongnu_resource_1` | Yuanyang | 38.75, 110.45 | (646, 656) | 1,205 | 20 (Pingding, Shuofang resource_1) | 43 |
| Yunzhong Xianbei (core) | `ironic_nomad_budugen_capital` | Chengle | 40.37, 111.82 | (704, 708) | 2,800 | 24 (new Wuquan) | - |
| Yunzhong Xianbei (core) | `ironic_nomad_budugen_resource_1` | Yunzhong | 40.28, 111.2 | (664, 709) | 1,748 | 40 (new Chengle) | 40 |
| Yunzhong Xianbei (core) | `ironic_nomad_budugen_resource_2` | Wuquan | 40.95, 111.75 | (721, 723) | 2,800 | 24 (new Chengle) | 24 |
| Danhan Xianbei (core) | `ironic_nomad_kebineng_capital` | Danhan | 41.15, 114.05 | (821, 732) | 2,800 | 37 (new Chuochou) | - |
| Danhan Xianbei (core) | `ironic_nomad_kebineng_resource_1` | Chuochou | 41.6, 114.9 | (858, 742) | 1,761 | 31 (new Rushui) | 37 |
| Danhan Xianbei (core) | `ironic_nomad_kebineng_resource_2` | Rushui | 41.95, 116.0 | (881, 761) | 2,800 | 31 (new Chuochou) | 60 |
| Wuhuan (core) | `ironic_nomad_wuhuan_capital` | Pinggang | 41.55, 118.9 | (969, 745) | 1,604 | 26 (new Baitan) | - |
| Wuhuan (core) | `ironic_nomad_wuhuan_resource_1` | Baitan | 40.95, 117.3 | (943, 746) | 1,462 | 26 (new Pinggang) | 26 |
| Wuhuan (core) | `ironic_nomad_wuhuan_resource_2` | Raole | 43.0, 119.3 | (969, 786) | 2,591 | 41 (new Pinggang) | 41 |
| Dai Wuhuan (optional) | `ironic_nomad_daiwuhuan_capital` | Pingcheng | 40.08, 113.3 | (785, 695) | 2,422 | 46 (Fanzhi, Yanmen resource_1) | - |
| Dai Wuhuan (optional) | `ironic_nomad_daiwuhuan_resource_1` | Shanwu | 39.99, 112.47 | (743, 693) | 1,717 | 36 (Yinguan, Yanmen capital) | 46 |
| Eastern Xianbei (optional) | `ironic_nomad_suli_capital` | Chishan | 43.6, 120.6 | (1024, 807) | 1,733 | 31 (new Xiliao) | - |
| Eastern Xianbei (optional) | `ironic_nomad_suli_resource_1` | Xiliao | 43.05, 121.35 | (1047, 787) | 1,571 | 29 (new Wulu) | 31 |
| Eastern Xianbei (optional) | `ironic_nomad_suli_resource_2` | Wulu | 42.05, 121.65 | (1049, 759) | 1,214 | 23 (Xuantu, Liaodong resource_1) | 60 |
| Buyeo (optional) | `ironic_nomad_buyeo_capital` | Buyeo | 43.85, 126.55 | (1284, 820) | 2,803 | 38 (new Nongan) | - |
| Buyeo (optional) | `ironic_nomad_buyeo_resource_1` | Nongan | 44.43, 125.17 | (1246, 836) | 959 | 38 (new Buyeo) | 38 |
| Buyeo (optional) | `ironic_nomad_buyeo_resource_2` | Yitong | 43.35, 125.35 | (1224, 801) | 2,845 | 46 (new Nongan) | 60 |

Why each province matters around 190:

- **Southern Xiongnu (core).** The chanyu's court was at Meiji. The Xiongnu hordes rose in 188 and killed the chanyu Qiangqu. Yufuluo's host then fought with Yuan Shao and Zhang Yang and raided Henei and Hedong through the 190s. Huchuquan submitted to Cao Cao in 216.
  - Both towns are carved out of 190E's Shuofang land. Heyin (Shuofang capital) shrinks from 2,897 to 1,009 hexes and Pingding (Shuofang resource_1) from 3,460 to 2,622.
  - A Yunzhong resource north of the river cannot be connected to Meiji without a ford.
- **Yunzhong Xianbei, Budugen (core).** Budugen, Kuitou's brother and of Tanshihuai's line, held the Yunzhong and Yanmen frontier with about 10,000 households. Han had abandoned Yunzhong, Dingxiang, Wuyuan and Shuofang in the 180s. The province covers the Tumed plain and the Yin shan front.
- **Danhan Xianbei, Kebineng (core).** Tanshihuai's old court was at Mount Danhan on the Chuochou river. Kebineng rose on the Dai and Shanggu frontier and was the strongest Xianbei chief by 218. The province covers the Bashang steppe.
- **Wuhuan (core).** Qiuliju (d. about 193), then Tadun, united the Wuhuan of Liaoxi, Youbeiping and Liaodong shuguo. They backed Yuan Shao against Gongsun Zan and later sheltered Yuan Shang and Yuan Xi. Cao Cao's march of 207 went Baitan → Pinggang → White Wolf Mountain → Liucheng. Liucheng is already 190E's Yu resource, so the province lies north-west of it.
- **Dai Wuhuan (optional).** The Sanggan basin and abandoned Dingxiang formed a Wuhuan and Xianbei frontier. Nengchendi's Dai Wuhuan later allied with Kebineng (218). It replaces **Shanggu Wuhuan (Nanlou, seat Ning)**, which cannot be placed: the live map puts `ironic_central_zhuo_resource_1` at (856,702), exactly on the Ning site, and the Yanqing–Huailai basins are really mountainous.
- **Eastern Xianbei, Suli / Mijia / Queji (optional).** These chiefs held the land beyond Liaoxi and Youbeiping. The province takes 2,691 hexes from 190E's oversized Changli region (4,990 → 2,299) and 464 from Xuantu.
- **Buyeo (optional).** King Wigudae married a daughter of Gongsun Du and was Liaodong's ally against Goguryeo and the Xianbei. The province is all opened NP land and needs the 102-hex link corridor. Goguryeo already exists in 190E (Gungnae-seong).

Picture: `research/main190/previews/north_tribes_proposal.png`. Tribal regions are coloured by province; mountains are shaded; kept props are red dots; the new footprints are yellow.

## 4. Files

| File | Contents |
|---|---|
| `docs/main190_north_cull_proposal.md` | this document |
| `research/main190/research_r6/north/north_cull.json` | criteria, masks, prop cull list (26 mountain/rock entities plus 280 vegetation entities), stats, territory and donors, provinces in the `candidates.json` shape plus `regions[]` (key, site, `carve_latlon`, corrected target, spacing, size, donors, clash flags) |
| `research/main190/research_r6/north/cull_blend.npy`, `cull_imp_playable.npy`, `zone_open.npy` (= `zone_final.npy`), `open_nomad.npy`, `keep_range.npy`, `height_flag.npy` | hex masks as int32 (col,row) pairs; the map is 1428×896 and row 0 is the south edge |
| `research/main190/research_r6/north/anchors.json` | the georef residual anchors |
| `research/main190/previews/north_cull_before.png`, `north_cull_after.png`, `north_tribes_proposal.png` | the pictures |

Scripts, to re-run in this order:
1. `dem_hex.py` builds the north DEM mosaic. It reads `research_r6/north/dem/` (102 extra GLO-90 tiles, 448 MB, kept out of `dem/` so `dem_fill` is not affected) through `fp3.py`.
2. `anchors.py`
3. `north_cull.py`
4. `sites.py`
5. `territory.py`
6. `north_cull.py` again, then `sites.py` again (`chain.sh` runs steps 3–6)
7. `draw_cull.py`, `draw_tribes.py`
8. `finalize.py`

## 5. Uncertainties

- **Registration.** The north-east georef correction is an IDW over 17 towns, some of them mutually inconsistent (Yangle and Liucheng). Residual error is about 5–20 hexes, so real ridges and 190E's painted ranges may be a few hexes apart. Check `keep_range` visually in Liaodong and Korea.
- **Thresholds.** The relief thresholds (350 m and 180 m within ±4 km) are a judgement. At that scale the narrow Yanqing, Huailai and Luan basins read as mountain, so they stay mostly mountain.
- **Map in flux.** The map was changing while this ran. Spacing was checked against the snapshot plus the 13:32 live map; re-run `sites.py` and `finalize.py` on the final carve6 output. The round-7 Zhuo resource has already removed the Shanggu Wuhuan site.
- **Seat coordinates.** Several coordinates are approximate: Yuanyang, Wulu, Chishan, Rushui, Chuochou, and Danhan's exact mountain. Nongan, Yitong and Xiliao are modern placeholder names; Buyeo-era names are unknown. Wuquan's site is 29 hexes from its seat (east of Chengle rather than north); Baitan's is 24.
- **Region sizes.** Eight tribal regions are larger than carve6's `MAX_AREA` of 1,850, and six of them sit at or just above the 2,800 cap (the north is scaled x1.4). carve6 only enforces the 550 minimum for new regions, but the vanilla p90 is 1,850; lower the cap if that matters.
- **3D relief.** A blend-only cull leaves 190E's height relief under 1,665 culled hexes. They will look like grassy hills unless the optional height smoothing is done.
- **DEM reading (correction).** Plain `C:\python311` tifffile cannot decode the GLO-90 tiles, which use floating-point predictor 3. The pipeline is not affected: `dem_fill.py` puts `output/pylibs` on `sys.path`, and the tifffile there reads `dem/*.tif`. The analysis scripts here use their own small decoder, `fp3.py`.

## 6. Implementation (approved scope: the 4 core provinces)

The user approved the 4 core provinces only. Dai Wuhuan, Eastern Xianbei and Buyeo are dropped, so there is no Buyeo corridor. The masks were recomputed with `NORTH_CORE=1` (`research_r6/north/chain.sh`). The raster and impassable cull now stops at corrected lon 124E, so it does not overlap `korea_fix`. Near the tribal territory it spreads 3 to 10 hexes outward with a noisy edge.

Final counts for the core scope:

| What | Hexes / entities |
|---|---|
| Blend cull | 18,827 (9,695 in existing regions) |
| Impassable → passable in existing regions | 7,554 |
| Tribal territory taken from the non-playable land (`zone_open`) | 20,760 |
| `open_nomad` (zone plus a 4-hex margin) | 25,116 |
| Mountain/rock props dropped | 24 unique (each also sits in the duplicate layer copy) |
| Vegetation props near the core towns | 0 |

The module is `research/main190/north_cull.py`:
- `apply_rasters(terrain_dir, log)`: run it after `class_fill.py` and before `korea_fix.py`. It is idempotent: the pristine rasters are kept in `<terrain_dir>/_pre_north/` and refreshed whenever the rasters are no longer its own output.
- `apply_hex(f, names, reg, terr, NA, log, mountain=None)`: called in carve6 after the Liang step.
- `drop_prop(entity_text, nx, nz)`: hooked in `ak_main.do_entity` after the warp.

The candidates are in `research_r6/north/candidates_north.json` and the tests in `research_r6/north/test_north_cull.py` (they run on copies in `research_r6/north/test/`).
