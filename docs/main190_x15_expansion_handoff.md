# Handoff: 190E x1.5 map expansion / region proposal

Written 2026-10-01 so someone (or a fresh Claude session) can pick the work up cold. Sources: the user's memory notes
(`C:\Users\Arsal Zubair\.claude\projects\Z--Claude-TerryClone\memory\`), `research/main190/proposal_x15/` (code, JSON,
previews) and `docs/main190_x15_region_proposal*.md`. Items marked **(uncertain)** need checking.

---

## 1. Status in one paragraph

This is **a proposal only**. Nothing has been written to `research/main190/hex/map.hex`, the assembly kit
(`assembly_kit_190E`) or any pack. The base map is the stock 190 Expanded map (892x702), upscaled x1.5 to
**1338x1053** with CAIME's `map-upscaler` branch (headless, `output/caime_upscaler`). After that come
`trade_rebuild.py`, the korea_fix chain and `town_fix.py` (city bars: stock impassable rings restored, 51 inland
towns moved 3+ hexes clear of their river, 19 ports given sea-side impassable). This map is built as its own map,
`3k_190e_expanded_map`, used by campaign `3k_main_campaign_map`. Extents: playable 892.65 x 812.49, campaign_maps
894 x 813, camera bounds inset 20.

Build history and in-game status:
- **First in-game test:** the stale-lf bug (see pitfalls). It was fixed in the 14:09 rebuild.
- **City-bar fix:** three rounds. The pack and startpos were rebuilt at 15:30 after round 3. The latest pack backup is
  `output/backups/main190_upscale_townfix_20261001_1541.pack`.
- **In game:** the city-bar fix is **not yet confirmed**, according to memory.
- **Pack name (uncertain):** the earlier rounds used `data/!!190_expanded_region_test_main190.pack`. Memory only says
  the x1.5 pack is "a fresh copy of the stock region test pack".

On top of this base, the work so far has produced three proposals:
- the region proposal: 67 new regions;
- the Hexi corridor and Xiping mockup;
- the steppe (northern tribes) mockup.

The carve has not started.

---

## 2. User decisions so far (all 2026-10-01)

| # | Decision | Where it lives |
|---|---|---|
| 1 | **Important regions only.** Core plus fill at 30 walking steps. Final count: **67 new regions** (54 new county towns + 13 new commandery capitals; core 26 / fill 41). 45 are north of the Yangtze, 22 south. 99 provinces, 41 of them new. | `select_x15.py` (FILL=30), `proposal_x15_final.json` counts |
| 2 | **Guandu** is a user-forced town: hex (695,737), Henan, `ironic_central_henan_resource_1`, importance high. | `plan_x15.py` FORCE |
| 3 | **Spacing:** at least **20** walking steps north of the Yangtze and **26** south, judged by the commandery's seat. The user wants more regions in the north. | plan GAP_N/GAP_S; proposal gap_n 20 / gap_s 26 |
| 4 | **Province = Han c.190 commandery.** Post-190 splits merge back into their Han parent. The AD 262 maps are a guide only. | `han190.py`, `commandery_hex.py` |
| 5 | The **`ironic_south_`** prefix is approved for southern regions (rule 4). | region-rules memory, rules_check |
| 6 | **Unnamed fills are optional.** The 105 unnamed towns are not proposed. | select_x15 |
| 7 | **Towns outside Kongming coverage are dropped.** The border land stays locked in the base proposal. | x15-region-proposal memory |
| 8 | The **4 existing 190E pairs under 20 steps are left alone**: Gu Pass–Jiexiu 16, Hulao Pass–Luoyang 19, Anya-guk–Guya-guk 18, Wirye-seong–Michuhol 18. Original regions are never removed; moving one is allowed if needed. | `spacing_check_final.json` |
| 9 | The duplicate Dai capital "Gaoliu" was dropped, because 190E already has it. Prop blocks are part of the site check. | memory |
| 10 | **Hexi corridor:** a **west pad of 140 columns** (grid 1478x1053) at 2.6 km/hex, against ~2.0 in the core (the user's "west pad, ~1.3x"). It is anchored on Guzang and shaped from Zhou's Liangzhou polygons. Dunhuang, Jiuquan, Lude, Xihai and Rile are moved; Yuanquan is a fill town. | `hexi_x15.py`, `hexi_x15.json` |
| 11 | **Xiping reworked from the DEM** (still one province). Xidu goes to Xining (311,793), Nan'an to the Gonghe basin (270,780) and Huandao to Guide (299,770). Playable land is below 3450 m; Qinghai Lake is a lake. | `hexi_x15.py` XIPING |
| 12 | **Steppe:** all four groups. They are the Southern Xiongnu, the Wuhuan in 3 bands (Liaoxi, Shanggu, Youbeiping), and the Xianbei: Budugen (Kuitou line), Kebineng, Tuoba and the eastern Suli. Terrain is opened from the DEM "like Xiping", the steppe is filled to 30 steps, and start owners are proposed. | `steppe_x15.py`, `steppe_x15.json` |

Proposed steppe start owners (`steppe_x15.json` owners):

| Group(s) | Owner |
|---|---|
| xiongnu | `ironic_faction_xiongnu_tribes` |
| budugen | `ironic_faction_xianbei_kuitou` |
| tuoba | `ironic_faction_xianbei_tuoba` |
| wuhuan_liaoxi, wuhuan_shanggu, wuhuan_youbeiping | `ironic_faction_wuhuan_tribes` |
| kebineng, suli | **no 190E faction**: a new faction or rebels (open question) |

---

## 3. The user's 11 region rules and their status

The rules are copied from memory `region-rules.md`. The status column comes from `rules_check_final.json`, which
covers the 67-region proposal only. The Hexi and steppe mockups have **not** been run through `check_rules.py`.

| # | Rule (user) | Status |
|---|---|---|
| 1 | **20 walking steps:** new towns at least 20 steps from every other town (26 south of the Yangtze for this proposal). | **PASS**: 0 new pairs under 20; 4 existing pairs left alone |
| 2 | **Capital and resources connected** by land, unless one of them is an island. | **PASS** |
| 3 | **Unique names:** no name may already exist in game. On a clash, rename the OLD region. | **PASS**: no clashes or duplicates. "Yiyang (Hongnong)" carries a name note |
| 4 | **Prefixes:** `ironic_hexi_` / `ironic_nomad_` / `ironic_central_` (+ `ironic_south_` approved), with `_capital` / `_resource_N`. | **PASS** |
| 5 | **Natural borders:** follow terrain, end on rivers, no straight edges. | **PENDING (carve)**: the previews use a walking-Voronoi estimate; the carve uses carve6's Dijkstra cost field |
| 6 | **Importance** set for every new region. | **PASS** in the data (high 14 / medium 12 / low 41). *Where the game stores importance is unknown* (Q1) |
| 7 | **Gate passes** keep the vanilla size. | **PASS**: 9 passes untouched; keep their size at carve time |
| 8 | **Trees:** none in or near settlements, none along roads. | **PENDING (carve)**: `tree_clear.py` |
| 9 | **Roads:** every settlement linked by road. | **PASS**: 67/67 routed, 447 new road hexes. The network as a whole is checked by CAIME at carve time |
| 10 | **Clear sites:** no towns inside props or mountains; check for nearby prop or impassable blocks. | **PASS**: blocked share under 20% within ~4 hexes |
| 11 | **Zhou maps are the authority** (`docs/reference/provinces`). | **PASS**: the Kongming maps are the same Zhou maps at higher resolution |

Importance tiers (from `select_x15.py`):
- **high:** new commandery capital, or user-forced (Guandu);
- **medium:** core, i.e. a commandery seat on the AD 262 map;
- **low:** fill.

---

## 4. Method (short)

1. **Sources.** The Zhou Dadudu AD 262 maps from kongming.net, saved in `docs/reference/kongming/`. The *Simple* map
   (9921x7016, flat fills) gives the polygons; the *Terrain* map (16535x12992) gives the rivers. The user's zhou maps
   in `docs/reference/provinces/` are the authority. CHGIS v5 supplies 943 county points valid in 190; its prefecture
   polygons are unusable for borders.
2. **Georeference.** `km_dots` finds the seat dots. `km_georef` fits an affine from 4 seed seats, then an iterative
   polynomial fit against CHGIS seats valid in 262. The proposal doc reports 43 seats with a median 3 km residual.
   The Terrain map is registered onto the Simple map by landmass bounding box plus seat-dot ICP.
3. **Commandery polygons.** `km_polys` flood-fills 155 pieces. `commandery_hex` assigns each piece to the Han
   commandery whose seat it holds. Seat-less post-190 pieces join their longest-border neighbour, plus 27 explicit
   parentage overrides. Shang, Wuyuan, Yunzhong, Dingxiang and Shuofang are absent from the AD 262 map.
4. **Membership by identity, not position.** A town's commandery is the Kongming polygon at its *real* seat lon/lat
   (`km_identity`). 190E towns sit a median 28 hexes from their georeferenced seats, and the offset is town-specific:
   leave-one-out shows no predictive field. Towns with no reliable seat, or a seat more than 250 km off, keep their
   190E province.
5. **Placement warp.** `geo_x15` is a fold-free Delaunay piecewise-affine map anchored on 162 existing towns. 19
   towns that 190E reorders were dropped because they flip triangles. Exact RBF/TPS fits folded the map or flew off
   its edges. **Accuracy is about ±20 hexes between anchors**, so use the warp for topology, not exact placement.
6. **Site rules** (carve6):
   - plain land; no mountain blend, impassable hex, pass, town or prop block;
   - blocked share under 20% within ~4 hexes;
   - the 190E town footprint must be off rivers;
   - CAIME's sprawl rule.
7. **Selection.**
   - `plan_x15` fills every gap: missing commandery seats first, then farthest-point first, preferring Han county seats.
   - `select_x15` keeps core plus greedy fill while a gap of 30 or more steps remains.
8. **Hexi and Xiping.**
   - Local equirectangular projection anchored on Guzang, 2.6 km/hex, west pad 140.
   - Corridor: Zhou's Liangzhou polygons; a 32-hex strip north of a 7-hex Qilian impassable wall; the Juyan spur
     (12 hexes); desert to the north; lakes from `research_r6/hexi_lakes.json`.
   - Xiping: Copernicus DEM. Valleys and basins below 3450 m are playable (the threshold drops south of 35.6N), with a
     mountain ring of 10 hexes or less.
9. **Steppe.**
   - Placement: `geo_x15` town-anchored mapping, plus **60 rows of north pad** (grid 1478x1113).
   - Terrain: Copernicus GLO-90. Steppe means relief under 300 m and elevation under 2100 m, inside the bounds
     106–124.8E, 38.2–44.8N. The adjacent ranges become impassable. Only non-playable land is opened.
   - Towns: historical sites first, then a farthest-gap fill to 30 steps, named after abandoned Han frontier counties
     where possible.

---

## 5. How to regenerate

Work in `Z:\Claude\TerryClone\research\main190\proposal_x15\`. The scripts import from `research/main190`
(`hexgrid`, `regions_carve`, `regions_carve6`, `rubber`, `warp`) and read `hex/map.hex` read-only.

| Step | Command | Writes |
|---|---|---|
| 1 | `python km_dots.py` | km_dots.json |
| 2 | `python km_georef.py` | km_georef.json |
| 3 | `python km_polys.py` | km_polys.npy / .json, km_polys_preview.png |
| 4 | `python han190.py` | han190.json |
| 5 | `python commandery_hex.py` | km_han.npy, cmd_hex.npy, cmd_keys.json, cmd_pieces.json |
| 6 | `python km_rivers.py` | km_river_hex.npy, km_river_ll.npz, km_rivers_meta.json |
| 7 | `python plan_x15.py` (**~10 min**) | plan_x15.json (all candidates) |
| 7b | `UNLOCK=1 python plan_x15.py` (optional) | plan_x15_unlock.json: padding opened in 11 under-covered commanderies, in memory only |
| 8 | `python select_x15.py` | plan_x15_final.json |
| 9 | `SUFFIX=_final python finalize_x15.py` | proposal_x15_final.json, region_est_final.npy, road_prop_final.npy, river_off.npy |
| 10 | `SUFFIX=_final python check_spacing.py` | spacing_check_final.json |
| 11 | `python check_rules.py` (reads the `_final` files, no env needed) | rules_check_final.json |
| 12 | `SUFFIX=_final python render_x15.py [sheet ...]` | previews/x15_final_*.png |
| 13 | `python hexi_x15.py` | hexi_x15.json, previews/hexi_x15_before/after.png |
| 14 | `SUFFIX=_final python gen_doc.py` | docs/main190_x15_region_proposal.md. Reads rules_check_final + hexi_x15.json, so run it after steps 11 and 13 |
| 15 | `python steppe_x15.py` | steppe_x15.json, previews/steppe_x15_after.png. Reads proposal_x15_final.json and imports hexi_x15 |
| 16 | `python full_x15.py` | previews/x15_full_map.png / _large.png |

Notes:
- **Runtimes:** only step 7's (~10 min) is recorded. The rest were not timed.
- **All-candidates run:** the same steps with no SUFFIX write `proposal_x15.json`, `spacing_check.json`, the
  `x15_*.png` previews and `docs/main190_x15_region_proposal_full.md`.
- **Inputs outside this folder:**
  - `research_r6/inventory.csv` (CHGIS seats of the 190E towns), `research_r6/name_registry.json` and
    `research_r6/chgis/`;
  - `research_r6/hexi_lakes.json`;
  - the DEM tiles in `research/main190/dem` or `research_r6/north/dem`.
- **Out-of-date outputs:**
  - `full_x15.py` does not draw the steppe yet; it shows the proposal plus Hexi only.
  - `steppe_x15.json` and `hexi_x15.json` (both 16:59) are newer than the generated doc (16:17). The doc's Hexi
    section has old numbers, e.g. corridor 20029 / Qilian 2117 / lakes 670, against the JSON's 19641 / 7921 / 1521,
    and it says "Qinghai unchanged" when Xiping has since been moved. Re-run steps 13–14 before you trust the doc's
    Hexi section. steppe_x15 may still be mid-revision.

---

## 6. Open questions for the user

1. **Where is region "importance" stored?** It wasn't found in the 3K db schema, the AK db XMLs or the decompiled
   CAIME source. Rule 6 can't be applied to game data until the user says which table, column or tool sets it.
2. **Southern prefix.** `ironic_south_` was approved (memory region-rules, rules_check). Confirm that it is final
   and that `ironic_central_` is not wanted for the 22 southern regions. The memory notes once called it
   "unconfirmed", so this is a cheap re-check.
3. **The two Yiyangs.** 益阳 in Changsha (`ironic_south_changsha_resource_2`) is currently named plain "Yiyang". 宜阳
   in Hongnong (`ironic_central_hongnong_resource_1`) got the label "Yiyang (Hongnong)" to avoid the pinyin clash.
   Ask for the final display names, and whether the Changsha one should carry a qualifier.
4. **Xiping misnomers.** The 190E regions "Nan'an" and "Huandao" are now at Gonghe and Guide, but the real places of
   those names are in Longxi. Keep the names (currently flagged) or rename? Rule 3: on a clash, rename the OLD region.
5. **Steppe factions.** Kebineng and the eastern Suli have no 190E faction. Should they be a new faction (or
   factions), rebels or unowned? Should the 3 Wuhuan bands all go to `ironic_faction_wuhuan_tribes`?
6. **Steppe fills.** 14 named steppe towns (8 capitals + 6 sites) and 67 **unnamed** optional fills, all keyed
   `ironic_nomad_<group>_resource_N`. By the "unnamed fills optional" rule they would be dropped unless the user
   names them. Confirm.
7. **Hexi reconciliation.** The final proposal adds Yumen (`ironic_hexi_jiuquan_resource_1`). The Hexi mockup has
   Yuanquan as its only fill and no Yumen. Decide which layout wins once the corridor is adopted. The Hexi and steppe
   towns also still need a `check_rules.py` pass, including name clashes, e.g. steppe "Yunzhong" and "Ning" against
   existing names.
8. **Rivers.** 36 major Kongming river runs lie more than 6 hexes from any game river (the largest: (344,745) 443
   hexes, max 30; (600,744) 326 hexes; (250,630) 308 hexes). Most are probably warp noise. Ask which, if any, to
   re-route. The user's rule: propose fixes only where the course is clearly off.
9. **Unlock scenario.** `plan_x15_unlock.json` opens padding in 11 commanderies (yongchang, qianwei_sg, guanghan_sg,
   shu, shu_sg, dunhuang, juyan, jiuzhen, rinan, yuyang, shanggu). The user chose "border land stays locked" for the
   base proposal, but later allowed the west and north pads. Should the south-west padding (Yongchang, Jiuzhen,
   Rinan) stay locked?

---

## 7. Next steps to actually build it (in order)

**Rule 0: back up everything before every overwrite. The user insists.** Use `output/backups/`, verify file for file
and check locks with whoLocks.ps1. The machine is shared with other sessions that use `assembly_kit_190E`, BOB and
the game: use `Z:\Claude\Headless\HOLD` plus messages. 3K TWeak locks Movie packs.

1. **Get answers to section 6**, at least Q1, Q4, Q5, Q6 and Q7.
2. **Grid change (west pad 140, north pad ~60 rows → 1478x1113).** This is a map-size change, so the
   **map-size → extents rule** applies:
   - pad `map.hex` (west columns; north rows at the top, since row 0 is south);
   - update `campaign_map_playable_areas` (pack row + kit db + EmpireDesignData), `campaign_maps` (kit only) and
     `campaign_camera_map_bounds`, in the kit AND the pack, **before any BOB step**;
   - convention: playable = raster world size; campaign_maps = ceil((w-1)·0.668), ceil((h-1)·0.772); for 1478x1113
     that gives 987 x 859 (**uncertain**: recompute from the final grid); camera = playable inset 20;
   - tools: `newmap_install.py` (kit), then `newmap_packdb.py` (pack TSVs), then rpfm add of the playable / camera /
     campaigns tables.
3. **Terrain for the new land** (Hexi, Xiping, steppe, the pads) from the DEM:
   - heights, blend/class, trees and climate, in the order dem_fill → coast_carve → class_fill+korea_fix;
   - class_fill and korea_fix always run together, in that order;
   - coast_carve reads `terrain/_pre_carve`, never `terrain/`;
   - flat sea 9594; sea rasters scaled by 44217/65535;
   - add the Qilian wall and Qinghai Lake;
   - `warp.py` MODE `scale1.5` (`ScaleWarp`, `is_scale()` disables the old Liang DEM zone and north_cull) is the
     current base mapping. The pad has to be added on top of it **(uncertain: no script does this yet)**;
   - scripts read the 190E originals from `output/backups/main190_originals_20260929_130639`, never re-warped kit
     copies.
4. **Carve the regions** in the `regions_carve6.py` style:
   - input `hex/map_korea.hex`; output `hex/map.hex` + `regions_new.json`; run `--dry-run` first;
   - natural borders: Dijkstra cost field, rivers are expensive to cross;
   - stamp footprints from the 190E town templates;
   - use the `sprawl_ok` CAIME rule;
   - roads: each new town links to the network; road hexes are never made impassable;
   - `fix_bridge_banks`: CAIME needs exactly 2 banks per bridge; check with `pftest/bridge_groups.py`;
   - gate passes never carved;
   - recompute the map.hex crc32 trailer;
   - the clean-up must not merge the islands of existing regions;
   - candidates come from `proposal_x15_final.json` + `hexi_x15.json` + `steppe_x15.json`.
5. **After the carve:**
   1. `tree_clear.py` (rule 8);
   2. re-check rules 1–11;
   3. re-check `town_fix` city-bar contact for any moved towns;
   4. `caime_tilemap.py` for the tile map.
6. **DB:**
   - `regions_db.py`: it rebuilds `db_out/` from scratch, unowned in all 5 campaigns, provinces
     `3k_ironic_province_<key>`. The pack junctions `region_to_province_junctions data__` **must** include the new
     regions, or the startpos build crashes at "About to create WORLD".
   - Add the start owners for the steppe if the user approves.
   - Then `install_ak.py` (`--db-only` if the terrain is unchanged), then `junction_fix.py` (install_ak keeps or drops
     the wrong rows for regions that move province), then `newmap_install.py` (**after** install_ak), then
     `newmap_packdb.py`.
   - `startpos_shift.py`: shift every startpos x by **+140**; y stays unchanged for the north pad. The x1.5 base
     already shifts through CAIME's town pins into `db_scale/`, so add the pad on top. Tell the user the numbers used.
7. **CAIME:**
   - `caime_prefs.py set` points `Three_Kingdoms_AssKitPath` at `assembly_kit_190E` (otherwise every region shows as
     "missing"); `caime_prefs.py restore` afterwards. Never sed the path.
   - Run validate (it can hang after writing the log; kill it once `tool.log` stops growing), then map-data,
     pathfinding, trade (use `trade_rebuild.py` if trade hangs), lookup, and borders (GUI only; it opens on the
     second monitor; can be delegated via uiclick.ps1).
   - The CLI detaches, so wait for CAIME.exe to exit. Check output timestamps, because stale pathfinding.ppd and
     lookup files have shipped before.
8. **lf maps:** `dotnet run --project src/TerryClone.Cli -- build-campaign --steps rasters` (+`camera_heightmap`).
   Copy `lf_height_map.*` / `lf_sea_height_map.*` into the **kit's** `working_data/terrain/campaigns/<map>/` before
   Tilemap.
9. **BOB** (one action at a time; `BOB_AK` / `run_bob.py`; close any leftover BOB window):
   1. Tilemap, plus hole rounds (`tile_holes.py`, `tile_repair.py`);
   2. set the pack to **Movie** with the new playable row, otherwise Global Mesh isn't listed or uses a stale width;
   3. Global Mesh x2;
   4. "Terry file" in **GUI mode** (the .terry name has a trailing space). This step rebuilds models, height_patches
      and global_props, which Global Mesh does not;
   5. "Convert lookup texture";
   6. `extras_main.py` (painted maps, lookup renames, camera heightmap, trees).
10. **Pack:** a copy of the region test pack. Only that copy, `!!190_expanded_with_charactersIntrex.pack` and
    `mtu_startpos_ironic.pack` are Movie; everything else stays Mod. Wait a moment after BOB exits before the first
    rpfm add, which has failed twice right after BOB.
11. **Startpos:**
    - rpfm_server.exe (**port 45127**), `3k_main_campaign_map` only;
    - historical with `process_hlp_spd=true`, then romance with `false`, then `build_starpos_post` and
      `save_packfile`;
    - set the packs back to Mod afterwards;
    - watch for loose `data/campaigns/<camp>/startpos_*.esf` files overriding the pack.
12. **In-game check:**
    - `lua_scripts/map_probe_190e.lua` and `citybar_probe_190e.lua`;
    - look at the city bars, the river water, tile heights and the new borders.

Known pitfalls that apply (from memory `main190-map.md`):

| Pitfall | Avoid it by |
|---|---|
| **Stale lf:** BOB Tilemap bakes tile heights from the kit's lf_* files. Old ones gave raised or sunk tiles, Bohai beaches in the sea and a water strip through Xiapi. | Copy fresh lf_* into the kit before Tilemap. |
| **Stale playable row:** BOB reads the world width from the **Movie pack's** playable row. A stale row built 420 meshes instead of 339 and offset everything. | Put the pack's playable / camera / campaigns tables in before Global Mesh. |
| **Extents changed after a build.** | Redo the whole chain from BOB Tilemap: CAIME → Tilemap+holes → GM x2 → Terry file → lookup → camera heightmap → pack → startpos. |
| **CAIME pathfinding crash** (HLCIGenerator index out of range) from a 3-bank bridge. | Run `fix_bridge_banks`. |
| **korea_fix re-routes roads over heights** after a height change. | Restore the hex files and run only `fix_rasters`. coast_carve's lake step reads map_korea.hex, so rerun from coast_carve after a grid change. |
| **Overriding pack crashes the startpos build** (`bad_alloc` in load_db_table). | Never use a separate overriding pack; merge everything into the copy. |
| **Upscaler kept towns unscaled but redrew rivers**, so river contact (city bars) breaks. | Re-run town_fix logic for any town the carve moves; CAIME validate is the referee. |
| **bob_mcp GUI popup opens at the mouse cursor.** | server.py parks the cursor; close leftover BOB windows. |

---

## 8. File index

| Path | What it is |
|---|---|
| `docs/main190_x15_region_proposal.md` | Final proposal (67 regions, provinces by zhou, rules table, rivers). Hexi section stale |
| `docs/main190_x15_region_proposal_full.md` | All-candidates version (282 new, unlock scenario, decisions-needed list) |
| `docs/main190_north_cull_proposal.md`, `docs/north_regions_sources.md` | Round-6 steppe / north analysis and seat sources, reused for the steppe |
| `docs/reference/kongming/` | Zhou Dadudu AD 262 maps (Simple, Terrain, per-zhou sheets) |
| `docs/reference/provinces/` | The user's zhou maps (ji, jing_wei, qing_xu, sili, yan_yu_yang): the authority |
| `proposal_x15/km_dots.py` | Seat dots on the Simple map |
| `proposal_x15/km_georef.py`, `km_georef_lib.py` | Simple-map pixel ↔ lon/lat polynomial |
| `proposal_x15/km_polys.py` | Flat-fill commandery pieces |
| `proposal_x15/han190.py` (+ `.json`) | Han c.190 commanderies with seats and the south flag |
| `proposal_x15/commandery_hex.py` | Han commandery per hex (`cmd_hex.npy`) and the identity raster (`km_han.npy`) |
| `proposal_x15/km_identity.py` | Real lon/lat → Han commandery (no warp) |
| `proposal_x15/geo_x15.py` | lon/lat → x1.5 hex, town-anchored fold-free warp (±20 hexes) |
| `proposal_x15/km_rivers.py` | Kongming rivers → hex |
| `proposal_x15/plan_x15.py` | All-gap town plan (FORCE Guandu, UNLOCK scenario); ~10 min |
| `proposal_x15/select_x15.py` | Core + fill at 30, importance tiers, name de-dup |
| `proposal_x15/finalize_x15.py` | Region estimate, provinces, keys, roads, river check |
| `proposal_x15/check_spacing.py`, `check_rules.py` | Independent BFS spacing; 11-rule check |
| `proposal_x15/render_x15.py`, `gen_doc.py` | Preview sheets; proposal markdown |
| `proposal_x15/hexi_x15.py` | Hexi corridor + Xiping DEM mockup (west pad 140) |
| `proposal_x15/steppe_x15.py` | Steppe groups mockup (north pad 60) |
| `proposal_x15/full_x15.py` | Whole proposed map on the padded grid (no steppe yet) |
| `proposal_x15/proposal_x15_final.json` | Final towns (307), provinces (99), counts, river runs |
| `proposal_x15/rules_check_final.json`, `spacing_check_final.json` | Rule and spacing results |
| `proposal_x15/hexi_x15.json`, `steppe_x15.json` | Mockup outputs (moved towns, fills, owners, grid) |
| `proposal_x15/plan_x15.json`, `plan_x15_unlock.json` | All-candidates and unlock-scenario plans |
| `proposal_x15/previews/` | `x15_final_*.png` (per zhou + overview), `hexi_x15_before/after.png`, `steppe_x15_after.png`, `x15_full_map*.png`, `xiping_crop.png`, `west_crop.png` |
| `research/main190/warp.py` | Map warps; MODE `scale1.5` = ScaleWarp (current base) |
| `research/main190/regions_carve6.py` | Carve template (spacing, natural borders, roads, bridge banks) |
| `research/main190/regions_db.py` | Pack TSVs (db_out/) + staged AK XMLs (ak_db/) for new regions |
| `research/main190/install_ak.py`, `junction_fix.py` | Kit install (backup first); fix junctions for moved regions |
| `research/main190/newmap_install.py`, `newmap_packdb.py` | `3k_190e_expanded_map` kit rows / pack TSVs (extents) |
| `research/main190/startpos_shift.py` | Startpos character coordinates → new grid |
| `research/main190/town_fix.py` | City-bar fixes (impassable rings, move towns clear of rivers) |
| `research/main190/caime_tilemap.py` | Tile map from the CAIME baseline export + 190E areas / roads + repair |
| `tiles-*` CLI / terry MCP tile tools / app tile window | Validated hand edits of tile_map.png, replayable after a rebuild ([campaign_tile_editor.md](campaign_tile_editor.md)) |
| `research/main190/tree_clear.py`, `extras_main.py` | No trees near towns or roads; per-map painted / lookup / camera files |
| `research/main190/caime_prefs.py`, `trade_rebuild.py` | Switch CAIME's kit path; redraw trade links |
| `research/main190/hex/map.hex` (+ `map_pre_townfix.hex`) | Current x1.5 map (read-only for the proposal) |
| `output/backups/main190_upscale_townfix_20261001_1541.pack` | Latest x1.5 pack backup |
| `output/backups/main190_originals_20260929_130639` | 190E originals (source for all re-warps) |
| Memory: `x15-region-proposal.md`, `region-rules.md`, `main190-map.md`, `map-size-extents-rule.md`, `startpos-coordinate-shift.md`, `startpos-190e-packs.md`, `campaign-map-build-process.md` | The user's standing rules and history |
