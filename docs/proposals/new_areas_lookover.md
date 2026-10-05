# New areas look-over: props, trees, ground textures, heightmap (proposal, no edits)

Map `3k_190e_expanded_map` (kit `assembly_kit_190E`, state of 2026-10-04 18:52). This is a read-only review. Nothing in the kit, packs or research scripts was changed.

Evidence, scripts and tables are in `output/proposals/new_areas/`:
- `metrics_by_group_climate.csv`: every number below, per group and climate.
- `py/`: the measurement scripts. Rerun them after the build to check the targets.
- `audit/`: a fresh `map-audit`.
- `ops_A_*.json`: ready-made ops batches.
- Images: `overview_flags.png`, `map_height_steps.png`, `height_*.png`, `blend_*.png`, `seam_*.png`, `sheet_citytour_*.png`.

## How it was measured

- **Groups:** groups come from `hex/map.hex` regions.
  - **hexi:** `ironic_hexi_*` plus `ironic_region_{hanyang,xi,wuwei,xiping}`.
  - **nomad:** `ironic_nomad_*` plus `ironic_region_wuyuan`.
  - **korea_ne:** the remaining `ironic_region_*`.
  - **central / south:** `ironic_central_*` and `ironic_south_*`.
  - **vanilla:** the playable `3k_*` regions of this map. This is the baseline.
  - Non-playable land is split into **np_old** (190E footprint) and **np_new** (the west/north padding, from `terrain/pad_mask.png`).
- **Climate codes:** 0 arid, 1 cold, 3 subtropical, 4 temperate. `climate_map.png` agrees with the map.hex climate on 99.6% or more of land hexes in every group, so there is no climate-map problem.
- **Inputs:**
  - Props: all entities of the kit layers (84,866).
  - Trees: kit tree raster, 2 px per hex.
  - Ground: kit BlendCampaign TIF. Palette index maps to `texture_arrays.xml` groups: 0-3 arid, 4-7 cold (the red "mountain" ground), 19-22 steppe, 23-26 subtropical, 27-30 temperate.
  - Heights: kit height TIF, 8 px per hex, sea level 14219.
- **Baseline caveat:** the whole map is a x1.5 spread of 190E with life-size props. "Vanilla" here means the vanilla regions *as they are on this map*.

## Summary

Central and south look like vanilla on every metric, because their content is carried over from the vanilla layers. Their only issue is inherited duplicate props. The problems are in **Hexi, the steppe (nomad), Korea/NE and the padding**, and they are mostly in the rasters, not the props:

1. **Heightmap block steps and stripe seams** around the Hexi DEM zone and along the old 190E north edge. These are visible in playable regions (Xiping, Longxi, Hanyang, Xi, Budugen, Wuwei).
2. **Mountain ground texture on flat farmland/steppe** (Korea north, Liaodong/Xuantu, the steppe, Xiping).
3. **Hex-stepped and straight-line texture borders** in Hexi and the padding.
4. **Bamboo and southern evergreens in the north-west.**
5. Smaller items:
   - The steppe has too many trees.
   - The generated poplars have no seasonal variants.
   - Korea has no rocks or mountain meshes.
   - Hexi and Korea rivers run along slopes instead of valleys.
   - Camp fences repeat a lot.

`overview_flags.png` shows where items 1, 2 and 4 are on the map.

## Prioritized changes

### HIGH

**H1. Height steps, block artefacts and stripe seams (Hexi zone, Ordos and the old north edge)**
- **What's wrong:** the raster has isolated one-pixel jumps of 270 to 1150 u16 at every 8-pixel (hex-column) border inside a band. On vanilla land the median slope is 36 per pixel. Sample at col 600, row 960: 0, 270, 1155 in consecutive 8-pixel blocks.
- **How common, measured as step pixels per 1000 land hexes:**

  | Group | Step pixels per 1000 land hexes |
  |---|---|
  | vanilla | 4.7 |
  | hexi | **350** |
  | np_new | 97 |
  | korea_ne | 73 (mostly coast) |
  | nomad | 66 |
  | central | 30 |
  | south | 0.4 |

- **Where the steps are:**
  - The four edges of a rectangle: cols 0 to ~605, rows ~695 to ~1050. This is the Hexi zone from `research_r6/hexi_zone.npz`.
  - A curved 12-hex band around the Yellow River loop and Xiping/Longxi.
  - A full-width east-west band at rows ~1040-1075 (the old 190E north edge). That band is 3% of the rows but holds 13-18% of all stripe detections.
- **Playable hexes affected (inland, off-river):**

  | Region | Hexes with steps | Share of the region |
  |---|---|---|
  | `ironic_region_xiping_capital` | 391 | 11% |
  | `ironic_nomad_budugen_resource_2` | 368 | 13% |
  | `ironic_region_hanyang_capital` | 303 | |
  | `ironic_region_xi_resource_1` | 299 | |
  | `ironic_central_longxi_capital` | 186 | 17% |
  | `3k_main_wuwei_capital` | 159 | |

- **Images:** `map_height_steps.png`, `height_ordos.png`, `height_xiping_longxi.png` (the waffle bands), `seam_sw_height.png` (row ~690-701, cols 146-320: about 11 rows of horizontal stripes plus a straight edge).
- **Root cause:** in `hexi_geo.py`, `weight()` looks up the 12-hex ramp weight per hex with `np.rint`, so the weight is constant within each hex. `to_lonlat` then blends two different projections (rubber georef and Guzang) with that stepped weight. Each hex therefore samples the DEM from a jumping position. The zone mask is also partly a hard rectangle (`west = cols <= xg-2 & lat >= 34`, plus the north rows copied from the top row). The north band is terrain_main's edge-clamped streaks that dem_fill did not fully remove.
- **Proposed fix:** a new one-off script, `terrain_polish.py`, built the same way as `ranges_relief.py`. It edits `terrain/<map>.height.*.tif` in place, keeps a backup in `terrain/_pre_terrain_polish/`, and leaves a marker `hex/.terrain_polish`.
  - Mask: pixels found by the step detector in `py/steps.py`, grown by 8 px. Add the hexi_geo ramp band (0 < w < 1), the rectangle edges ±12 px, and rows 1040-1075 (±10 px) on land.
  - Inside the mask, replace the heights with a masked Gaussian (σ ≈ 6-8 px, iterated 3 times). Feather it into the unmasked ground.
  - Never touch pixels below sea level + 300, river-hex pixels, or coast-carve pixels.
  - For future rebuilds of the terrain chain, also fix the root cause:
    - `hexi_geo.weight`: switch to bilinear `ndi.map_coordinates(Z["w"], ..., order=1)`.
    - `dem_fill.sample`: blend the DEM *metres* sampled under both georefs instead of blending lon/lat.
    - Re-running the chain (terrain_main → dem_fill → coast_carve → class_fill → korea_fix → north_cull → ranges_relief → jeju) is not proposed now. It would redo many one-off passes.
- **Effect:** target step pixels below 20 per 1000 hexes in hexi, nomad and np_new. No waffle bands at Xiping, Longxi or Ordos.
- **Risk:** low to medium.
  - Ground under props changes by up to a few tenths of a unit. `kit_edits/01_sink_floating_mountains.json` sets absolute y values, and 3 of those 50 mountains are within 3 hexes of a step hex. Re-run `map-audit --checks floating-mountain,buried-mountain,floating-prop` after the build and refresh op 01 if needed.
  - Generated props are seated at build time by ak_main, so they follow the new ground.
- **Rebuild:** yes (height). `relief_build.sh` already copies the height into the kit.

**H2. Mountain ("cold", Qilian-red) ground texture on flat, passable land**
- **What's wrong:** share of passable hexes with local mean slope below 30 that carry blend classes 4-7:

  | Group | Share |
  |---|---|
  | vanilla | 9.0% |
  | central | 0.7% |
  | south | 6.0% |
  | korea_ne | **35.7%** |
  | nomad | **35.0%** |
  | hexi | **25.0%** |

  That is 20,143 hexes. The worst regions:

  | Region | Share |
  |---|---|
  | `ironic_region_xiping_resource_1` | 66% |
  | `dongokjeo_resource_2` | 57% |
  | `hyunto_resource_1` | 57% |
  | `hyunto_capital` | 53% |
  | `hyunto_resource_2` | 33% |
  | `nomad_suli_*` | 24-36% |
  | `nomad_kebineng_resource_4` | 31% |
  | `buyeo_resource_1` | 24% |
  | `budugen_capital` | 22% |
  | `goguryeo_resource_1` | 22% |

  In the Korea/NE crop, a wide red band runs across Buyeo/Goguryeo, and its north side is a straight line at row ~1058. See the orange areas in `overview_flags.png`, plus `blend_korea_ne.png` and `blend_nomad.png`.
- **Where it comes from:** `class_fill.py` paints mountain classes by DEM elevation per zone ("steppe: mountains > 1600 m", "manchu: hills > 700 m"). High but flat plateaus therefore get mountain ground. `north_cull.py` already fixes this, but only in its 4 core tribal provinces.
- **Proposed fix:** a new one-off script, `blend_polish.py` (H2 and H3 together). It edits `terrain/<map>.blend.*.tif` in place, with a backup and a marker.
  - Select hexes that are passable, have a 5-hex mean slope below 30, are in hexi, nomad or korea_ne, and carry blend 4-7. The mask is the one in `scratch/flat_mountain_texture_mask.npy`.
  - Reclass them by climate: arid and cold climates go to steppe 19-22, temperate goes to temperate 27-30. For Xiping, keep cold ground on slopes and use steppe in the basins (as `hexi_plan.py` intends: "high grassland").
  - Pick the variant per *pixel* with 2-octave smooth noise (the class_fill method), not per hex.
- **Effect:** target below 12% for each of the three groups (vanilla is 9%). The plains read as plains.
- **Risk:** low. Only the texture changes; tiles, passability and props are untouched.
- **Rebuild:** yes. The blend must be copied into the kit (see the batched plan, because `relief_build.sh` does not copy it). Native `rasters,global_map` then rebuilds `global_blend.dds`.

**H3. Hex-stepped texture borders and straight seams (Hexi, padding, old north edge)**
- **What's wrong:** share of horizontal texture transitions that fall exactly on a hex-column border. Random placement gives 12.5%.

  | Group | Share on hex borders |
  |---|---|
  | vanilla | 13.7% |
  | central | 13.7% |
  | korea_ne | 14.6% |
  | nomad | 15.1% |
  | hexi | **47.9%** |
  | np_new | **49.7%** |

  Other evidence:
  - Hexi uses 10 classes per climate where vanilla uses 21, so large areas carry a single texture. Transition density is 0.16 per hex in Hexi against 0.53 in vanilla.
  - The corridor has a dead-straight east-west border between arid and steppe ground (`blend_hexi_zoom_fullres.png`, cols 100-220, row ~940).
  - A "comb" of vertical dark-green streaks runs along row ~1053 across Hexi, the steppe and the NE (`seam_north_hexi_blend.png`, `blend_nomad.png`). Blend stripe detections in rows 1040-1075 total 731 + 692 (rows + cols).
  - In the viewer, Xiping and Suli show stepped patches (`sheet_citytour_hexi.png`, `sheet_citytour_nomad.png`).
- **Root cause:** class_fill picks the class per hex. The comb is the edge-clamped padding streaks; class_fill's SEAM dither did not cover them.
- **Proposed fix:** in the same `blend_polish.py`, restricted to hexi, np_new, the north band (rows 1035-1080) and the Hexi rectangle edges:
  - (a) Domain-warp re-sample: read the class at (x + dx, y + dy), where dx and dy are smooth noise of about ±6 px. Then apply a 5×5 majority filter. This turns hex staircases into organic borders.
  - (b) Comb band: redraw the classes from the rows 12 px outside the band, mirrored with noise.
  - (c) Corridor: add 1-2 extra steppe/arid variants per zone (class_fill's ranked-noise mix) so single-texture areas get patches.
- **Effect:** target hex-border share below 18%, and no straight lines or comb. Ground variety comes closer to vanilla.
- **Risk:** low (texture only). Do not run it on Korea's south, where korea_fix already gives about 14.6%.
- **Rebuild:** yes, the same blend copy as H2.

**H4. Subtropical trees (bamboo, castanopsis) in the north-west**
- **What's wrong:** share of tree hexes north of row 700 that carry tree classes 0-3:

  | Group | Share |
  |---|---|
  | vanilla | 0.1% |
  | nomad | 0.0% |
  | korea_ne | 0.4% |
  | hexi | **24.5%** (cold climate: 27.3%) |
  | np_new | **35.9%** (39% in cold climate) |

  See the purple areas in `overview_flags.png`.
- **Root cause:** `class_fill.py` draws tree classes "from the 190E tree distribution for each blend class", which mixes in southern species. `trees_x15.py` step 1 keeps that raster for the new land and pads.
- **Proposed fix:** a new one-off script, `trees_polish.py`, run on `terrain/<TREE>` plus the kit raw copy and `tree_new`, the same files trees_x15 writes. For new-land and pad hexes north of row ~430, remap classes by climate with a stable per-hex hash:

  | Class | Arid | Cold | Temperate |
  |---|---|---|---|
  | 0-1 (bamboo) | poplar 9/16 | fir 4/6 | katsura 7/8/14/15 |
  | 2-3 (castanopsis) | poplar 9/16 | fir 4/6 | katsura 7/8/14/15 |

  Alternatively, add the remap as a step 1b inside `trees_x15.py`.
- **Effect:** target below 1%. No bamboo in the Gobi or on the Qilian.
- **Risk:** very low. `tree_clear.py` keeps clearing towns and roads afterwards.
- **Rebuild:** yes. The tree list is rebuilt by `extras_main.trees()` in `relief_build.sh`.

### MEDIUM

**M1. Steppe over-forested, and patchy "speckle" forests**
- **What's wrong:**
  - Tree cover on arid steppe is 35.5% in nomad against 17.4% for vanilla arid, and 37% of those trees are fir.
  - Patches are small and ragged: mean patch size is 16.6 hexes in Hexi and 36.4 in nomad, against 68.6 in vanilla. Edge-hex share is 59.5% and 61.0% against 37.7%.
  - Korea has 57.9% cover against 40.1% for vanilla temperate, and its fir share is 39% against 7%.
- **Proposed fix:** extend `trees_polish.py`:
  - Thin nomad arid hexes to about 18% cover: drop patches smaller than 4 hexes first, then the outer ring of the remaining patches.
  - Majority-smooth new-land forests (3×3 hex), which removes most single-hex speckle.
  - Optional for Korea: lowland (bottom height tercile) fir → katsura at 50%.
- **Effect:** steppe reads as open grassland, with forests in real blocks.
- **Risk:** low.
- **Rebuild:** same build as H4.

**M2. Generated poplar groves: two models and no seasonal variants**
- **What's wrong:**
  - `north_dress.POPLAR` holds only `arid_tree_poplar_medium_1` and `arid_tree_poplar_large_1`, placed with `season_mask=""`.
  - Vanilla places every poplar as a set of 5 entities: the base model plus spring, harvest, autumn and winter variants (1017 masked sets in the kit). The generated groves therefore keep summer leaves in winter.
  - Hexi tree props use 2 models (entropy 1.0 bit). Vanilla uses 100 models (5.45 bits). The 2,033 unmasked poplars are almost all north_dress output.
  - 7% of Hexi tree props stand on river hexes (vanilla: 1.9%).
- **Proposed fix in `north_dress.py`:**
  - Use POPLAR = small_1, medium_1, medium_2, large_1, large_2.
  - Emit the vanilla 5-entity seasonal set per tree, with the same transform and `season_mask` values as vanilla.
  - Skip river hexes for groves.
  - FIR is evergreen, so leave it as is.
- **Effect:** seasons work, and groves look less cloned.
- **Risk:** low. Prop count grows by about 4× for groves (roughly 2,000 → 8,000 entities), which is fine for global_props.
- **Rebuild:** yes, the props part (ak_main) of the same build.

**M3. Korea/NE has almost no landscape props**
- **What's wrong:** per 1000 land hexes in Korea, with vanilla temperate in brackets:
  - Mountain meshes: 0 (0.4).
  - Rock props: 0 (1.9).
  - Tree props: 0.1 (16.8).
  - Countryside settlement pieces: 74.6 (117.9).
- Korea's 9,728 impassable hexes have 1 mountain prop in total. The reason is that Korea is stock 190E, so `village_dress.py` skips it ("regions stock 190E doesn't have") and `north_dress` covers only the steppe and Hexi plans. See `sheet_citytour_korea.png`.
- **Proposed fix:**
  - (a) `village_dress.py`: add the korea_ne regions to the region list with their own density. About 1.2 clusters per 1000 hexes lifts the settlement pieces to about 100 per 1000 hexes. Add the Korea ambient groups too.
  - (b) `north_dress.py`: add a "korea_ridges" rule that puts the same ridge/peak and rock-outcrop routine on Korea impassable mountain hexes. Use about 1 mountain prop per 100 impassable hexes, sunk with `korea_ref/vanilla_sink.json`, and keep it off towns via `town_props_scan.covered`.
- **Effect:** Korea gets the vanilla look of farmsteads and rocky ridges.
- **Risk:** medium (new content). Check it with `py/props_density.py` and `map-audit` after the build.
- **Rebuild:** yes, the props part.

**M4. Rivers run on slopes instead of in valleys (Hexi, Korea)**
- **What's wrong:** share of river hexes higher than the mean of the non-river land within 3 hexes:

  | Group | Share |
  |---|---|
  | vanilla | 25.9% |
  | central | 17.2% |
  | nomad | 22.7% |
  | hexi | **54.9%** |
  | korea_ne | **41.3%** |

  The Hexi rivers are the Kongming rivers drawn over the Guzang-projected DEM, and Korea's rivers sit on 190E/vanilla relief.
- **Proposed fix:** add a river-valley carve to `terrain_polish.py`, written like `coast_carve.py`. Along the hexi and korea_ne river hexes, lower the ground to at most the local 25th percentile within 3 hexes, using a 2-hex smooth valley profile. Cap the change at 1500 u16, never touch sea pixels, and keep the ends at the river mouths.
- **Effect:** the river meshes sit in visible valleys.
- **Risk:** medium. The native `rivers` and `global_props` steps rebuild the river meshes. Re-audit floating props near rivers afterwards.
- **Rebuild:** yes (height).

**M5. Padding backdrop (np_new: 237k hexes, 26% of all land) is bare, with flat-topped cliffs at the west edge**
- **What's wrong:**
  - Mountain props: 0.17 per 1000 impassable hexes, against 1.29 on np_old.
  - Settlement pieces and tree props: 0.
  - 4.4% of padding pixels sit at the u16 maximum (65535 flat tops). The 190E source has 1.3%.
  - At the map's west edge (cols 3-12, rows 786-1011) there are cliff clusters with slope above 700 per pixel (282, 121 and 69 hexes). One of them is inside `ironic_region_hanyang_capital` (cols ~8-12, row ~929).
- **Proposed fix:**
  - In `terrain_polish.py`, soft-knee the np_new heights above their 99th percentile so they do not saturate.
  - Feather the outermost 12 columns toward the inner ground (this is not a hard clamp).
  - In `north_dress.py`, extend the ridge/peak routine to np_new ridges within about 25 hexes of playable land, at the np_old density (about 1.3 per 1000 impassable hexes).
- **Effect:** the backdrop seen from the Hexi and Xianbei cameras gets relief and silhouettes.
- **Risk:** low.
- **Rebuild:** yes (height, props).

**M6. Camp fence repetition**
- **What's wrong:** `fence_1_level1.wsmodel` is 27% of Hexi non-tree props (589) and 17% in nomad (746). Vanilla's most-used model is about 8%.
- **Proposed fix in `village_dress.py` camp builder:**
  - Cap pen fence pieces per camp at about 6.
  - Alternate fence variants: the `.rigid_model_v2` and `.wsmodel` versions, plus `wall_1`.
  - Spend the freed budget on carts, hay and log piles that are already in the camp kit.
- **Effect:** less grid-like pens.
- **Risk:** low.
- **Rebuild:** props part.

### LOW

**L1. Audit cleanup (kit_edits ops, ready-made)**
- New-area duplicates (same model and transform): 159, as `ops_A_remove_duplicates_new_areas.json` (deletes).
  - Rates per 100k land hexes: south 93 (243), central 55 (85), vanilla 38.
  - All of them are inherited from stock 190E/vanilla layers, mostly `roof_1_corner_level3` stacks, so their ids are stable.
- Floating rocks: 2, in central Beidi and Qi, as `ops_A_seat_floating_props_new_areas.json`.
- Buried mountains: 3, on np_new, as `ops_A_lift_buried_mountains_new_areas.json`.
- Buried props: 82 (`ops_A_seat_buried_props_new_areas.json`). This is optional. The rate is at or below vanilla's: 19 per 100k for korea_ne and 63 for central, against 59 for vanilla. It is mostly `platform_wood_1` sunk 0.2, which is how vanilla does it too.
- **Rebuild:** these replay in any build through `kit_edits.py`.

**L2. Leave as is**
- `resource_salt_1` at scale 0.8 (22 cases, south and central). Vanilla has 9 of the same.
- 2 floating-mountain infos in nomad (rests-on-mountain, under 2.5 units).
- Central and south ground, trees and heights are vanilla-like:

  | Metric | Central | South |
  |---|---|---|
  | Hex-border transition share | 13.7% | 14.2% |
  | Step pixels per 1000 hexes | 30 | 0.4 |
  | Tree cover | 39.8% (temperate) | 47.1% (subtropical) |

- Trees on towns, roads and rivers in the tree raster: 0% in every group, so tree_clear works.
- Climate map vs map.hex climate: at least 99.6% agreement.

## Batched plan: one rebuild

**Stage 0: code and data, no build**
1. Write three one-off raster scripts. Each works in place on `research/main190/terrain/`, keeps a backup dir and a `hex/.<name>` marker, has a `--dry` mode that writes previews, and refuses to run twice.
   - `terrain_polish.py`: H1 seams, M4 river carve, M5 padding knee.
   - `blend_polish.py`: H2 and H3.
   - `trees_polish.py`: H4 and M1. It also writes the kit raw copy and `tree_new`, like trees_x15.
2. Make the pipeline edits:
   - `north_dress.py`: M2, M3(b) and M5 props.
   - `village_dress.py`: M3(a) and M6.
   - `hexi_geo.py` / `dem_fill.py`: the root-cause fix for H1. It only takes effect if the terrain chain is ever rerun.
3. kit_edits: copy the `ops_A_*.json` files you want into `kit_edits/` as `05_…`, `06_…`, and add their lines to `EDITS`. Use `y_only` for the seat ops. Ids are stable because these entities come from stock layers, not generators.

**Stage 1: dry checks, minutes**
- Run each polish script with `--dry`.
- Run `python ak_main.py` into `ak/` (not installed). Then run `py/props_density.py`, `py/props_rep.py` and `polish_audit.py` against the ak output.
- Pass targets:

  | Metric | Target |
  |---|---|
  | Step pixels per 1000 hexes (hexi, nomad) | < 20 |
  | Mountain texture on flat land (hexi, nomad, korea_ne) | < 12% |
  | Hex-border texture transitions (hexi, np_new) | < 18% |
  | Bamboo/castanopsis share in the north | < 1% |
  | Nomad arid tree cover | 18-20% |
  | Korea rock and mountain props | > 0 |

**Stage 2: one build**
- Run the three polish scripts for real, then `relief_build.sh` (or `hexi_build.sh` if CAIME/startpos also need a refresh for other reasons).
- `relief_build.sh` needs one addition before `native ...`: `cp terrain/$OLD.blend.191fd8068da8020.tif "$RT/$NEW.blend.191fd8068da8020.tif"`. Today it copies only the layers and the height. The tree raster reaches the kit through `trees_polish.py`.
- The native steps it already runs (`rasters, tile_list, global_map, global_mesh, rivers, global_props, camera_heightmap`) plus `extras_main.trees()` cover everything above.

**Stage 3: verify**
- Run `map-audit` and rerun the `py/` metrics. Refresh `kit_edits/01` only if floating or buried mountains reappear near the H1 seams.
- In game, look at Xiping/Longxi, Ordos (Budugen res. 2 and Wuyuan), Hyunto/Dongokjeo/Buyeo, the Juyan/Dunhuang corridor, and the north edge at Suli.

## What could not be checked

- **Viewer tours:** the region tour (`--region-tour … ironic_hexi_`) produced no frames in about 20 minutes while the game was running (it looked stuck waiting for the 3D view), so I stopped it. Visual evidence comes from raster renders (texture families coloured with hillshade, so not the real texture art) and the existing `output/previews/citytour190` shots, which have region tints. There is no `--shots` set.
- **In game:** not checked, because the game was in use by another session.
- **Effect on the compiled tiles:** the steps were found on the kit raster. How visible they are in game depends on the compiled mesh LOD. The H1 regions should be the first in-game check after the build.
