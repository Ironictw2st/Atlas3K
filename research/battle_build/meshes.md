# Battle tile meshes: native vs BOB (worker B, 2026-10-06)

To be merged into `docs/native_battle_build.md`. Steps: `src/Atlas3K.Core/Battle/Build/Meshes/` (`tile_meshes`, order 200;
`river_meshes`, order 210). Test: `BattleTileMeshTests` (all 5 corpus projects).

## Status (battle-parity corpus, bob_run1)

| File | Status |
|---|---|
| `shadow_mesh.rigid_model_v2` | identical, 5/5 |
| `outfield_mesh.rigid_model_v2` | identical / masked-identical (LOD u32 0xA4..0xA7), 5/5 |
| `mesh.rigid_model_v2` | identical / masked-identical, 5/5 |
| `river_mesh.wsmodel`, `outfield_river_mesh.wsmodel` | identical, 5/5 |
| `river_mesh.wsmodel.rigid_model_v2`, `outfield_river_mesh.wsmodel.rigid_model_v2` | identical (no river) / masked-identical (dfe064a6, df46bdbc: + material u32 0x318..0x31B) |
| `*.agf` | not BOB output: asset-graph files of an old build (`load_asset_graph=0`); dropped |

Not covered (same BOB action, other families): `hf_height_map` / `hf_water_map.compressed_map`, `normal.dds`,
`bmd_nogo_data`.

## Where it comes from

"TerryTile / Process Terry tile (heightmap)" = bob_tile `ACTION_TERRY_TILE_HEIGHTMAP::run` →
`TOOLDATABUILDER::process_tile_internal` (tooldatabuilder 0x1800d76a0). Per output, `FUN_1800edbf0(ctx, mode, mesh path,
river path, hf path, write hf, ...)`: shadow (mode 2), then for `requires_infield_lodding` tiles (Terry's
`infield_tile`) outfield (mode 1) and mesh (mode 0). Each: `FUN_1800d9c60` builds the TILE_OUTPUT_DATA,
`MODEL_PROCESSOR::open_height_map` + `write` the RMV2; `FUN_1800d98c0` / `open_river_spline` the river model.
Decompiles (CA code, not in the repo): `Z:\Claude\BattleMaps\research\bob_re\tile_mesh`, `tile_mesh2`, `tile_mesh3`,
`tile_action`.

BOB settings (bob_tile FUN_18001ac60, defaults used): `DisableMeshOptimisation` (false), `DisableProtectionMap` (false),
`infield_fixed_vertex_interval` (16), `outfield_fixed_vertex_interval` (0x800).
Battle tile database (`terrain/tiles/battle/_tile_database/_settings.bin`, fast.pack): triangle_density 128,
shadow_mesh_angle 90, triangle_decimation_angle_factors0 20°, render_params.unit_scale 2.

## Rules (each one checked against the corpus)

| Part | Rule |
|---|---|
| Height field | warscape `load_and_process_height_map`: the Terry Height TIF (float32, 1280² for 8×8 at density 128) minus a border: size W − (2·density − 1) = 1025, sample (r, c) = TIF[r + density + 1, c + density + 1]. No flip. (A per-pixel scale field multiplies it; 1 on every corpus tile.) |
| Grid | vertex r·W + c = (c·f, h, r·f), f = 128 / density. Mesh step 1; outfield and shadow step 16 (lod shift (density == 128) + 3). Quads [a, b, c] [b, d, c], a = (r, c), b = (r+s, c), c = (r, c+s); the last quad of a row/column stretches to the edge. |
| Flags | 0 if the ±step neighbourhood leaves the tile cells (`FUN_1800e01e0`: floor((c ± s)/density), floor((r ± s)/density) inside width × height): the borders and, at step 1, the second-to-last row/column; then the fixed-vertex lattice (16, or 2048 for outfield) and corners → 0; edge lattice (8 / 2048) → 0; other edge → 3; else 2. Protection map > 0.5 → 0 (mesh only, row-flipped index; all corpus maps empty). |
| Normals | `FUN_180147380`: the campaign Sobel (÷8, clamped) with up = 1 / normal_strength. |
| Skirts | `FUN_1800dcf00` (unmasked branch): top, bottom, left, right edge rows copied 10 lower (fringe marker +0x78 = 1) and stitched with two triangles per step; flags 1 on the lattice / at corners, else 4. The masked branch (per-cell skirts) is not ported: no corpus tile is masked. |
| Merge | campaign `TriangleMerger` with span 120, height tolerance 3, factor cosf(20° · 0.017453292) (`process(factor, 120, 3, flags)`). Skirts and edges never collapse (vertical skirt triangles are slivers in x/z). |
| Clean / split / sort | first-use renumbering, MESH_SPLITTER (65,000), "Sort fringes" = stable partition of triangles touching a skirt vertex to the end. |
| Shadow | mode 2 keeps triangles whose face normal is steeper than shadow_mesh_angle (90°): none on a height field, so an RMV2 with 0 LODs (140 bytes). |
| RMV2 | material 96, render flags 0, 8-byte vertices (BOB float→half of x, y, z; w 0), each triangle's first two indices swapped, bounds = float min/max of the vertices. Shader block "rigid_default" + 0x8D at 15, 9E D4 at 24. Material block: "TerrainBase0" (64 bytes), then u32 1024, 1024, field width (1025), LOD count 1, 16, index count before the fringes. |
| Rivers | `FUN_1800d99e0` per ECRiverSpline of the tile's layers (`<project>.<ECLayerFile id>.layer`, recursively) = the campaign `BobRiver` chain (spline, FUN_18015e9e0, snap pass, cleaner, splitter) in the layer's own coordinates, world uv over (0, 0)..(tiles · unit_scale · 128); `FUN_180146460` then divides x and z by unit_scale (2) before the pivot (bounds centre, unscaled) is subtracted. Outfield and infield river files are the same model. wsmodel: LF, no final newline, the river's material or the project's `river_material`, `<materials/>` without rivers. |

## Open

- Multi-river tiles: each river is written as one mesh of LOD 0 (one `FUN_1800d99e0` call each); no corpus tile has
  two rivers to confirm the part order.
- Masked tiles (`cells/mask`): the per-cell skirt branch of `FUN_1800dcf00` and the masked validity paths are not ported.
- Protection map (buildings): its generation (TerryTile "excluding heightmap", `debug_protection_map.png`) is not ported;
  every corpus map is empty, so it is passed as none.
- Tiles at another density or size than 128 / 8×8: the code follows the decompile, but only 128 / 8×8 is in the corpus.
