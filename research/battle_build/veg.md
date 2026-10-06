# Battle procedural vegetation (procedural bmd + tree lists)

Native step `procedural_vegetation` (src/Atlas3K.Core/Battle/Build/Bmd/ProceduralVegetationStep.cs, order 321, after the
old empty-bmd step `procedural_bmd` whose files it overwrites). Rows for docs/native_battle_build.md:

| File | Status (bob_run1) |
|---|---|
| `<climate>_procedural_bmd_data.bin/.xml` | identical on all 8 corpus projects (10 climates; trees, 1,138 props, vfx; round 1 empty) |
| `<climate>.tree_list.bin/.xml` | identical on all corpus projects that place trees (5a2e0001 temperate, 5a2e0002 cold, 5a2e0003 arid / subtropical / temperate / tropical); none written on the round-1 projects, as in BOB |

## How BOB does it (bob_vegetation FUN_180007630 → qttoolutility QTU::ProceduralTerrainContent::generate)

- Parameters: every `battleterrain/vegetation/*tree_parameters.xml` (data/vegetation.pack), parsed with calibs
  `CA::UniString::parse(float&)` (digit accumulation in float, fraction digits · 0.1f^k: "0.9" = 0.90000004), ranges
  normalised by FUN_1800723d0, each group's object probabilities scaled so the maximum is 1 (FUN_180072430). A comment
  ends at the first `-->` (sbt_grass0 nests one).
- Compiled tables (FUN_1800855c0): category objects sorted by (group, model) bytes; groups with objects and a tile
  texture sorted by (channel, name); group runs copied to the front; 20-byte groups (FUN_1800d7660), 12-byte objects
  (FUN_1800c64d0); grid spacing 1/√(max trees per m²), origin (W − (n−1)s)/2.
- Maps: composited Height = the height TIF; Blend8 = byte/255, channel 0 += 1 − Σ (float, channel order).
- generate: std::mt19937 (vegetation_seed), three passes (masks 0x33, 4, 8): place (jitter bytes, group / object by
  weight, single candidate without a draw), resolve (keys sorted by separation, column, jitter, cell; grouping
  ascending, separation descending), emit (scale, yaw). Three different float orders for cell positions.
- Output: tree → tree_list (key BattleTerrain/vegetation/…; yaw byte = (int)(yaw·256/2π)); prop/decal → PROP
  (RigidModels/[Decals/]…; transform FUN_18000a390 = base scale · s rotated by FUN_180036990 about the Sobel terrain
  normal); vfx → PARTICLE_EMITTER. Tree list: items sorted (model bytes, x, y, z), models in CA hash-map order.
  Hand-placed ECVegetation trees join every climate's list.

## Open

- Tree y = height(pixel) · hf influence map (warscape build_hf_influence_map / get_hf_influence_value, ported in
  HfInfluenceMap.cs and veg_hf_influence.py, bit-exact against the dumped map): ported for tiles without a cell mask
  or link points only (the corpus); masked / linked tiles change the neighbour flags.
- Props use that height map's normal (keep_upright off); corpus props sit on flat ground.
- Not ported: prefab (0x10) / building (0x20) objects, exclusion polygons and the cell mask (empty in the corpus),
  BOB's hard procedural limit, per_climate_tree_conversions for hand-placed trees.

Prototypes: veg_proc_proto.py, veg_compile.py, veg_treelist.py, veg_e2e.py; Frida: research/bob_re/frida_veg_procedural.js
(veg_run_frida.sh).
