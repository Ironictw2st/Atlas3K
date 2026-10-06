# Survey: Atlas3K's native campaign build on Total War: ATTILA

How much of the 3K native build (`docs/native_campaign_build.md`, `docs/hlp_spd.md`) carries over to Attila. This is a
read-only survey from 2026-10-05 that mirrors `docs/surveys/warhammer3.md`. No Atlas3K code was changed.

**Inputs**
- **Attila install:** `D:\SteamLibrary\steamapps\common\Total War Attila`. `Attila.exe` and `empire.retail.dll` are
  32-bit; the game build is 25370302. Packs are PFH4.
- **Attila kit (app 343660):** the installed depot (2.3 GB) has binaries dated 2020-01-17 (`s:\branches\attila\slavs`),
  the XML tile database and `raw_data\terrain\campaigns\bel_attila_map` (map.hex, trees.png, tree_database.xml,
  dynamic_resources). The Steam update was still pending when the survey ended: the manifest says StateFlags 1044 and
  BytesDownloaded 0 of 8.6 GB.
- **Staged kit files:** the staging folder `steamapps\downloading\343660` already holds about 55 GB with real content.
  It includes the **main_attila_map sources**: `main_attila_map.terry`, `lf_heights.tif`, `lf_sea_heights.tif`,
  `tile_map.png`, `climate_map.png`, `layout_map.png`, `normal.dds`, `lf_sea_colour(_small).tif`, `masks.xml`, the season
  masks and 1 snow mask TGA. These files were only read, in place.
- **3K references:** the kit at `C:\...\Total War THREE KINGDOMS\assembly_kit`, `Vanilla\Map` (3k_dlc07) and the WH3
  survey probes.
- **Extracted Attila files:** in `output/survey_attila/attila`, about 110 MB after pruning:
  - `terrain/campaigns/main_attila_map`: everything except the big lf DDS files, which were checked and then deleted;
  - `campaign_maps/{main,bel,cha}_attila_map`: everything except the display textures and pictures;
  - the compiled tile database and 3 sample tiles.
- **Probes:** in `output/survey_attila/probes`.
  - `Probe/` is a C# app against the built `Atlas3K.Formats.dll` / `Atlas3K.Core.dll`. Its modes are the default run, `esf`, `hlp`, `hlptail` and `terry`.
  - Outputs: `probe_out.txt`, `hlp_out.txt`, `esf_hlp_out.txt`, `terry_out.txt`.
  - Python scripts: `keyfuncs_attila.py` (string hits, `keyfuncs_out.txt`), `exports_attila.py` and `expcmp.py` (exports), `tilelist_attila.py`, `trees_attila.py`, `trees2.py`, `maphex_attila.py`, `heights_attila.py`, `heights2.py`, `climate_check.py`, `lohi_check3.py`, `masks_check*.py` and `tifinfo.py`.

## Summary

Attila is the **Rome II-generation Warscape**: 32-bit, Qt 4.8 tools, BOB `*.AssemblyKit.dll`. Its campaign terrain is
older and simpler than 3K's:
- **Terrain:** tiles placed from `tile_map.png` (`terrain.tile_list`) on top of a u16 low-frequency heightmap
  (`lf_height_map.dds` / `.data`).
- **Props:** in one `prop_marker.markers` file (`BASE_MARKER_REPOSITORY`).
- **Trees:** come from a colour-coded `trees.png`.

Attila has no global meshes, BMD `global_props.bin`, river spline models, height patches, `global_map\`, generated
camera heightmap or spd_data.

So the picture is the reverse of WH3:
- **Carries over:** the terrain core. The tile-list record layout is nearly identical (19 vs 21 bytes, same orientation
  bits, same normalised lo/hi), and the tile DB has the same model (TILE / TILE_SET / VARIATION / TLT_EQUALS, same
  Warscape class names). The u16 8 px/hex lf DDS, map.hex (16 B/hex), PPD, the ESF reader and PFH4 pack reading also
  carry over.
- **Simpler or absent in Attila:** most of the hard 3K work (global meshes, BMD props, BOB rivers, camera heightmap)
  isn't needed.
- **Older formats:** props, trees, the hlp root and map_data are older, so their writers are new but small.

**The blocker:** BOB parity would mean new Ghidra/Frida work on 32-bit DLLs, and the CHMF `lf_height_map.data` format
is still unported.

## 1. Tools: kit DLLs

All Attila kit binaries are **x86 (32-bit)** PE files dated 2020-01-17. The 3K kit is x64 (2023-03-16).

| 3K kit (x64) | Attila kit (x86) | Notes |
|---|---|---|
| `warscape.modder.x64.dll` | `Warscape.AssemblyKit.dll` (8.7 MB) | 1,136 exports. 985 distinct names vs 3K's 1,066, **369 common**. TILE_DATABASE names 159 vs 227, 41 common. |
| `bob_terrain` / `bob_campaign` / `bob_tile` / `bob_vegetation` / `bob_texture` / `bob_warscapeshared` | `BOB_Terrain` / `BOB_Campaign` / `BOB_Tile` / `BOB_Vegetation` / `BOB_Texture` / `BOB_WarscapeShared` `.AssemblyKit.dll` | BOB_Terrain's campaign actions are **Tilemap**, **Heights & Normals**, **Trees** and **Terry file**. There is no Global Mesh, Generate Camera Height Map or Convert lookup texture action. |
| `tooldatabuilder.modder.x64.dll` | `ToolDataBuilderDll.AssemblyKit.dll` | 180 names, 112 common. |
| `empireutility`, `utilitydll`, `qttoolutility`, `calibs` | same names, `.AssemblyKit.dll` | 1,643 / 1,120 / 688 / 807 names in common with 3K. |
| `empirecampaign.modder.x64.dll` (hlp/spd) | **missing** | The hlp generator is in the game's `empire.retail.dll` (32 MB, x86): it has `process_campaign_ai_map_data` and `CAI_HIGH_LEVEL_PATHFINDER`. BOB_Campaign keeps `process_campaign_ai_map_data`. |
| `bob.retail.x64.exe` | `BOB.AssemblyKit.exe` (x86) | The Frida harness would need an x86 target. |
| — | `BOB_DBExport`, `BOB_TDBShared`, `TEd.AssemblyKit.exe`, `TWeak_TerrainMetadataEditor`, Qt4 DLLs | |

**Functions and classes the 3K port relied on** (string, RTTI and export hits; `keyfuncs_out.txt`):

| Present in Attila | Missing in Attila |
|---|---|
| `TILE_DATABASE`, `TILE_MAP::calculate_flow`, `TLT_EQUALS`, `link_target_count`, `get_tile_space_high_frequency_positions` | `process_terrain_global_mesh` / "Global Mesh", `global_meshes`, `land_mesh_`, `height_patch_collection`, `global_blend` |
| `rasterise_max_heights`, `VERTEX_LIST_CLEANER`, `MODEL_PROCESSOR`, `MESH_SPLITTER`, `TRIANGLE_MERGER` (tooldatabuilder, used for battle and river meshes) | `generate_camera_height_map`, `TERRAIN_QUAD_TREE`, `intersect_non_empty_nodes_gproj`, `TERRAIN_RENDER_SETUP::get_height_worker` |
| `SEGMENTED_SPLINE_3::optimise_spline` | `COMPRESSED_MAP` (Attila uses CHMF `.data` and DDS instead) |
| `CAMPAIGN_TREE_LIST`, `TOOLDATABUILDER::process_trees` | `CampaignTreeGenerator`, `generate_campaign_tree_list_for`, `ACTION_PROCESS_CAMPAIGN_TREES`, `HeightDataProvider`, `get_high_frequency_height_new` |
| `terrain.tile_list`, `lf_height_map.data`, `CHMF`, `FASTBIN0`, `map.hex`, `process_campaign_ai_map_data`, `trade_routes` | `BMD_META_TAG_COLLECTION`, `bmd_objects`, `global_props.bin`, `ECRiverSpline` |
| `BASE_MARKER_REPOSITORY`, `PROP_MARKER`, `PARTICLE_EMITTER_MARKER` (EmpireUtility) | `CA::murmur_hash` (no hits), `CAI_TRANSITION_DATA`, `CAI_SIMPLE_PATH_DIRECTORY` / `spd_data` |

All the 3K function addresses would have to be found again with Ghidra in 32-bit code (`__thiscall`, `QAE`
mangling). Ghidra was not run for this survey.

## 2. Campaign map sources

| | 3K (`3k_dlc07_main_map`) | Attila (`main_attila_map`, staged kit files) |
|---|---|---|
| `.terry` | project v20, scene v35, per-region `.layer` files, TerrainMaps | **project v3, scene v10**: one 12 MB XML, entities directly under `<scene>`, no layers, no TerrainMaps. 14,644 entities: 14,322 ECPropMesh (with ECMesh, ECTransform, ECSeasonMask, ECLandscapeAbove), 310 ECVFX, 12 ECEnvironmentVolume. **No rivers, lights or composite scenes.** |
| Heights | LowFrequencyHeight u16 TIF, 8 px/hex; LowFrequencyHeightSea 4 px/hex | `lf_heights.tif` u16, **16 px/hex** (16256 × 11528); `lf_sea_heights.tif` u16, 4 px/hex (4064 × 2882) |
| Other rasters | BlendCampaign, CampaignTree (2 px/hex) | `normal.dds` (A8R8G8B8, 8128 × 5764, 13 mips), `lf_sea_colour.tif` / `_small.tif`, `snow_mask\*.tga`, `masks.xml` and season masks (seasonal texture swaps) |
| tile_map / climate_map | 2 px/hex | 2 px/hex: `tile_map.png` RGBA and `climate_map.png` RGB, both 2032 × 1441, plus `layout_map.png` |
| Trees | CampaignTree TerrainMap and DB tables (campaign_tree_ids / variants / seasons) | `trees.png` (2 px/hex RGBA) and `tree_database.xml` (colour → spring/summer/autumn/winter/snow model folders), in `raw_data\terrain\campaigns\<map>` (bel) |
| map.hex | v19, 16-byte header, 7 name lists, 16 B/hex | **v15**: 8-byte header, **6 lists** (no AOI list), the same two colour tables, **the same 16 B/hex records** plus a 4-byte tail; bel_attila is 1016 × 650 |
| Tile DB source | `_tile_database\_settings.bin` and `tiles\*.bin` | **XML**: `_settings.xml` (RENDER_PARAMS v3, 8 CLIMATES) and `TILES\*.xml` (TILE v3, VARIATION v2), 481 tiles |

**Campaign maps.** The terrain packs hold only **`main_attila_map`**. `bel_attila_map` (The Last Roman) and
`cha_attila_map` (Age of Charlemagne) ship only campaign_maps data (lookup, hlp, map_data, ppd, camera heightmap) and
reuse the main terrain:

| Map | Hexes |
|---|---|
| main | 1016 × 720 |
| bel | 1016 × 650 |
| cha | 920 × 800 |

## 3. Compiled files compared

**Packs.** Attila packs are **PFH4, uncompressed** (byteMask 0x1, or 0x40 for boot). Atlas3K's `PackFile` reads them
as they are, byte-identical to RPFM's extraction (`probe_out.txt`). Its writer emits PFH5, so it needs a PFH4 mode.

| File | 3K | Attila | Atlas3K on Attila |
|---|---|---|---|
| `tile_list.bin` → **`terrain.tile_list`** | FASTBIN0 v1/1: paths, climates, 6 floats, 11 ints, u8, 21-byte records (u16 ver, u32 path, u8 climate, u16 x, y, u8 orient, u8 flag, f32 lo, hi) | **no magic**. u32 version 11 and u32 record count, then **the same 6 floats** and 11 ints (0, 2032, 1441, 1016, 720, 0, −1441.0f, −9, −37, 2053, 1447), u8 1, paths (419), no climate table. **19-byte records**: u32 path, u16 x, y, **the same one-hot orientation** (0x10..0x80, \|0x04), u8 flags (1/3/6/7), u8 **climate = tile DB climate index**, f32 lo, hi normalised 0..1. 623,706 records, parsed to the exact end. | 3K reader: "not FASTBIN0". **Small branch.** Checked: the climate byte matches `climate_map.png` at the record's (x, y) **without a y flip**. lo/hi = min/max of `lf_heights.tif`/65535 over the footprint plus a 2-tile-pixel margin (±1 LSB on samples). |
| `global_map\*` | blend DDS, texture_arrays, tile list copy | **not shipped** | n/a |
| `lf_height_map.compressed_map` / `.dds` | FASTBIN0 compressed_map and L16 DDS | `lf_height_map.dds`: L16, 8128 × 5764 (8 px/hex), no mips. It is the **2 × 2 box mean of `lf_heights.tif`** (≤ 1 LSB on 99.94% of pixels; the rest is one local edit of about 190 × 190 px where kit and shipped differ; the exact rounding is still open). `lf_height_map_lq.dds` (4064 × 2882) is the 2 × 2 mean of that. `lf_height_map.data` is **CHMF v5** (2032 × 1441 header, tiled) | `CompressedMap`: "not FASTBIN0". The DDS writers are trivial; **CHMF needs a new codec** (it is also WH3's tile hf format, never ported) |
| `lf_sea_height_map` | compressed_map and L16 DDS, no mips | `lf_sea_height_map.dds`: L16 4064 × 2882, **top mip byte-identical to `lf_sea_heights.tif`**, plus an 11-mip chain | the writer needs mips |
| `lf_normal.dds` | unused in 3K | DXT5 8128 × 5764, 13 mips, from the kit's `normal.dds` | BC3 encode (the kit ships `nvtt.dll`) |
| `lf_sea_colour.dds`, `snow_mask_*.dds` (9 seasonal) | — | A8R8G8B8 1016 × 720 with 10 mips; L8 2032 × 1441 | Derived, **not straight copies**: sea colour mean abs 9.6 against the small TIF; snow correlation 0.75 against the TGA, same orientation. The rule needs BOB RE |
| `climate_map.cm` | yes | **not shipped** (the climate is in the tile list) | n/a |
| `global_meshes\`, `height_patches\`, river `models\` | yes | **not shipped**. Rivers are river / river_start / river_mouth / river_crossing tiles in the tile list | n/a |
| `global_props.bin` | BMD v35 per region, buckets | **`prop_marker.markers`** (1.24 MB): a UTF-16 `BASE_MARKER_REPOSITORY` / `PROP_MARKER` table, models grouped by name (266 model strings). Per record: a transform matrix, the position (the first record = `roman_port_jetty_1` at 50.110, −0.0188, 177.102, as in the .terry), 1.0, season mask 0x0F and 4 visibility flags. Count field 14,331 vs 14,322 ECPropMesh in the kit .terry. Also `particle_emitter_marker.markers` (ECVFX), `display\campaign_*_marker.markers` | no reader; new writer (simple, no regions or buckets) |
| `trees.campaign_tree_list` | v5: x, y, z, flag(1), variant, u32 season list | **v3**: the same header (version, 0, 0, world 678.5 × 556.14, 39 types). **15-byte instances**: x, y, z, flag (0/1), variant (0–5), season mask byte (0x0F). 123,029 trees. **One tree per trees.png pixel** (122,965 of 122,997 cells hold one) | rejected (v3). Small branch; WH3's v4 has the same 15-byte instance |
| `camera_heightmap.png` | 16-bit grey, 2 px/hex, `height_scale` tEXt | **8-bit palette PNG, hand-made** (pHYs / cHRM / iCCP chunks): main 406 × 288, bel 406 × 260, cha 368 × 320. No kit generator | n/a (copy or paint) |
| Lookup `.tga` / `.dds` / `_minimap.tga` | 16-bit indices, 32-bit palette, plus an R16 DDS | **8-bit indices, 256 × 24-bit palette**, stored bottom-up (descriptor 0x08), **no DDS**. Main is 2400 × 1702 (224 colours used); `_map_minimap.tga` is type-2 RGB | `LookupTexture` decodes the same colours, but CA's palette order is not first-appearance (top-down or bottom-up), so it probably comes from an indexed source BMP: wait for the kit BMP. Small branch |
| `map_data.esf` | MAP_DATA v2, 25 records (MASKED_REGIONS_DATA, REGION_INDEX, PRIMARY / PORT_SLOT_AREA_BLOCK) | **MAP_DATA v0**, 26 records: adds trade_nodes, bridges, SLOT_ARRAY / SLOT_POSITIONS / SLOT_AREA / PORT_POSITIONS / PORT_AREA_BLOCK; **no MASKED_REGIONS_DATA, REGION_INDEX or MAP_FILE_DATA_VERSION** | `EsfTree` reads it; `MapDataRegions` fails (no MASKED_REGIONS_DATA) |
| `hlp_data.esf` | `CAI_TRANSITION_DATA` v0, flat | **`CAI_HLP_ROOT` → `CAI_HIGH_LEVEL_PATHFINDER` v5**, flat: **3K's node / area / transition / cost layout minus area field B** parses all 224 / 120 / 175 nodes (main / bel / cha). It is followed by a fixed table: 131,072 u32 (0xFFFFFFFE) plus 65,537 zeros plus 1 value (`hlp_out.txt`) | `HlpData` rejects the root name; **medium branch** |
| `spd_data.esf` | `CAI_SIMPLE_PATH_DIRECTORY` | **not shipped** | n/a (less work) |
| `pathfinding.ppd` | v2 | v2 | **reads unchanged**: 1016 × 720, 1016 × 650, 920 × 800 |
| others | `trade_routes.ptd` | `trade_routes.ptd`, `metadata.dat` (MTGI 4096 × 2048 u16 from terrain / attribute_metadata.tga), `dynamic_resources.esf`, `borders.pbd` | BOB_Campaign "Process metadata" and "dynamic resources" |

## 4. Tile database

| | 3K | Attila |
|---|---|---|
| Kit source | binary `_settings.bin` and `tiles\*.bin` | **XML**: `_settings.xml` and `TILES\*.xml` (481) |
| Compiled | the same folder in `terrain2.pack`, 544 tiles | **one `terrain\tiles\campaign\tile_database.bin`** (FASTBIN0, RENDER_PARAMS **v6**, 259 KB). It holds the climates, tile sets and every tile inline, with TLT_EQUALS links |
| Climates | 4 | **8**: default, desert, europe, mediterranean, eastern_desert, northern_europe, desert_notsand, north (each with a texture set and ROME_Destruct) |
| Tile sets | generic, sea, mountains_*, river*, roads_* … | grass_01..08, sand_01..08, mud_01..04, farmland_*, swamp_01, sea, sea_coast, deep_sea, cliff_custom, *_mountains, lakes, river, river_start / mouth / crossing, roads, roads_stone, roads_climate, marib_dam … |
| Tile contents | hf `.compressed_map`, bmd_data.bin, meshes (RMV2 v8) | `hf_height_map.data` (CHMF, 129 × 129 on a 1x1), **RMV2 v6** `mesh.rigid_model_v2`, blend / index / normal DDS, `bmd.grass_list`, battle-style `.markers` and building lists |

Atlas3K results:
- `CampaignTileDatabase.ReadTileSets` on `tile_database.bin`: fails.
- `LoadFolder` on the kit: fails (it wants `_settings.bin`).
- `RigidModel` on RMV2 v6: fails ("truncated attachment").

The matching code (TILE_MAP, calculate_flow, TLT_EQUALS) has the same class and method names in Attila's Warscape, so
3K's TileListStep logic is the right starting point. The shipped `terrain.tile_list` and the staged `tile_map.png` give a
ready parity reference.

## 5. Verdict per step

| Step | Attila verdict | What changes | Effort | WH3 verdict (for comparison) |
|---|---|---|---|---|
| `rasters` | **re-port (small–medium)** | BOB's "Heights & Normals": lf DDS (2 × 2 mean of the 16 px/hex TIF), the `_lq` DDS, sea DDS (copy plus mips), lf_normal (BC3), sea colour, snow masks, and the **CHMF `lf_height_map.data`** (new codec); no climate_map.cm | 1.5–2.5 weeks (CHMF most of it) | re-port (small) |
| `tile_list` | **version branch (small) + tile DB reader (medium)** | v11 header order, 19-byte records, climate index byte, no y flip, lo/hi with a margin; XML or `tile_database.bin` DB with 8 climates; parity against the shipped list | 1.5–3 weeks to parity | small branch + medium DB |
| `global_map` | **not applicable** | not shipped | 0 | small branch |
| `global_mesh` | **not applicable** | not shipped | 0 | not applicable |
| `rivers` | **not applicable** | rivers are tiles; no spline models in the .terry or packs | 0 | re-port (medium) |
| `global_props` | **re-port (small–medium)** | `.terry` v3 reader plus `prop_marker.markers` / `particle_emitter_marker.markers` writer; no regions, buckets or quadtree | about 1 week | re-port (medium–large) |
| `camera_heightmap` | **not applicable** (hand-made 8-bit PNG) | optional simple generator | 0–2 days | re-port (medium) |
| `trees` | **branch (small–medium)** | v3 writer (15-byte instance, season mask byte); source `trees.png` and `tree_database.xml` instead of DB tables; one tree per pixel; the jitter / variant rule needs `TOOLDATABUILDER::process_trees` RE for parity | 3–5 days game-valid, +1 week parity | branch (small–medium) |
| `lookup` | **branch (small)** | 8-bit / 24-bit palette TGA, bottom-up, no DDS; palette order from the source BMP (await the kit) | ≤ 1 day | works as is |
| `hlp_spd` | **branch (medium)**; spd not applicable | hlp = 3K layout minus one u32 per area, `CAI_HLP_ROOT` wrapper v5, plus a fixed 196,610-value table; map_data v0 reader (no MASKED_REGIONS_DATA); the generator is in 32-bit `empire.retail.dll` | 2–3 weeks | re-port (large) |
| new: metadata.dat, dynamic_resources.esf | **new (small each)** | MTGI raster from two TGAs; ESF from dynamic_resources.png / xml | about 1 week together | — |
| plumbing | **small** | PFH4 pack writer; game profile (`Attila.exe` x86, `data\`, `*.AssemblyKit.dll`, `BOB.AssemblyKit.exe`); map.hex v15 reader (6 lists, 8-byte header); `.terry` v3 single-scene reader (TerryProject finds 0 maps; LayerDocument: "layer has no <entities>") | about 1 week | zstd packs + profile |

## Attila vs WH3 vs 3K

| | 3K (2019) | Attila (2015) | WH3 (2022) |
|---|---|---|---|
| Engine generation | Warscape, WH2/3K line, x64, Terry with layers | **Rome II-line Warscape** (Rome II, Attila, Thrones), **x86**, Qt4 BOB/TWeak, single-scene .terry v3 | 3K's successor, x64, Terry v26 |
| Terrain rendering | tiles plus lf compressed_map, global meshes | **tiles plus u16 lf DDS / CHMF** (no global meshes) | full-resolution float rasters (BC6H), no tile list lo/hi |
| Props | BMD v35 per region | marker table | BMD v27 plus culture masks |
| hlp | CAI_TRANSITION_DATA v0 | CAI_HLP_ROOT / CAI_HIGH_LEVEL_PATHFINDER v5 (3K-like body plus table) | CAI_HIGH_LEVEL_PATHFINDER v1 (WH3's root name comes from the Attila lineage) |
| Packs | PFH5, uncompressed | PFH4, uncompressed (read today) | PFH5, zstd |

**Is Attila closer to 3K than WH3?** It is closer for the **terrain core**: tile list, tile DB model, u16 lf at 8 px/hex,
2 px/hex tile and climate maps, map.hex records, hlp body and packs. That is the part of 3K's code worth reusing.

It is farther in **generation and tooling**: 32-bit, Qt4, single-scene .terry, marker props. Those steps need new
writers, though small ones. Many 3K steps have no Attila counterpart (global_map, global_mesh, rivers, camera, spd), so
the total work is smaller than for WH3 even though less 3K code is reused verbatim.

## Overall estimate

| Goal | Scope | Time |
|---|---|---|
| **Game-valid Attila build** | lf DDS rasters (CHMF codec included), sea / normal / snow textures, tile_list on the Attila tile DB, prop and VFX markers from `.terry` v3, trees v3, lookup TGA, metadata / dynamic resources, PFH4 packs and the game profile; hlp from CA's flow (`process_campaign_ai_map_data`) | about 4–6 weeks |
| **BOB-parity level like 3K** | the above plus Ghidra / Frida on the x86 DLLs (lf rounding, CHMF, tile matching and lo/hi margin, tree jitter, sea colour / snow rules) | about +3–5 weeks |
| **hlp** | the native hlp branch plus a map_data v0 reader; generator RE in `empire.retail.dll` | about +2–3 weeks |

## What still needs the kit download

The staged files used here came from an unfinished download (the manifest still reports 0 bytes). Re-check them once
StateFlags is 4.

| Missing piece | Needed for |
|---|---|
| `raw_data\EmpireDesignData\campaign_maps\main_attila_map` (map.hex, lookup BMP, `trees.png` / `tree_database.xml`, terrain / attribute_metadata.tga, dynamic resources) | map.hex v15 records on main, lookup palette order, tree parity, metadata.dat |
| the other snow-mask TGAs and any season inputs not yet staged | snow mask rules |
| BOB reference outputs in `working_data` (none on disk) | true BOB parity rather than shipped-file parity |
| `raw_data\db` XML for the campaign tables (playable areas, campaign_map variables) | world extents and constants |

Running BOB on the kit (not allowed in this survey) is the way to get fresh reference outputs, given how much the kit
sources and the shipped files differ (one lf edit area, 14,322 vs 14,331 props).
