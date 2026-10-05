# Native campaign build (BOB replacement)

Atlas3K rebuilds BOB's campaign-map outputs itself, straight from the assembly-kit sources. Intermediate files are
read from disk, so no pack import is needed between steps. Plan: `~/.claude/plans/we-have-a-bob-snazzy-valiant.md`.

## Running it

| Way | Command |
|---|---|
| CLI | `Atlas3K.Cli build-campaign [--map <map>] [--steps a,b] [--out <dir>] [--json]` |
| CLI | `Atlas3K.Cli diagnose-campaign [--map <map>]`: per-step readiness |
| CLI | `Atlas3K.Cli parity <builtDir> <referenceDir> [--mask-junk]`: byte comparison |
| MCP | `terry` server (`tools/terry_mcp/server.py`): `build_campaign`, `build_step`, `diagnose`, `parity_check`, `list_outputs`, `rebuild_tool` (prop tools below) |

- **Output location:** by default the output goes to `output/compiled/<map>/`, laid out like `working_data`: `terrain/campaigns/<map>/…` and `campaign_maps/<map>/…`.
- **Straight into the kit:** `--out <kit>/working_data`, or `to_working_data=true` in the MCP tools, writes into the kit and replaces BOB's files there.
- **Step order:** steps run in dependency order, and independent steps run in parallel. On dlc07 the whole native set takes about 24 s (global meshes 21 s, in parallel).

## Prop editing (AK layers)

The `terry` MCP server also edits the props in the kit's region layers (`<map>.<id>.layer`), the way the battlemap MCP drives Dungeondraft.

| Way | Commands / tools |
|---|---|
| CLI | `props-layers`, `props-list`, `props-get`, `props-models`, `props-ground`, `props-edit --ops <json>`, `props-undo`, `props-checkpoint`, `props-rollback`, `props-history`, `props-preview` (all print JSON) |
| MCP | `list_prop_layers`, `list_props`, `get_prop`, `list_prop_models`, `ground_height`, `edit_props` (batch), `add_props`, `move_props`, `transform_props`, `set_prop_properties`, `duplicate_props`, `delete_props`, `prop_checkpoint`, `prop_rollback`, `prop_undo`, `prop_history`, `preview_props` (returns the image), `rebuild_props` |

- **Code:** `LayerDocument` (Formats/Terry) edits single entities and writes Terry's exact layout. Loading and saving an unedited layer gives identical bytes; this is tested on all 265 dlc07 layers. `PropEditor` (Core/Editing) adds op batches, history, ground sampling and the region lookup. `PropPreview` (Core/Rendering) draws the previews.
- **Undo:** each batch snapshots the layers it touches into `output/prop_edits/<map>/` (a copy of the kit gets its own folder). Undo and rollback refuse to restore if a layer changed outside the tools since then.
- **Season variants:** these are separate props at one spot. `group: true` applies an op to all of them.
- **Ground height:** `ground_y` comes from the lf height TIF. Campaign relief such as mountains is made of props, so trees often stand above the lf ground. `snap: "relative"` keeps a moved object's height above the terrain.
- **Compiling:** edits reach `global_props.bin` only through `rebuild_props`, which runs the `global_props` and `camera_heightmap` steps.

## Steps

| Step | Replaces BOB action | Status | Parity (vanilla 3k_dlc07) |
|---|---|---|---|
| `rasters` | Height map compressed / DDS (land, sea), climate map | native | byte-identical |
| `tile_list` | Tilemap | native | **byte-identical to BOB on vanilla** (2026-10-04: `tile_list.bin`, and `global_map\` with it). Fixes: `TILE_DATABASE::sort` runs before link targets are loaded (all 0), so the DB order is area then name; `calculate_flow` neither flows nor queues a tile with no TLT_EQUALS entry link. main190 (BOB 2026-10-03): every record field identical; only low/high differ because that BOB run had no lf (all records +/-FLT_MAX sentinels). Evidence: Frida dumps `research/bob_re/frida_out`, `research/sim_first_divergence.py`, `research/tilelist_fields.py` |
| `global_map` | Global Mesh (`global_map\` part) | native | `global_blend.dds`, `texture_arrays.xml`, `global_map\tile_list.bin` byte-identical |
| `global_mesh` | Global Mesh (`land_mesh_N`, `sea_mesh_N`) | native (game-valid) | same mesh count and positions (170 land, 125 sea); holes identical (coverage IoU 1.0); land triangles 1.06× vanilla, sea 1.00×; surface-to-lf error equal to vanilla's (p99 ≈ 0.1–0.25); compressed-map holes agree on 97–99.7% of grid points |
| `rivers` | Terry file (river models, height patches) | native (game-valid) | same 24 rivers and numbering as vanilla (checked by shape); land-mesh river holes left uncovered: 78 px map-wide (vanilla 0, BOB 732) |
| `global_props` | Terry file (`global_props.bin`) | native (game-valid) | every vanilla prop present; tags, decal, snow/destruction/shroud flags 100%, seasons 99.9%, season bucket 99.9%, quadtree cell 92.8% (with model radius; since 2026-10-04 cells use position only, see below); 8,420 bodies (vanilla 8,891). main190 checked in game 2026-10-04 |
| `camera_heightmap` | Generate Camera Height Map | native (close, not byte-identical) | correlation 0.94, 73% of pixels within 0.1 units |
| `trees` | Campaign Trees (`trees.campaign_tree_list`) | native | byte-identical when the CampaignTree map is the one decoded from vanilla (`trees-decode`) and heights are reused; heights from lf alone: 61% bit-exact, 98.9% within 1e-5 |
| `lookup` | Texture / Convert lookup texture | native | byte-identical to BOB (vanilla's minimap differs in 304 bytes because of CA's own file) |

## main190 in-game test (2026-10-04)

The first in-game test of a native main190 build (`output/compiled/main190_native_20261004b`, 223 s against about 20 min
through BOB) showed **empty rivers** and **missing northern mountains**. A/B packs (native with BOB file groups swapped
in) traced both to `global_props.bin` alone. Fixed in `GlobalPropsBuilder` and `BmdRecords`:
- **River records:** byte 91 (`PropRiver`) = 1, cast shadow on, season bucket 16, as vanilla and BOB. Without byte 91 the
  game culls the river water.
- **Quadtree cell:** by position only (radius 0). BOB's main190 cells match a radius-0 point for 92% of objects; the model
  radius put mountain props in much coarser cells, and the game didn't draw them.
- **Bucket references** in the cell bodies: campaign mask 0 (was 1), as vanilla and BOB.

After the fix both render in game. Other findings from the comparison:
- **BOB tile heights:** BOB's main190 `tile_list.bin` stores +/-FLT_MAX ("unset") low/high on every record, while vanilla
  stores real heights. Writing the sentinel into the native lists made no difference in game.
- **tile_list height source:** it now reads the .terry's lf maps, the same as `rasters`. The kit's `lf_heights.tif` was stale
  (main190 `ranges_relief.py` only edits the `.height` tif).
- **Open:** native land meshes cover about one cell more than BOB at road/river/coast hole rims
  (`TileCoverage.Covered`'s diagonal probes and far-edge test).
- **BOB threads:** BOB's "Enable multiple threads in processing" preference doesn't speed up Tilemap; it runs on one core
  either way.

## main190 check (2026-10-02)

`3k_190e_expanded_map` (1478×1133 hexes, assembly_kit_190E) was built natively in 231 s into `output/compiled/main190_native`.
- **Inputs:** a staging copy of the kit, `output/stage_main190_native`. It uses the tile map BOB ran on (`output/backups/main190_holes_20261002_150202`) and `--accept-tilemap layout.mesh_columns`.
- **Reference:** BOB's 14:20–14:33 outputs in the kit's working_data.
- **Script:** `research/native_vs_bob.py`; the full output is in `output/main190_native_vs_bob.txt`.

| Output | Native vs BOB |
|---|---|
| tile_list | 383,440 vs 383,410 records; header identical; 97.9% same tile at the same place, 88.4% identical records; holes 145 vs 144 points, 141 shared |
| global_map | `global_blend.dds` and `texture_arrays.xml` byte-identical; the `tile_list.bin` copy differs (same differences as tile_list) |
| global_meshes | 184 land / 126 sea meshes, same as BOB; not byte-identical (expected) |
| rivers | 24 rivers / 48 model files, same as BOB. Height patches: 108 vs 85 files, because the native tiling per river is wider |
| global_props | 66,271 vs 66,268 objects; model + position 100%. Region: 100% (331 regions, same set as BOB) since the fix below. It was 67.7% while the step used layer names. River models are numbered differently (see the regions note), but each river entity gets BOB's region |
| lookup | `.dds` and `.tga` byte-identical; `_minimap.tga` differs in 6,959 of 3.88M bytes |
| rasters, climate | byte-identical to the kit's copies, but those were built natively too, so there is no BOB reference |
| camera_heightmap, trees | no BOB output in the kit to compare against |

## Guandu check (2026-09-29)

The full native build of `3k_guandu_map` takes 37 s, into `output/compiled/3k_guandu_map`. Against your BOB v3 build:

| Output | Result |
|---|---|
| Global meshes | same count (154 land, 73 sea) |
| Rivers | same count (20) |
| Props | 40,352 against BOB's 40,339 |
| Prop regions | same as BOB for 98.6% of objects |

**Not yet checked in game.**

## Format notes

### global_map

- **`global_blend.dds`:** DDPF_RGB, 16-bit, R mask 0xFF, G mask 0xFF00. dwFlags, pitch and caps are all 0.
  - Byte 0 is the palette index from the blend TIF.
  - Byte 1 is `climate_map.cm` repeated 4×4 (0 cold, 1 arid, 2 temperate, 3 sub_tropical).
- **`global_map\tile_list.bin`:** the root file with record byte +12 cleared from 07 to 00 for base tiles (generic, generic_sea, sea_coast, mountains_*). Linear features (rivers, roads, cliffs, canals) keep 07.
- **`texture_arrays.xml`:** the same on every map.

### Lookup textures (`*lookup*.bmp` → `.tga`, `.dds`, `_minimap.tga`)

- **Palette:** unique colours in first-appearance order, scanning the BMP from the top.
- **TGA:** colour-map type 1, image type 1, first-entry field 18, 32-bit BGRA entries with A = 255, 16-bit indices stored top row first, no footer.
- **DDS:** DX10 header, R16_UNORM (DXGI 56), depth 1, 1 mip.
- **Minimap:** `indices[::4, ::4]` with the same palette.

### Meshes (`RigidModelV2`)

- **Layout:** RMV2 v8, 1 LOD, 1 mesh.
  - Land/sea: material 101, 16-byte vertices.
  - River: material 68, 48-byte vertices, 860-byte material block.
- **Header bytes that aren't real data:** vanilla carries the same values in every file of a kind, and the writer hard-codes them.
  - Land: 0xA4..A7 = 0, 0xE8..EF = 0.
  - Sea: 0xA4 = `00 41 0c c9`, 0xE8 = `b0 a0 19 c9 fd 7f 00 00`.
  - River: 0xA4 = `00 ff ff ff`, 0xE8 = `a5 70 cf 28 fa 7f 00 00`.
  - Rivers also have 2 uninitialised bytes at 0x31A that differ per file. They're written as 0 and masked by `parity --mask-junk`.
- **Bounding box:** BOB's box for land/sea tiles is the **whole tile rectangle** in x/z (`col × 37.19375` computed in double, then cast to float) and the vertex extent in y.
- **Mesh layout** (Phase 2 findings so far):
  - Surface triangles come first as fans over merged polygons, which are mostly rectangles: 1×1 up to 7×2 cells.
  - Vertical skirt triangles come last.
  - Vertices are appended in the order the merged polygons are visited.
  - Winding is clockwise seen from above.
- **River `.wsmodel`:** 2-space indent, CRLF, no trailing newline. The material differs per river.

### Global meshes (`GlobalMeshBuilder`)

The decompiled algorithm is written up in `docs/bob_re_global_mesh.md`. Native version, game-valid:

- **Tiling:** square meshes of (int)(maxTiles × 0.125) cells, 2 cells per tile-map pixel. They're visited south-west first, row by row, and empty ones are skipped.
- **Heights:** `LfSampler` gives BOB's bilinear lf sample, (l × 5500 − 1200) × tile/128.
- **Holes:** `TileCoverage` works from the placed tiles, with masks and orientation, plus ±0.001 diagonal probes. Tile categories:

  | Category | Feeds |
  |---|---|
  | `river*`, `roads_*`, `canal*` | neither (holes) |
  | `generic_sea`, `river_mouth`, `blockout_cliff*` | sea |
  | `sea_coast` | both |
  | everything else | land |

- **Vertex flags:**
  - 0 near holes.
  - 0 on mesh seams.
  - 3 on map edges.
  - 2 elsewhere.
  - Sea meshes also pin every 4th row and column.
- **Decimation:**
  - Normalised Sobel normals.
  - `TriangleMerger` (factor 0.9999, 10 passes, limit growing by 6.4).
  - Winding flipped, then first-use renumbering.
- **Skirts:** double-sided quads 1.0 below boundary edges next to holes or the map edge.
- **Land compressed map:** the final surface rasterised onto the grid, with header (0, −50, 0, 0, max, 0) and 0 = hole.

### Rivers (`RiverBuilder`)

- **Source:** every `ECRiverSpline` entity in the AK layers. The river number comes from the entity name (`river_N`), the numbering vanilla and the renumbered `global_props.bin` use.
- **Curve:** a chain of cubic Béziers, (p_i, p_i + tangent_out, p_i+1 + tangent_in, p_i+1), placed by the entity transform and sampled every `spline_step_size` along the arc.
- **Cross-sections:** 5 vertices each, at −w/2, −w/4, 0, w/4 and w/2.
  - **Width margin:** width × 1.15, with both ends pushed out by w/2, so the water covers the tile-based land-mesh holes. The extra water sits under the higher banks.
- **Vertex, 48 bytes:** position relative to the pivot, then 1, then v = 0.1 × lateral offset, then u = 0.1 × arc length, then world uv = (x/595.1, z/541.79) scaled to the map, then packed normal (up), tangent (downstream) and bitangent (across), then 4 zero bytes. The bounding box is in world coordinates.
- **Height patches:** the water surface rasterised at 16 px per unit into 32-unit blocks (512², row 0 = south), header (0, −50, 0, 0, max, 0), 0 = no water. They're named `river_N_patch_<dx>x<dz>` by pixel offset from the river's first block, and listed in `rivers.height_patch_collection` with their world rectangles.

### global_props.bin (`GlobalPropsBuilder`)

**Layout**, recovered from vanilla and the decompiled serializers (`research/bob_re/bmd_fields`, `bmd_export`):
- **Regions:** BOB puts every object in the region of the map.hex hex under its entity's ECTransform position, whichever layer it came from.
  - The lookup is a port of bob_terrain `FUN_18005fe10`, in `HexRegionLookup.cs`.
  - Grid geometry: flat-top hexes of radius R = (2/3)·(maxx − minx)/(columns − 1) over the map bounds, odd columns half a hex north. There is a corner test at the slanted edges, and the maths is in float32.
  - The bounds come from the map's `campaign_map_playable_areas` row; BOB reads them from map_data.esf.
  - For river models (placed at the origin) the position is the ECRiver entity's transform.
  - Without a map.hex the step falls back to the layer name. A layer whose name isn't one of the map's regions goes to `3k_main_reg_non_playable`.
  - Checked on main190: 66,268 of 66,268 objects get BOB's region. On vanilla, 99.99% get CA's; the exceptions are the 24 duplicate river-model props that the converted kit layers carry at the origin.
  - **River numbering:** BOB numbers `models/river_N` by ECRiver entity id, descending. The native rivers step numbers by entity name instead, which matches vanilla's numbering on the vanilla layer. Models, height patches and props agree with each other either way.
- **Cells:** 7 quadtree levels, each a row-major 2^L × 2^L grid over the world (595.1 × 541.79 scaled to the map; row 0 = north). Cell id = the number of cells in the shallower levels + row × 2^L + col. An object goes to the deepest cell that holds its bounds. The native builder uses the model's LOD0 radius; rivers and polygon meshes go in cell 0.
- **Season buckets:** 16 + bits (spring 1, summer 2, autumn 4, winter 8; harvest adds none). No season mask = 31.
- **Files:**
  - `bmd_objects.<region>.<cell>.<bucket>.bin` holds the objects.
  - `bmd_objects.<region>.<cell>.bin` holds nested references to its buckets (campaign mask 1).
  - `bmd_objects.bin` (the root) holds nested references to every cell body, with the region key.
  - Entry order: each cell's buckets, then the cell; the root comes last.

**Round trip:** `BmdBody` parses every section into raw records, and all 8,891 vanilla bodies re-encode byte for byte.

**Record templates:** new records start from vanilla's most common record of each type (read from `global_props.bin` in the game packs), with the layer's fields replaced:
- path, transform, meta tags (flags plus a mask covering whole enum types) and season mask
- snow, destruction and shroud visibility
- decal, apply-to-terrain and apply-to-objects
- cast shadow and height-patch flags
- light, sound and probe parameters

**One preamble:** every body lists every vanilla enum type.

**Object sources:**

| Layer entity | Becomes |
|---|---|
| `ECPropMesh`, `ECDecal` | props |
| `ECRiver` | `models/river_N.wsmodel` prop at the origin |
| `ECVFX` | VFX |
| `ECPointLight` | point lights |
| `ECCompositeScene` | composite scenes |
| `ECSoundMarker` | sounds (+ `ECPointCloud` → multi-point) |
| `ECLightProbe` | light probes |
| `ECPolygonMesh` | polygon meshes (ear-clipped) |

Tags come from the tag layers (`ECLayerExportTags`) linked through the Logical association.

### trees.campaign_tree_list (`CampaignTreeGenerator`)

Decompiled from `QTU::CampaignTreeGenerator` / `generate_campaign_tree_list_for` (qttoolutility) and `EMPIREUTILITY::CAMPAIGN_TREE_LIST::add_tree` / `write` (empireutility). Notes in `research/bob_re/trees*`, prototype in `research/trees/`.

- **Grid:** the campaign hex grid from `map_data.esf`: n columns (892 on dlc07 = tree map width / 2), rows = tree map height / 2 (702). Hex size s = (2/3) / (n − 1) × world width, columns 1.5·s apart, rows √3·s apart, odd columns half a row north. World height = (rows + 0.5) × row step (541.7862). All float32 in BOB's order.
- **One tree per hex:** BOB samples the AK CampaignTree map at pixel (2·col, H − 2·row − 1 − (col & 1)), y = 0 the top row. Palette index 19 (no tree), or a colour with no `campaign_tree_ids.colour_hex` match, means no tree.
- **RNG:** `std::minstd_rand` (× 48271 mod 2³¹ − 1) seeded with ((row << 16) | col) mod (2³¹ − 1), 0 → 1. Draws, in order:
  1. tree id among that colour's ids, sorted ordinally (MSVC `uniform_int_distribution`: 30-bit draws, values > 0x3FFFFFFF rejected; no draw for a single id)
  2. z jitter, then x jitter: `generate_canonical<float>` = (e − 1) / 2³¹, × 0.4 − 0.2
  3. rotation index 0..5 (`uniform_int`)
- **Position:** z = ((0 + row·dz [+ dz/2 if col odd]) + jz·0.4) − 0.2, x = ((jx·0.4 − 0.2) + col·dx) + 0.
- **Height:** `TerrainSurface::Object::height_split`: the max over covering tiles of `TERRAIN_RENDER_SETUP::get_height` at (x, z / 1.15476) in tile space (extent = tiles × 595.1/1784), split (total − lf, lf) and summed. lf alone gives 61% bit-exact, 98.9% within 1e-5; the rest is river/road/canal hf. 2026-10-04: a float32-exact port of BOB's sampler (`FUN_18039eea0`: corners int(fx), int(fx)+1, int(fy)-1, int(fy)) and every bounds / scale representation tried stay at 60.83% (`research/trees/lf_exact.py`, `lf_bounds_search.py`, `lf_scale_search.py`); the misses are 1-4 ulp, 77% negative, so they are a small per-tile hf term (`get_high_frequency_height_new` / `get_tile_hf_height_raw_data`) present even on base tiles, not sampler rounding. Next: port the tile hf or dump it with Frida from Terry's tree export (BOB's Terry file action does not build trees). The native step reuses the reference list's y wherever the regenerated (x, z) is bit-identical.
- **Seasons:** each variant row sets its season's model (later rows win; no/unknown season = default model). Written: the `seasons_tables.index` of each season with a model, ascending, then 0xFFFFFFFF if the default model is set. Flag byte is always 1.
- **Type order:** a CA_STD hash map keyed by `CA::murmur_hash` (= MurmurHash3 x86_32, seed 0x4A545EED). Starts at 1 bucket, grows to 2b + 1 when count + 1 > b; new keys are appended to their bucket; a rehash re-buckets in list order. The file lists types in that list order, inserted in row-major first appearance (`CaHash.HashMapOrder`).
- **Header:** version 5, world bounds (0, 0, width, height), type count.
- **Reverse:** `Atlas3K.Cli trees-decode [--list] [--out]` maps a compiled list back to hex colours and heights, checks that regenerating is byte-identical, and writes the AK CampaignTree TIF (1784 × 1405, 2×2 px per hex, palette = sorted DB colours, 19 = no tree).
- **Vanilla AK caveat:** neither the kit's `3k_dlc07_main_map.tree.*.tif` (no trees) nor `tree_new` (90% of hexes) reproduces the shipped list. Use the decoded TIF.

### camera_heightmap.png

- **What the game needs:** `empirecampaign.dll` loads `campaign_maps\<map>\camera_heightmap.png` and requires the tEXt `height_scale`.
- **Format:** 16-bit greyscale at tile-map resolution. Values are normalised to the highest sampled height; `height_scale` = highest / 65535, written with 6 decimals.
- **BOB's generator:** `TOOLDATABUILDER::generate_camera_height_map`. Its settings are samples per world unit, resolution relative to the tile map, and an optional blur (kernel size, sigma).
- **Native version:**
  - Terrain is taken as max(lf height, 0) in world units (u16 × 0.000218712 − 3.12725).
  - Every non-decal prop's LOD0 mesh from the game packs is rasterised at lf resolution, including `.wsmodel` → geometry.
  - The result is reduced by a 4×4 maximum, with no blur.
- **Remaining gap:** vanilla is up to about 10 units higher over the mountain ranges than the current props explain. This is still open; a BOB run on dlc07 with the same inputs is needed to tell whether the gap comes from CA's shipped file.

### lf_normal.dds

Not needed for campaign maps. dlc07 ships none, and the game uses the file as the battle resource `RC_BATTLE_TERRAIN_LF_NORMAL`.

## Code

- **Formats** (`src/Atlas3K.Formats/`):
  - `Models/RigidModelV2.cs`: terrain-tile and river RMV2 writer.
  - `Models/RigidModelGeometry.cs`: any RMV2, positions and indices for one LOD.
  - `Models/WsModel.cs`
  - `Maps/TileList.cs`, `Maps/LookupTexture.cs`, `Maps/HeightPatchCollection.cs`, `Maps/Png16.cs`
  - `TerrainDds.WriteBlend`
- **Core** (`src/Atlas3K.Core/Campaign/`): `CampaignBuildPipeline`, `BuildSteps` (rasters, global_map, lookup, pending steps), `CameraHeightmapStep`, `Parity`.
- **Tests:** `src/Atlas3K.Tests/CampaignBuildTests.cs`.
- **Research:** `research/derived_maps/` holds the camera heightmap and lf_normal analysis and the mesh study. Ghidra decompiles of the kit DLLs are in `research/bob_re/`. Ghidra and JDK 21 are installed portably in `Z:\Claude\Tools`.
