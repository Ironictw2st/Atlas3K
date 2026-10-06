# Native battle-map build (BOB's battle export without BOB)

`Atlas3K.Cli build-battle <kit root> <map id> [--out dir] [--only step,...] [--compare]` runs the steps in
`src/Atlas3K.Core/Battle/Build/` and writes BOB's working_data layout under `output/battle_native/<id>/`.
- With `--corpus Z:/Claude/BattleMaps/out/battle_parity [--run bob_run1]` it reads a corpus project's frozen sources
  instead of the kit, and `--compare` byte-compares against that run.
- `battle-parity` (corpus worker) does the full masked comparison.
- `battle-steps` lists the steps; `battle-db <kit>` dumps the battle tile database and the placement groups.

Steps are `IBattleBuildStep` classes found by reflection and ordered by `[BattleStepOrder]`:

| Range | Family |
|---|---|
| 100–199 | map folder, tile database entry, terrain rasters |
| 200–299 | meshes (`Build/Meshes`) |
| 300–399 | bmd and vegetation (`Build/Bmd`) |

Ground truth is the parity corpus (8 kit battle projects, 3–5 BOB runs each; `bob_run1` is the reference; the
status table below covers the 5 round-1 projects, "Round 2 corpus" the other 3). See
`Z:\Claude\BattleMaps\out\battle_parity\README.md`. Research scripts are in `research/battle_map_files/`
(map family) and `research/battle_build/` (corpus, meshes, bmd).

## Status (bob_run1)

Map-folder files exist only for 224ad6d5 and df46bdbc; the other three projects are tile-only.

| File | Step | Status |
|---|---|---|
| `map/climate_map.cm` | climate | identical 2/2 |
| `map/lf_height_map.compressed_map` / `.dds` | lf | identical 2/2 (round 2: 3/3) |
| `map/lf_sea_height_map.compressed_map` / `.dds` | lf | identical 2/2 |
| `map/lf_normal.dds` | lf_normal | identical 2/2 (round 2: 3/3) |
| `map/map_info.xml` | map_info | identical 5/5 |
| `map/icon.tga` | icon | identical 5/5 |
| `map/tile_list.bin` | tile_list | identical 2/2 (round 2: 3/3, with the corpus's `kit_tile_db`) |
| `tile_db/_assembly_kit_<id>.bin` / `.xml` | tile_db | identical 5/5 |
| `tile/hf_height_map.compressed_map` | hf_height | identical 5/5 |
| `tile/hf_water_map.compressed_map` | hf_water | identical 2/2 (the river projects), correctly absent on the other 3 |
| `tile/blend0.dds`, `blend1.dds` | blend | identical 2/2 (dfe064a6, df46bdbc), correctly absent on the 3 unpainted projects (round 2: 3/3, partial weights) |
| `tile/normal.dds` | tile_normal | identical 2/2, correctly absent on the other 3 |
| `tile/ground_types.dds` | ground_types | identical 5/5 (round 2: 3/3) |
| `tile/debug_protection_map.png` | debug_protection | identical 5/5 (all corpus maps are empty; building protection not ported) |
| Terry-save inputs → `<out>/terry_save/` | terry_save | raw map folder (tile_map.png, lf tifs, climate_map.png, explicit_tiles.txt) identical on 224ad6d5 (the only Terry-made map folder; df46bdbc's was scripted); rules.bob identical; Terry's tile database entry identical on 0a26b6e0, dfe064a6 differs only in the uninitialised `scalable` byte |
| `tile/shadow_mesh.rigid_model_v2` | tile_meshes | identical 5/5 |
| `tile/mesh.rigid_model_v2`, `outfield_mesh.rigid_model_v2` | tile_meshes | identical or masked-identical (LOD u32 0xA4..0xA7) 5/5 |
| `tile/river_mesh.wsmodel`, `outfield_river_mesh.wsmodel` | river_meshes | identical 5/5 |
| `tile/*river_mesh.wsmodel.rigid_model_v2` | river_meshes | identical without a river; masked-identical with rivers (the stale u32 at +624 of each river part: 0x318..0x31B with one river) |
| `tile/bmd_data.bin` / `.xml` | bmd_data | identical 4/4 (224ad6d5 has none) when the grass list is present; BOB's capture-location list order is random (ours: descending first id; compared modulo that order) |
| `tile/<climate>_procedural_bmd_data.bin` / `.xml` | procedural_bmd | identical 5/5 (BOB headless places 0 procedural positions: empty bmd per climate) |
| `tile/bmd_nogo_data.bin` / `.xml` | bmd_nogo | identical 5/5 (4 terrain outlines on dfe064a6/df46bdbc, none on the flat tiles) |
| `tile/<climate>.grass_list.bin` | – | **not started** (QTU::generate_grass decompiled: xoroshiro128+ jittered grid per terrain texel; see bmd notes) |
| `tile/<climate>.tree_list.bin` / `.xml` | – | **not started**; no corpus tile places trees |

## Round 2 corpus

Three more projects (2026-10-06, corpus README "Round 2"), made to exercise what round 1 left empty:
- `5a2e…0001` r2_tmp_forest: temperate, painted forest, 13,392 procedural objects, 2 rivers.
- `5a2e…0002` r2_cld_siege: cold vista, walls / gate / siege AI, capture points, deployment zones.
- `5a2e…0003` r2_multi_climate: subtropical vista, climate_mask subtropical,temperate,arid,tropical, 3 rivers.

Round 1 had no procedural objects because its blend maps paint no texture that has `*_tree_parameters.xml` groups
for its climate, not because of headless mode.

Native = `build-battle --corpus … --run bob_run1` at f8ac7b5, compared with `battle-parity` (masks applied). These are
the next porting round's to-do list:

| File | r2_tmp_forest | r2_cld_siege | r2_multi_climate | Note |
|---|---|---|---|---|
| `map/climate_map.cm`, `icon.tga`, `map_info.xml`, `lf_*.dds`, `lf_sea_height_map.*` | identical | identical | identical | |
| `map/lf_height_map.compressed_map` | identical | identical | identical (was 8 bytes) | a constant source keeps lo = hi in the header |
| `map/lf_normal.dds` | identical | identical (was 19 bytes) | identical | BOB's convolution term order (steep cold map) |
| `map/tile_list.bin` | identical | identical | identical | the corpus runs had the sibling round-2 tiles installed: `kit_tile_db` (below) |
| `tile_db/*` | identical | identical | identical | |
| `tile/blend0.dds` | identical | identical | identical | channel 0 absorbs the float sum's error (rules) |
| `tile/ground_types.dds` | identical | identical | identical | first channel over 0.55, not the highest weight (rules) |
| `tile/hf_*`, `normal.dds`, `shadow_mesh`, `debug_protection_map.png`, `bmd_nogo_data.*` | identical | identical | identical | |
| `tile/mesh`, `outfield_mesh` | masked-identical | masked-identical | masked-identical | |
| `tile/*river_mesh.wsmodel` | identical | identical | identical | |
| `tile/*river_mesh.wsmodel.rigid_model_v2` | masked-identical | masked-identical | masked-identical | several rivers (2, 3): every part gets the union bounds and pivot; a stale u32 at +624 per part (masked) |
| `tile/bmd_data.*` | identical (with BOB's tree list) | identical to run3 (with BOB's tree list; capture-list order is random in BOB) | identical (with BOB's tree lists) | siege AI nodes, inlined-wall building_id, ECWall flags and AIH_AMBUSH_FOREST hints ported; only the tree list references wait for a native tree_list step |
| `tile/<climate>_procedural_bmd_data.*` | **differs** (44,670 vs 308) | **differs** | **differs** ×4 climates | native writes the empty bmd; procedural placement not ported |
| `tile/<climate>.grass_list.bin`, `.tree_list.bin/.xml` | missing | missing | missing ×4 | not ported |

## Map family: the rules

| File | Rule |
|---|---|
| lf maps | Float32 throughout: h = s · (1/65535); lo/hi = min/max of h; v = trunc((h − lo) · (1/(hi − lo)) · 65535). Header f[1] = lo, f[4] = hi. Both reciprocal multiplications matter: dividing is off by one on a few pixels (`lf_round2.py`). The sea map is the same rule. A constant source gives all zeros with lo = hi = its value (round-2 subtropical map, lf 1966 everywhere; an all-zero sea map gives 0, 0). |
| climate_map.cm | climate_map.png pixel → exact RGB match against the battle tile database climates (`_settings.bin`, in order: default, arid, arid_fertile, cold, …); 0 if no match. Same size as the png, 16-pixel tiles, header f[4] = 65535. |
| map_info.xml | bob_tile `ACTION_TERRY_TILE::save_user_created_map_data`: a QDomDocument saved with indent 4 and LF line ends, built from `<user_created_map>` and the vista `env`. An empty display name becomes the .terry base name. Text escaping is QDom's: only `&`, `<` and `>`. |
| icon.tga | The same function: an `icon.tga` already in the map's output folder is kept, else VFS `Terry/icon.tga` (kit `working_data/Terry/icon.tga`) is copied. |
| tile_list.bin | Campaign `TileMatchSimulator` on the battle tile database (`BattleTileData`), with the battle-only inputs below. |
| tile_list.bin: groups | `raw_data/terrain/battles/tile_placement_groups.xml` groups are merged **after** the database's own (`TILE_PLACEMENT_GROUPS::load_and_merge`; the first colour match wins). A group's `link_as_set` counts in `contains_link_as`, and `add_tile_to_link_map` marks cells with the **group's** link_as when it has one (Frida, `research/bob_re/frida_battle_links.js`). |
| tile_list.bin: explicit tiles | `explicit_tiles.txt` tiles are placed first (`add_explicit_tiles`: y' = H − 1 − y, anchor (x, y' − h + 1), climate at (x, y'), place + also-place, no link map, no draw). |
| tile_list.bin: battle switches | `is_campaign` is false, so the campaign-only 2×2 junction-pass rule is off. |
| tile_list.bin: database order | BOB's VFS lists the packs' tile files (lower-case ordinal), then the kit's loose `working_data` ones (every `_assembly_kit_<id>` entry in `_tile_database/TILES`, lower-case ordinal) last. That input order matters for the unstable MSVC sort (Frida, `research/bob_re/frida_battle_tiles.js`). Every assembly-kit tile in the kit is a matching candidate, so other kit maps' entries change the result: the round-2 corpus runs had the sibling round-2 projects installed, recorded in `<corpus>/<id>/kit_tile_db/` and read as `BattleBuildContext.ExtraTileDbDirs` (BOB on the project alone gives the native output without them, checked with a Frida run of the full export). |
| tile_list.bin: output | Records and heights as the campaign writer. Header floats (0.5, 0.5, 1, 1, 500, 1.333); marker 0. |
| tile database entry | TILE v7 / VARIATION v10 / texture_set v2. BOB's TerryTile rewrite = Terry's saved entry with the texture channels re-derived from the .terry `texture_channel_N`, keeping only the channels the blend TIF uses (channel 0 always), compacted in order, the rest empty. That is why re-running BOB is a fixed point. The `scalable` byte is uninitialised memory from Terry's save (0x00, 0x58 and 0x8B seen) and is carried over; without a saved entry it is 0. The `.xml` has CRLF line ends, tabs and single quotes, with floats as `%f`. |
| lf_normal.dds | bob_terrain FUN_18000e4d0/FUN_18003ba70: 3×3 Sobel of h = s·(1/65535) (clamped edges), accumulated as BOB does: from 0, term by term in row-major order, ((4000 · h) · k) with k = (1, 0, −1, 2, 0, −2, 1, 0, −1) (the y gradient reads the kernel transposed), then ÷ (3·3 − 1) (FUN_180026620 / FUN_180026910); n = 1/sqrt(gy² + gx² + z²) in that addition order, nx = n·gx, ny = n·gy; z = 1/((lf px per tile-map cell) / (unit_scale 2 · tile size 128)) = 32; pixel B,G,R,A = 0, (ny+1)·127.5, 255, (nx+1)·127.5 truncated. Gentle maps also match the plain Sobel × 500; the steep round-2 cold map needs the term order (8 pixels). DDS via `AmdCompress`: the kit's AMDCompress_MT_DLL.dll (AMD_TC_ConvertTexture, options zero but dwSize 2000), mips = 2×2 box average with rounding down to 2×2 (campaign: 8×8), standard DXT5 header (Frida: `research/bob_re/frida_amd_compress.js`). |
| Terry save | Vista (`raw_data/terrain/vistas/<vista>`) tile_map.png + lf tifs copied byte for byte; climate_map.png re-encoded like Qt/libpng: RGB8, pHYs 3780, zlib level 0 (68 05, one stored block per 16 KiB), libpng adaptive filter (min sum of \|signed byte\|, first min), 8192-byte IDATs. explicit_tiles.txt = the tile centred on the tile map + CRLF. rules.bob (map and tile working folders) = `[Pack]` template with `<.terry stem>_<id>.pack`, CRLF, no final newline. Tile entry = `TileDbEntry.FromTerry` (all 8 channels). |
| blend0/1.dds | The blend channels in use (channel 0 always, channel order, as in the rewritten tile entry) packed R,G,B,A = used 0..3 → blend0, 4..7 → blend1, full 1280², DXT5 via `AmdCompress`. Written only when the blend TIF has a non-zero weight. The bytes are not the TIF's: `QTU::TerrainMap::data_composited` gives f = w · (1/255) per channel and channel 0 then takes up the float sum's error, f0 −= (Σ₀..₇ f − 1) (summed in channel order; an empty pixel gets f0 = 1), and `TOOLDATABUILDER` FUN_18015e8c0 writes (int)(f · 255). So channel 0 often comes out one lower than the TIF (234 → 233 next to 21): every pixel of the round-2 dump matches (Frida: `convert_blend_map`'s float vector, `Z:/Claude/BattleMaps/research/bob_re/blend_gt`). |
| tile normal.dds | 3×3 Sobel of the full float Height TIF, normalise(gx/8, gy/8, 1/normal_strength), pixel as lf_normal, DXT5 via `AmdCompress`; written with the blend textures. |
| ground_types.dds | Per pixel the EMPIREUTILITY::GROUND_TYPE (forest 0, grass 1, mud 2, sand 3, scrub 4, rock 5, deep_water 6, shallow_water 7, road 8, wooden_floor 9, snow 10, …; empireutility name table) of the first blend channel whose weight is over 0.55 (≥ 141 of 255), else channel 0's: not the highest weight (a 127/128 or 115/140 split keeps channel 0; fitted on the round-2 painted maps, 0 pixels off on all 8 projects), texture group → type from db `ground_type_to_texture_groups` (binary column order: ground_type, texture_group); blend TIF cropped by density on each side (1280 → 1024); uncompressed L8 with a bare header (flags 0, pf LUMINANCE 8-bit). |
| hf_height_map | tooldatabuilder FUN_1800edbf0 mode 0: the **decimated terrain mesh** (the float mesh behind mesh.rigid_model_v2) rasterised back onto the 1025² vertex grid by FUN_1800dc250 (field initialised to 1.0), then normalised to its own min..max with the lf rule. Steep areas therefore differ from the raw TIF wherever the triangle merger dropped vertices. |
| Mesh rasteriser (FUN_1800dc250) | Per triangle A,B,C: integer bbox of x and z (truncated) from min − 1 to max; barycentric weights from dot products of (B−A), (C−A), (P−A) in (z, x), accepted in [−0.0001, 1.0001]; cell (trunc(s·z), trunc(s·x)) with s = density / 128 **overwritten** (last triangle wins) by w_C·C.y + w_B·B.y + w_A·A.y. |
| hf_water_map | A −1000 field, the river model (+ pivot) rasterised in by FUN_1800dc250, then water planes (FUN_1800ed480; not in the corpus). |

### Open in the map family

- **Water planes** (WATER_PLANE_MESH) in hf_water_map, and `hf_height_map_mesh_delta.compressed_map` (written with HEIGHT_OBJECTs): no corpus project has them.
- **Protection map from buildings** (debug_protection_map.png content, and the mesh's protection flags): every corpus map is empty, so only the empty map is reproduced (Qt PNG, classic zlib level 6).

## Meshes (worker B, 2026-10-06)

Steps live in `src/Atlas3K.Core/Battle/Build/Meshes/`: `tile_meshes` (order 200) and `river_meshes` (order 210). The
test is `BattleTileMeshTests`, over all 5 corpus projects. `*.agf` files are not BOB output: they are asset-graph
files of an old build (`load_asset_graph=0`) and are dropped.

### Where it comes from

"TerryTile / Process Terry tile (heightmap)" calls bob_tile `ACTION_TERRY_TILE_HEIGHTMAP::run`, which calls
`TOOLDATABUILDER::process_tile_internal` (tooldatabuilder 0x1800d76a0).
- Each output goes through `FUN_1800edbf0(ctx, mode, mesh path, river path, hf path, write hf, ...)`:
  - shadow first (mode 2);
  - then, for `requires_infield_lodding` tiles (Terry's `infield_tile`), outfield (mode 1) and mesh (mode 0).
- Each one: `FUN_1800d9c60` builds the TILE_OUTPUT_DATA, then `MODEL_PROCESSOR::open_height_map` + `write` write the
  RMV2.
- `FUN_1800d98c0` / `open_river_spline` write the river model.
- The decompiles are CA code and not in the repo: `Z:\Claude\BattleMaps\research\bob_re\tile_mesh`, `tile_mesh2`,
  `tile_mesh3`, `tile_action`.

BOB settings (bob_tile FUN_18001ac60, defaults used):
- `DisableMeshOptimisation` false;
- `DisableProtectionMap` false;
- `infield_fixed_vertex_interval` 16;
- `outfield_fixed_vertex_interval` 0x800.

Battle tile database (`terrain/tiles/battle/_tile_database/_settings.bin`, fast.pack):
- triangle_density 128;
- shadow_mesh_angle 90;
- triangle_decimation_angle_factors0 20°;
- render_params.unit_scale 2.

### Rules

| Part | Rule |
|---|---|
| Height field | warscape `load_and_process_height_map`: the Terry Height TIF minus a border. Size W − (2·density − 1) = 1025; sample (r, c) = TIF[r + density + 1, c + density + 1]; no flip. A per-pixel scale field multiplies it; it is 1 on every corpus tile. |
| Grid | Vertex r·W + c = (c·f, h, r·f), f = 128 / density. The mesh uses step 1; outfield and shadow use step 16 (lod shift (density == 128) + 3). Quads are [a, b, c] [b, d, c] with a = (r, c), b = (r+s, c), c = (r, c+s); the last quad of a row or column stretches to the edge. |
| Flags | In order: (1) 0 if the ±step neighbourhood leaves the tile cells (`FUN_1800e01e0`); this covers the borders and, at step 1, the second-to-last row/column. (2) The fixed-vertex lattice (16, or 2048 for outfield) and the corners → 0. (3) The edge lattice (8 / 2048) → 0; other edge vertices → 3; everything else → 2. (4) Mesh only: protection map > 0.5 → 0 (row-flipped index; empty on every corpus map). |
| Normals | `FUN_180147380`: the campaign Sobel filter (÷8, clamped), with up = 1 / normal_strength. |
| Skirts | `FUN_1800dcf00`, unmasked branch: the top, bottom, left and right edge rows are copied 10 units lower (fringe marker +0x78 = 1) and stitched with two triangles per step. Flags: 1 on the lattice and at corners, else 4. |
| Merge | The campaign `TriangleMerger`: `process(factor, 120, 3, flags)` with span 120, height tolerance 3 and factor cosf(20° · 0.017453292). Skirts and edges never collapse. |
| Clean / split / sort | First-use renumbering, then MESH_SPLITTER (65,000), then "Sort fringes": a stable partition that moves triangles touching a skirt vertex to the end. |
| Shadow | Mode 2 keeps triangles whose face normal is steeper than shadow_mesh_angle (90°). A height field has none, so the result is an RMV2 with 0 LODs (140 bytes). |
| RMV2 | Material 96, render flags 0. 8-byte vertices: BOB's float→half of x, y, z, with w 0. Each triangle's first two indices are swapped; bounds are the float min/max of the vertices. Shader block: "rigid_default", plus 0x8D at 15 and 9E D4 at 24. Material block: "TerrainBase0" (64 bytes), then u32 1024, 1024, field width (1025), LOD count 1, 16, and the index count before the fringes. |
| Rivers | `FUN_1800d99e0` runs once per ECRiverSpline in the tile's layers (`<project>.<ECLayerFile id>.layer`, recursively). It is the campaign `BobRiver` chain in the layer's own coordinates, with world uv over (0, 0)..(tiles · unit_scale · 128). `FUN_180146460` then divides x and z by unit_scale before the pivot is subtracted. Outfield and infield river files hold the same model. The wsmodel uses LF line ends and no final newline; its material is the river's own or the project's `river_material`, and it is `<materials/>` when there are no rivers. Several rivers: one LOD-0 part per river in layer order, every part with the union bounds of all parts (and so the union's pivot); the u32 at +624 of each part is stale memory (masked). |

### Open (meshes)

- Masked tiles (`cells/mask`): the per-cell skirt branch of `FUN_1800dcf00` is not ported.
- Protection map (buildings): passed as none, because every corpus map is empty.
- Tiles at any density or size other than 128 / 8×8: the code follows the decompile, but the corpus only has 128 / 8×8.

## Bmd family: the rules (worker C)

| File | Rule |
|---|---|
| bmd codec | `Atlas3K.Formats.Battle.BattleBmd`: FASTBIN0 v35 BATTLE_MAP_DEFINITION_DATA through the field table `Battle/Data/bmd_layout.json` (shared with `research/battle_build/bmd_codec.py`); bin → tree → bin and → BOB's .xml identical on every corpus bmd. Xml: tabs, single quotes, CRLF, floats as MSVC `%f` (exact value, ties away from zero) cut to 31 characters; non-zero meta_tags get `<!-- flags = type.value; -->` / `<!-- mask = type; -->` comments. |
| META_TAG_KEYS | bmd_data only (procedural and nogo bmds have none): every `bmd_export_types` value of a battle `bmd_layer_groups` group, DB record order; types in first-use order; checksum = the campaign mix over the values in record order (124565231). A tag's bit is its index over all values. |
| bmd_data records | Ascending entity id per section; props keyed by sorted model path, then id. Exported = not under an `ECLayerExport export="false"` layer (the Reference layer); tags from tag layers (`ECLayerExportTags`). Transforms through QtuTransform; position copied (no clamping); `ECTerrainClamp active` only sets `BHM_TERRAIN`. Spot-light angles = deg · π · (1/180) in float. Capture location: location = position + flag_position, flag_facing = (cos a, −sin a) with the degree value used as radians, building links from prefab overrides (prefab index, override name); one CAPTURE_LOCATION_LIST per tag set, in a random order (BOB's pointer-keyed map: 3 runs gave 3 orders on 5a2e0002; ours descending first id; compare modulo the list order). Deployment: one area per category (DZC_ → DAC_), zones by alliance, orientation = facing + 90, boundaries = world polyline. Playable area = ECRectangle around the position, has_been_set true, valid_* false. Grass/tree list references with the climate's meta tag. META_DATA_KEYS = season codes in first use (ECCampaignProperties; none = all five, catalog ha au wi sp su). |
| Buildings and walls | BUILDING building_id = the entity's ECPrefabOverride id when enabled (an inlined prefab building), else empty; properties weak_point / ai_breachable / dockable = ECWall weak_wall / ai_breachable / dockable (false / true / true without ECWall). |
| Siege AI | Each ECSiegeAINode (entity id order) → AI_HINTS > polylines_list HINT_POLYLINE, type AIH_SIEGE_{AREA,ENTRY,INTERSECTION,WALL_AREA}_NODE (FIRING_AREA, EXIT, SPAWN have no hint type), polygons = the node's ECRectangle corners (−w/2,−h/2), (−w/2,+h/2), (+w/2,+h/2), (+w/2,−h/2) through its transform, then each ECSiegeAIBoundary child's world polyline (Logical association, id order). Binary: ver 2, type, u32 polygon count, per polygon u32 point count + (x, y) floats, meta_tags (layout key `polylines_list>HINT_POLYLINE`). Edges (ECSiegeAIEdge) are not in the corpus. |
| Forest ambush hints | `ForestHints` (bob_tile run_bmd → QTU::procedural_forest_ai_hints → ai_hint_outlines_from_forest_blendmap): blend channels named "forest*", weights byte·(1/255) summed > 0.8 over the whole 1280² blend map; the nogo outline machinery on that bool field (min box 6, the three simplification passes) with cell = 2560/1280 and offset −256 + 0.5; each outline made clockwise, Sutherland–Hodgman clipped to [0, 2048]² (edges top, right, bottom, left; on-edge = outside), kept when area ≥ 200; appended to AI_HINTS > polylines after the layers' hints as AIH_AMBUSH_FOREST, meta_tags 0. Identical on the 3 forest tiles. |
| procedural bmd | Empty bmd (no META_TAG_KEYS, default playable area 64..1920) per climate of `climate_mask`. |
| bmd_nogo_data | `NogoOutlines`: no_go_outlines_from_heights on the Height TIF crop (Frida: the field is exactly `TerryTileProject.HeightField`, cell 2). Slope limit 30° (runtime global, Frida), normal y < sin 60°; 3-tap blur > 0.1; OUTLINE_CALCULATOR marching boundary (skips starts inside earlier outlines, drops boxes ≤ 6 cells); · cell size; three greedy simplification passes with shortcut-crossing checks. Decompiles in `Z:/Claude/BattleMaps/research/bob_re/bmd_nogo`, prototype `research/battle_build/nogo_outlines.py`. |
