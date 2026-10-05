# Survey: Atlas3K's native campaign build on Total War: WARHAMMER III

How much of the 3K native build (`docs/native_campaign_build.md`, `docs/hlp_spd.md`) carries over to WH3. This is a
read-only survey from 2026-10-05. No Atlas3K code was changed.

**Inputs**
- **WH3 install:** `D:\SteamLibrary\steamapps\common\Total War WARHAMMER III`. Kit binaries are dated 2026-09-30; the build path in BOB is `T:\branches\warhammer3\patch_9_0`.
- **Older WH3 kit:** `F:\...\Total War WARHAMMER III\assembly_kit_old`, a 2023 kit. It holds CA's sample campaign map `cr_albion_map_1`, with raw sources and compiled output.
- **3K references:** the kit in `C:\...\Total War THREE KINGDOMS\assembly_kit`, and `Vanilla\Map` (3k_dlc07).
- **Extracted WH3 files:** in `output/survey_wh3/wh3`, about 520 MB after pruning. They cover Immortal Empires (`wh3_main_combi_map_1`): the root terrain files, 1 devastation piece, 2 rivers, the campaign_maps files (no display textures), the campaign tile database and 3 sample tiles.
- **Probes:** in `output/survey_wh3/probes`. `Probe/` is a C# console app against the built `Atlas3K.Formats.dll`; `probe_out.txt` is its output. The Python scripts cover tile lists, DDS headers, compressed_map, exports and string diffs.

## Summary

The WH3 campaign terrain pipeline is not 3K's pipeline with new version numbers. WH3 dropped the tile-based global
meshes and the river height patches. In their place, the campaign is rendered from full-resolution rasters:
- `full_height_map.dds` (BC6H)
- `full_logic_map.compressed_map`
- `shroud_heights.dds`
- colour overlay, corruption, snow and patch masks

WH3 also adds devastation "pieces" and culture-masked props. The kit's BOB has no "Global Mesh" action. It has new ones
instead: *Campaign Heightmap*, *Campaign Shroud Heights*, *Campaign Global Blendmap*, *Color Overlay*, *Corruption
Mask*, *Snow Mask*, *Patch Visibility Mask*, *Event Area Mask*, *Global Tilemap* and *Devastation pieces*.

Much does carry over:
- the hex grid geometry, tree placement and RNG
- the FASTBIN0 / compressed_map container (with a small writer quirk)
- the lookup textures
- the pack-level `global_props.bin` container
- the RMV2 v8 river container
- `pathfinding.ppd`
- the PNG writer
- most named BOB functions: the shared Warscape DLLs keep the same exports

As a proof, WH3's `full_logic_map.compressed_map` for `cr_albion_map_1` was rebuilt **byte-identical** (1,191,010
bytes) from the raw height TIF. It took Atlas3K's compressed_map encoder plus three small rule changes (below).

**The blocker for vanilla parity work:** the current WH3 kit ships **no campaign terrain sources**. There is no
`raw_data\terrain\campaigns` and no `.terry` for any vanilla map, only `map.hex` and the lookup BMPs for
`wh3_main_chaos_map_4`, `wh3_main_combi_map_7` and `wh3_main_prologue_map`. The only full source set found is CA's
sample `cr_albion_map_1` in the 2023 kit. It is small: 200 × 200 hexes, 2 prop layers and no rivers.

## 1. Tools: kit DLLs

| 3K kit | WH3 kit | Notes |
|---|---|---|
| `warscape.modder.x64.dll` | same name | 8.1 → 11.3 MB; 1,235 → 3,030 exports, 1,071 identical mangled names. TILE_DATABASE exports 302 / 316, 292 common. |
| `bob_terrain`, `bob_campaign`, `bob_tile`, `bob_vegetation`, `bob_warscapeshared`, `bob_texture` | same names | Campaign action set changed (see Summary). |
| `qttoolutility`, `empireutility`, `calibs`, `utilitydll` | same names | utilitydll: 1,759 of 2,155 exports identical; SEGMENTED_SPLINE_3 27 / 28 common. |
| `tooldatabuilder.modder.x64.dll` | **renamed** `tooldatabuilderdll.modder.x64.dll` | 214 of 255 exports identical |
| `empirecampaign.modder.x64.dll` (hlp/spd) | **missing** | The AI pathfinding generator is in `Warhammer3.exe`: `CAI_HIGH_LEVEL_PATHFINDER`, `REFERENCE_POINTS`, `process_campaign_ai_map_data`, `full_logic_map`. `bob_campaign` keeps `process_campaign_ai_map_data`. |
| `bob.retail.x64.exe` | `bob.modder.x64.exe` | The Frida harness's process name changes. |
| `empirebattle`, `serialisation`, `imgui`, `qttoolutilitylite`, `utilitydlllivelink`, `tweak_twad`, `tweak_varianteditor` | missing | not used by the campaign port |
| — | `toolutility`, `toolutilitylegacy`, `toolutilityqt`, `toolutilityinfrastructureshared`, `contextsystem`, `events`, python37 / pyside2 | WH3 only |

**Functions and classes the 3K port relied on** (string, RTTI and export hits; `output/survey_wh3/probes/keyfuncs.py`):

| Present in WH3 | Missing in WH3 |
|---|---|
| `TILE_DATABASE` (sort, link_target_count), `TILE_MAP::calculate_flow`, `TLT_EQUALS` | `process_terrain_global_mesh`, the "Global Mesh" action, `land_mesh_`, `height_patch_collection` |
| `TERRAIN_RENDER_SETUP::get_height_worker`, `TERRAIN_QUAD_TREE`, `intersect_non_empty_nodes_gproj` (warscape only) | `get_high_frequency_height_new` (the 3K tile-hf height used for trees) |
| `WARSCAPE::rasterise_max_heights`, `COMPRESSED_MAP::compress` | `HeightDataProvider`, `ws_tile_instance_indices_at` (the tree height provider) |
| `generate_camera_height_map` (tooldatabuilderdll) | `BMD_META_TAG_COLLECTION` (the 3K BMD preamble checksum) |
| `CampaignTreeGenerator`, `generate_campaign_tree_list_for`, `CAMPAIGN_TREE_LIST`, `ACTION_PROCESS_CAMPAIGN_TREES` | |
| `SEGMENTED_SPLINE_3::optimise_spline`, `VERTEX_LIST_CLEANER`, `MODEL_PROCESSOR`, `MESH_SPLITTER`, `TRIANGLE_MERGER` | |
| `CA::murmur_hash` (217 bytes in both, 0.96 byte similarity), `WARSCAPE::contains` (identical bytes), `QTU::ECTransform::update_transform` | |

**Signature changes that matter:**
- `EMPIREUTILITY::CAMPAIGN_TREE_LIST::add_tree`:
  - 3K: `(String, VECTOR_3, bool, uchar, BITSET<16> seasons)`
  - WH3: `(String, VECTOR_3, bool, uchar, uchar)`
- The `QTU::CampaignTreeGenerator` constructor has lost its `TerrainSurface::Object` height-provider argument.

**Caveat on code similarity:** most exports are thin stubs, so comparing export bodies says little. The internal
`FUN_…` addresses in the 3K docs have to be found again with Ghidra in the WH3 DLLs. Ghidra was not run for this
survey.

## 2. Campaign map sources

| | 3K (`3k_dlc07_main_map`) | WH3 (`cr_albion_map_1`, the 2023 kit sample) |
|---|---|---|
| `.terry` | project v20, scene v35 | project v26, scene v41 |
| TerrainMaps | LowFrequencyHeight (8 px/hex, u16), LowFrequencyHeightSea (4 px/hex), BlendCampaign, CampaignTree (2 px/hex) | Height and HeightSea (8 px/hex, **float32** TIF), HeightShroud (4 px/hex, float), BlendCampaign (8-bit palette), ColorOverlay / ColorOverlaySea (RGBA), CampaignTree (2 px/hex), CorruptionMask, SnowMask (2 px/hex), PatchVisibilityMask (100 × 100) |
| tile_map.png / climate_map.png | 2 px/hex | 2 px/hex (400 × 401 for 200 × 200 hexes) |
| Layers | ECPropMesh, ECRiver(Spline), ECVFX, ECCompositeScene, lights, sounds, … | Same entity types; attribute sets differ (ECCampaignProperties `visible_in_shroud`, `culture_mask`; ECVisibilitySettingsCampaign; ECPropHeightPatch `for_camera_height_map_only`) |
| map.hex | version 19, 16 B/hex | **version 20**: same 16 B/hex records plus an extra table before the grid size and a trailing 1 bit/hex array (22.5 MB for Immortal Empires); 40 settlement "climates" |

**WH3 campaign maps in the packs** (`data_maps.pack`, `terrain_camp*.pack`, `tiles_campaign.pack`):

| Terrain (`terrain/campaigns/`) | campaign_maps variants |
|---|---|
| `wh3_main_combi_map_1` (Immortal Empires, 1440 × 970 hexes) | `wh3_main_combi_map_1..5`, `_7` |
| `wh3_main_combi_map_devastate_1` (devastation pieces only) | — |
| `wh3_main_chaos_map_1` (Realm of Chaos) | `wh3_main_chaos_map_1..4` |
| `wh3_main_prologue_map` | `wh3_main_prologue_map` |

In the current kit, `raw_data\EmpireDesignData\campaign_maps` has map.hex and lookup BMPs for `combi_map_7`,
`chaos_map_4` and `prologue_map` (prologue also has `trees.png`, `tree_database.xml` and `dynamic_resources*`).

## 3. Compiled files compared

All WH3 packs that matter are **zstd-compressed per entry**: terrain_camp 9,327 of 9,327 entries, data_maps 391 / 391,
tiles_campaign, db. Atlas3K's `PackFile` refuses compressed entries, so it cannot read any WH3 campaign file yet.

| File | 3K | WH3 | Atlas3K reader on WH3 |
|---|---|---|---|
| `tile_list.bin` | FASTBIN0 v1/1, 21-byte records, lo/hi normalised 0..1 | **v2/1**: same header and 21-byte records, plus 1 trailing byte (00); lo/hi in world units (−17..28); ints [7..10] = (−24, −24, W/4 + 2, H/4 − 3) vs 3K (−16, −15, W/4, H/4); a single climate `default`; no river tiles in IE | fails on the version check; small branch |
| `global_map\tile_list.bin` | full copy, flag cleared on base tiles | a **subset**: generic and sea records are dropped (38,873 of 274,216 kept) | same branch |
| `global_map\global_blend.dds` | 16-bit (blend index + climate byte) | **8-bit**: the blend TIF index with 255 → 0, not flipped (verified on albion) | new small writer |
| `global_map\texture_arrays.xml` | the same on every map | per map (54–65 KB) | copy / generate |
| `lf_height_map`, `lf_sea_height_map` (`.compressed_map`, `.dds`), `climate_map.cm` | yes | **not shipped** | n/a |
| `full_logic_map.compressed_map` | — | v3 TABLE_INDEXED, 8 px/hex, header (0, lo, 0, 0, hi, 0) | decodes; **rebuilt byte-identical on albion**: flipped float TIF, `trunc((h−lo)·(1/(hi−lo))·65535)` in float32, Atlas3K's tile-mode rule, and 3 zero bytes after every bit-packed tile |
| `full_height_map.dds` | — | DX10 **BC6H_SF16** (DXGI 96), 8 px/hex, 1 mip | new; game-valid needs a BC6H encoder; byte parity depends on CA's encoder (AMDCompress) |
| `shroud_heights.dds` | — | DX10 R32_FLOAT, 4 px/hex | **byte-equal** to the flipped HeightShroud TIF on albion |
| `lf_normal.dds`, `lf_sea_colour.dds`, `colour_overlay.dds`, `corruption_mask.dds`, `snow_mask.dds`, `tile_mask.dds`, `patch_mask.dds`, `terrain_visibility_mask.dds`, `event_area_mask.dds` | lf_normal only (unused) | DXT5 / BC1 / R8 / BC4 / L8 / R8_UINT rasters | new texture writers |
| `global_meshes\` | land/sea RMV2 + `.compressed_map` | **not shipped** | n/a |
| River models | `models/river_N`, material 68, 48-byte vertices, 5 vertices per sample | `models/river_<entity id hex>`, the same RMV2 v8 container (material 68 "River", 48-byte stride), a **2-vertex ribbon** (376 vertices, 374 triangles), `.wsmodel` → the map's sea water-plane material | `RigidModel` / `RigidModelV2` read it; the mesh generator needs a re-port |
| `height_patches\` | yes | **not shipped** | n/a |
| `global_props.bin` | container plus BMD bodies **v35** (enum-type preamble); buckets 16–31 | same container; bodies **v27** (no preamble, other section layout); bucket ids 0–367 (culture-mask bits above the season bits); separate `global_props_sound.bin`; devastation `pieces/event_xxxxxx/objects.bin` and `.culture` | container OK; `BmdBody` rejects every body (v27): re-port |
| `trees.campaign_tree_list` | v5: per tree x, y, z, flag, variant, season list | **v4**: x, y, z, flag, variant, 1 byte (always 0xFF); no seasons | rejected (v4); small branch |
| `camera_heightmap.png` | 2 px/hex, `height_scale` tEXt, 8192-byte IDAT chunks | **0.5 px/hex** on IE (720 × 486), same tEXt and chunking; albion's is a hand-made placeholder (100 × 100, no height_scale) | the PNG writer carries over |
| Lookup `.tga` / `.dds` / `_minimap.tga` | indexed TGA, R16_UNORM DDS | same formats | albion: tga + dds **byte-identical**; IE combi: 81 bytes differ (kit BMP vs shipped); elector_counts: dds identical, tga palette alpha 0 instead of 255; minimaps a few bytes off |
| `hlp_data.esf` | `CAI_TRANSITION_DATA` v0 | `CAI_HIGH_LEVEL_PATHFINDER` v1 holding `TRANSITION_DATA` (per-area `REGION_AREA_INDEX` records added), a 4 MB u32 array, a 1 MB byte array and `OTHER_CONSTANTS` | rejected; re-port |
| `spd_data.esf` | `CAI_SIMPLE_PATH_DIRECTORY` v0, 8 landmarks | v1 with `REFERENCE_POINTS` (8 points on albion, 52 on IE) and a different per-cell encoding; 98 MB on IE | rejected; re-port |
| `map_data.esf` | 25 record types | 27: adds `REGION_AREA_INDEX` and `REGION_AREA_INDEX_OVERRIDE`; `MASKED_REGIONS_DATA` laid out differently | `EsfTree` reads it; `MapDataRegions` fails ("covers 0 of 40000 hexes") |
| `pathfinding.ppd` | | | **reads unchanged** (1440 × 970, 200 × 200) |

## 4. Tile database

| | 3K | WH3 |
|---|---|---|
| Location | `terrain2.pack`, 544 tiles | `tiles_campaign.pack`, `_tile_database` plus 320 tiles |
| `_settings.bin` | render params v13 | render params **v12** of a different lineage (extra fields before the fog params), so the 3K parser stops at 0x86 |
| Tile `.bin` | v ≤ 7, variation ≤ 10 | 300 tiles at v6 with variation v11 (a `climate` texture set) fail the 3K parser; 20 parse (v5 / variation 8) |
| Tile sets | generic(_sea), sea_coast, mountains_*, blockout_cliff*, river*, roads_*, canal*, … | cliff_gen(_ends), generic, sea, sea_coast, roads, roads_light, roads_grey(_dark), river, river_start, river_mouth, river_crossing (IE uses no river tiles) |
| Tile contents | hf `.compressed_map`, bmd_data.bin, meshes | `hf_height_map.data` (**CHMF**; Atlas3K never ported this path), mesh / shadow_mesh / river_mesh RMV2 v7 with 3 LODs, normal.dds, blend0.dds |
| Climates | 4 (arid, cold, temperate, sub_tropical) | tile list climate `default` only; map climates are a map.hex concept (40 keys) |

The tile-matching code itself (calculate_flow, TLT_EQUALS, the DB sort) has the same names in WH3's warscape. Whether
the 3K rules (sort before links, MSVC sort, flow exceptions) still hold needs a parity run. Albion's `tile_list.bin`
(5,881 records) is a ready reference.

## 5. Verdict per step

| Step | WH3 verdict | What changes | Effort |
|---|---|---|---|
| `rasters` | **re-port (small)**; the 3K outputs don't exist in WH3 | Replace with *Campaign Heightmap*: `full_logic_map` (proven byte-identical) and `full_height_map.dds` (BC6H), *Campaign Shroud Heights* (identical) and lf_normal; float TIF input; no climate_map.cm | 3–5 days (game-valid); BC6H byte parity unknown |
| `tile_list` | **version branch (small) + tile DB branch (medium)** | v2 trailer, world-unit lo/hi, new int fields, WH3 tile DB / tile parsers, CHMF hf maps; verify matching against albion | 1–2 weeks to parity |
| `global_map` | **branch (small)** | 8-bit blend (255 → 0), subset tile list, per-map texture_arrays | 1–2 days |
| `global_mesh` | **not applicable** | WH3 ships no global meshes | 0 |
| `rivers` | **re-port (medium)** | 2-vertex ribbon, water-plane material, entity-id names, no height patches; the spline code is shared. No WH3 source map with rivers (albion has none) to check parity | 1–2 weeks (game-valid sooner) |
| `global_props` | **re-port (medium–large)** | BMD v27 bodies, culture-mask buckets, `global_props_sound.bin`, map.hex v20 region lookup, new ECCampaignProperties fields; devastation pieces only for event maps | 2–3 weeks to parity |
| `camera_heightmap` | **re-port (medium)** | Same grid/PNG code with a WH3 resolution scale; the scene is the logic heightmap plus prop patches, not global mesh + height patches (correlation 0.92 with max-pooled logic heights) | 1 week |
| `trees` | **branch (small–medium)** | v4 writer (no seasons, +1 byte), WH3 tree tables (ids/types/type_cultures/variants, no seasons). Height = full_logic_map sample (correlation 0.997), not TileHfHeight. Grid, jitter and one-tree-per-hex are identical (6,624 / 6,624 albion trees), and the 3K minstd jitter rule reproduced 1,765 of 2,000 sampled trees, the rest being draw-count differences | 2–4 days |
| `lookup` | **works as is** (tiny tweak) | Byte-identical on albion; palette alpha and minimap details differ on some IE lookups | ≤ 1 day |
| `hlp_spd` | **re-port (large)** | New hlp/spd record layouts, variable landmark count, extra arrays, map_data branch; the generator is in `Warhammer3.exe` (Ghidra on a 100+ MB exe); ppd unchanged | 3–5 weeks |
| new: masks / overlays | **new (small each)** | colour_overlay / lf_sea_colour (BC1), corruption (R8), snow (BC4), tile_mask, patch / terrain visibility (R8_UINT), event area; mostly direct TIF → DDS conversions | about 1 week together (game-valid); byte parity depends on CA's BCn encoder |
| new: devastation pieces | **new (medium)**, IE-style event maps only | per-event folders with BMD, tile and tree lists, and the rasters cut to the event area | 1–2 weeks, optional for custom maps |

## Game-specific assumptions in Atlas3K to generalise

| Area | Today (3K) | WH3 needs |
|---|---|---|
| Packs | uncompressed entries only | zstd entries (`u32 size` + zstd frame) |
| Install and kit | `Total War THREE KINGDOMS` Steam folder, `Three_Kingdoms` process (`BuildRunner.GameProcess`), `bob.retail` | game profile: folder, exe name, kit binaries, BOB exe name |
| Map sources | `raw_data\terrain\campaigns\<map>\*.terry` with lf u16 TIFs | float TIFs, the new TerrainMap types, `.terry` v26; regenerate the component schema (`terry-schema`) from the WH3 kit; vanilla WH3 maps have no sources (only albion) |
| Constants | `595.1 / 7136` pixel size (CameraHeightmapStep), `TileSize = 595.1 / 1784` (GlobalMeshStep), the 3K tree world | derive from map_data / playable areas (IE world 961.3 × 748.6, albion 200 × 232.68) |
| Names | `3k_main_reg_non_playable`, the `3k_` prefix in audits and battle regions, `3k_main_map` battle workspace, `3k_main_sea_lake`, 3K snow-mask file names | per-game tables |
| map.hex and CAIME | v19 reader; CAIME writes map.hex / map_data / ppd | v20 reader; no CAIME support for WH3 checked (CA's flow: `process_campaign_ai_map_data` through the game) |
| DB | campaign_tree_ids / variants / seasons TSVs, campaign_map_playable_areas / roads / variables | WH3 tree tables (types, type_cultures, no seasons); the kit's `raw_data\db` has `.xml` exports (playable areas, roads, variables) |
| Seasons | season buckets, tree seasons, 3D viewer seasons | WH3 uses culture masks instead (prop buckets, tree types) |

## Overall estimate

| Goal | Scope | Time |
|---|---|---|
| **Game-valid WH3 build** | logic/height/shroud rasters, BC6H/BCn masks, global_map, tile_list on a WH3 tile DB, trees, lookup, a simple camera heightmap, BMD v27 props with region lookup, ribbon rivers, zstd packs and the game-profile plumbing; hlp/spd still from CA's own flow | about 5–7 weeks |
| **BOB-parity level like 3K** | the above plus Ghidra and Frida rounds on the WH3 DLLs (`bob.modder.x64.exe`), tile-matching parity on albion, BMD v27 field parity, camera scene and river parity | about +4–6 weeks |
| **hlp/spd** | a new reverse-engineering target in `Warhammer3.exe` | about +3–5 weeks |

The practical limit is test data. Albion is the only WH3 map with sources and CA-built output. It has no rivers, few
props and no devastation, so parity on rivers and IE-scale props cannot be checked without making new BOB runs on WH3.
