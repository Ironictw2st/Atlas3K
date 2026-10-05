# 3K campaign tile database: compiled FASTBIN0 layout

Parser: `research/tiles/tiledb.py`. All 544 `tiles/*.bin` files and `_settings.bin` parse to exactly EOF.
Serializers come from `warscape.modder.x64.dll`. The decompiled C is in `research/bob_re/tiledb`, `tiledb2`, `tiledb3` and `tilematch`.

## Encoding

* The file starts with the 8 bytes `FASTBIN0`. After that come raw little-endian values with no names or type tags. `FUN_1802b9650` only switches to tagged reads for the `SAFEBIN` magic, where `FUN_1802c7fa0` checks the type code and name of each field.
* Each struct starts with a u16 `serialise_version`, read by `FUN_1802b77a0(maxver)`. The gates below use `v`, the stored version. `FUN_180215110` returns it.
* Each array is a u32 `size` followed by its elements (`FUN_1802cda50(..,"size",..)`). The name strings for arrays and child structs (`CLIMATES`/`CLIMATE` and so on) only matter in SAFEBIN.
* Primitive types are listed by their type code in `FUN_1802c7fa0`:

| code | type | reader | used by |
|---|---|---|---|
| 1 | bool, 1 byte, raw copy, tested `!=0` | FUN_1802cdba0 -> FUN_1802b4f40 | flags |
| 2 | u8 | FUN_1803f81e0 | byte colours in newer versions |
| 5 | u16 | FUN_1802cd9b0 | serialise_version |
| 6 | u32 | FUN_1802cda50 | size, width, height, blend_size, tri density |
| 7 | i32 | FUN_1802cda00 | link and target x/y (-1 occurs) |
| 8 | f32 | FUN_1802cdaa0, FUN_1802b5280 (wrapper) | floats |
| 9 | string = u16 len + bytes | FUN_1802cdaf0 | strings, masks, enum strings |

* vec3 = 3 f32 (`FUN_1802b5350` r,g,b; `FUN_1803d4ee0` x,y,z).
* "rgb" in older versions is 3 f32 (`red`,`green`,`blue`) that the engine casts to bytes. In newer versions it is 3 u8. Every vanilla file uses the f32 form.

## _settings.bin: TILE_DATABASE (`FUN_1803c2070`, called from `TILE_DATABASE::load_binary_new`)

```
u16 v (=1)
RENDER_PARAMS      FUN_1803c4fe0  (max 13, file 13)
CONVERSION_PARAMS  FUN_1803c48d0  (max 4,  file 4)
CLIMATES  array of CLIMATE   FUN_1803d97c0 -> FUN_1803c43c0
TILE_SETS array of TILE_SET  FUN_1803d9e00 -> FUN_1803c5a50
(TILES: FUN_1803db390 enumerates tiles/*.bin; nothing is stored in this file)
```

**RENDER_PARAMS** (FUN_1803c4fe0). All fields are f32 unless marked otherwise.
`v`, lf_height, [v>6] alt_lf_height, hf_height, blend_pixel_scale, unit_scale, mid_distance_detail_scale, mid_distance_detail_strength, mid_distance_normal_strength, mid_distance_detail_near, [v<11] mid_distance_detail_far (read and discarded), mid_distance_detail_slope_low, mid_distance_detail_slope_high, vertical_offset, normal_lf_scale, normal_tile_scale, normal_terrain_scale, [v>2] blend_contrast, [v>2] layer_exempt_0..3 (strings), [v>3] campaign_sea_transparency_scale, campaign_sea_uv_scale, [v>5] near_distance_detail_distance, near_distance_detail_scale, near_distance_detail_strength, mid_distance_detail_near_lq, [v>7] grass_normal_scale, [v>8] near_distance_normal_strength, near_distance_detail_slope_low, near_distance_detail_slope_high, [v>9] fog_of_war_params struct, [v>11] far_terrain_mid_distance_colour_strength, far_terrain_mid_distance_normal_strength, far_terrain_mid_distance_material_strength, [v>12] lf_terrain_z_scale_factor.

**fog_of_war_params** (FUN_1803c4b50, max 6). `v`, fog_of_war_brightness, fog_of_war_saturation, then:
* [v>1] shroud_cel_steps (u32), followed by 19 f32: shroud_cel_offset, _strength, _blend, shroud_edge_depth_bias, _depth_scale, _normal_bias, _normal_scale, _pillow, _blend, discovered_shroud_brightness, _saturation, undiscovered_shroud_brightness, _saturation, shroud_edge_noise_uv_scale, _noise_strength, _brightness, _ink_uv_scale, shroud_lerp_time, shroud_terrain_detail_factor
* [v>2] shroud_edge_kernel_size, shroud_ssao_strength
* [v>3] discovered_shroud_border_brightness, _saturation
* [v>4] discovered_shroud_border_alpha
* [v>5] shroud_fade_in_out_alpha

**CONVERSION_PARAMS** (FUN_1803c48d0). `v`, [v>1] use_placement_groups (bool), triangle_density (u32), max_lf_heights_per_pixel (u32), [v>1] shadow_mesh_angle (f32), triangle_decimation_size_factors0..5 (f32), triangle_decimation_angle_factors0..5 (f32), [v>2] land_colour, sea_colour, nogo_colour (vec3 f32).

**CLIMATE** (FUN_1803c43c0, max 8, file 7).
* `v`, name, [v<6] texture_set (string), rgb ([v<8] 3 f32, else 3 u8)
* TEXTURES array of TEXTURE (FUN_1803d51a0 -> FUN_1803c46d0). The array is empty in vanilla.
* [2<=v<=3] grass_alpha_add, grass_alpha_mul (f32)
* [3<=v<=4] destruction_climate (string)
* [v>4] vampire_creep_climate, chaos_creep_climate (strings)
* [v>6] grass_mid_distance_colour_saturation (f32)

Climate index is its array order: 0 cold (0,85,85), 1 arid (255,170,0), 2 temperate (0,85,0), 3 sub_tropical (170,170,85).

**Climate TEXTURE** (FUN_1803c46d0, max 9; the engine rejects v<=5). `v`, name, [3<=v<=6] mid_distance_strength, [v>=7] mid_distance_colour_strength, mid_distance_normal_strength, blend_pixel_scale, [v>=2] outfield_blend_pixel_scale, [v>=6] near_distance_strength, [v>=8] mid_distance_colour_saturation, [v>=9] mid_distance_material_map_strength.

**TILE_SET** (FUN_1803c5a50, max 3, file 2). `v`, name, linking_tile, shared_geometry, also_place_tile_set, link_as_set (all strings), rgb ([v<3] 3 f32, else 3 u8), [v>1] exclude_from_global_mesh (bool).
* There are 27 sets. The id is the array index, e.g. 0 generic (150,170,100), 1 river (0,0,255).
* `post_load_fixup` stores `index | 0x80000000` in tile set +0x10.

## tiles/*.bin: TILE_DATABASE_TILE (`FUN_1803c5550`, max 7; files: 540 at v6, 4 at v5)

```
u16 v
[v<2]  location            string
[v>1]  name                string   (file stem == tile_set + "_" + name)
       tile_set            string   FUN_1803da770 -> TILE_DATABASE::string_to_tile_set
       mask                string   FUN_1803dab50 -> TILE_DATABASE_TILE::string_to_mask
[v>5]  nogo                string   same mask converter (empty in all vanilla files)
       width, height       u32      in tile-map pixels
       rgb                 [v<7] 3 f32 red/green/blue, else 3 u8   (0,0,0 in almost all files)
       requires_infield_lodding  bool
       random_rotatable          bool  (true on all 544)
       custom_alpha_blend_texture string
       scalable                  bool  (178 files hold garbage bytes; engine semantics != 0)
       encampable                bool
       custom_blend_tile         string
[v<4]  TEXTURE_GROUP: red, green, blue, alpha strings
       VARIATIONS        array of VARIATION        thunk FUN_1803d89f0 -> FUN_1803c5c70
       TILE_LINK_TARGETS array of TILE_LINK_TARGET FUN_1803d81b0 (inline)
       TILE_LINKS        array of TILE_LINK        FUN_1803d7b70 -> FUN_1803c24c0
[v>2]  barbarian   bool
[v>4]  use_alt_lf  bool
```

The serializer writes link targets before links, even though the in-memory order is links at +0x50 and targets at +0x60.

**mask** is a string of `'0'`/`'1'` characters, length width*height, in row-major order. Index `width*y + x` comes from `subtile_masked_valid`, which treats an empty mask as all valid. 262 tiles have a mask.

**VARIATION** (FUN_1803c5c70, max 10; files: 540 at v9, 4 at v8).
* If v<5: [v>1] TEXTURE_GROUP (red, green, blue, alpha strings), location, [v>2] name, min_height, scale, normal_strength, overlap_border_size (f32), raw_data_tri_density (u32), blend_common, index_common, normal_common (strings), red, green, blue (f32), [v>3] requires_sea_in_infield (bool).
* If v>=5: texture_set struct, location, name, min_height, scale, normal_strength, overlap_border_size (f32), raw_data_tri_density (u32), blend_common, index_common, normal_common, rgb ([v<10] 3 f32, else 3 u8), requires_sea_in_infield (bool), [v>5] shadow_camera_depth (f32), [v>6] enable_sea_water_plane (bool), [v>7] is_subterranean (bool), [v>8] fog_mask (string).
* `post_load_fixup` fills in the name from the location when it is empty. It also checks that `<location>custom_mesh.rigid_model_v2` and `<location>/blend0.dds` exist.

**texture_set** (FUN_1803c1690, max 2). `v`, [v>1] faction_key, red0, green0, blue0, alpha0, red1, green1, blue1, alpha1 (strings). These are blend-layer texture names: `climate` means "use the climate's texture", and other values are named sets such as `arid_1`, `imperial_road`, `blockin_12`.

**TILE_LINK_TARGET** (in FUN_1803d81b0). `v` (1), tile_set (string, via string_to_tile_set), x (i32), y (i32). Accessors: target_set, target_point.

**TILE_LINK** (FUN_1803c24c0). The fields are:
* `v` (1)
* link_set (string -> tile set)
* x, y (i32): link_point
* base_x, base_y (i32): base_point
* is_entry (bool)
* blend_quad: an array of "point" (3 f32 x,y,z, FUN_1803d9020 -> FUN_1803d4ee0); always empty in vanilla
* blend_size (u32)
* no_offline_blend (bool)
* test (string)

`test` is converted by TILE_DATABASE_TILE_LINK::string_to_enum. Values seen: `TLT_EQUALS` (886) and `TLT_NOT_EQUALS` (232).

## Vanilla observations

* There are 353 tiles with links (1118 links, 843 link targets in total). blend_size is 1 or 64, is_entry is true on 320 links, and no_offline_blend is always false.
* Each tile has exactly 1 variation. No variation carries a per-climate colour: variation rgb is (0,0,0) everywhere and there is no climate field. Climate dependence goes through `texture_set` layers named `climate`.
* also_place_tile_set is set on river_mouth, sea_coast, blockout_cliff and blockout_cliff_ends (all -> generic_sea), and on sea (-> beach).
