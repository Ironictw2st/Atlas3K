# BOB global mesh and camera heightmap: reverse-engineering notes

These notes come from Ghidra decompiles of the assembly-kit DLLs. The decompiled C is in `research/bob_re/`:

| Folder | Contents |
|---|---|
| `tooldatabuilder/` | Driver, per-tile builder, merger, cleaner |
| `mesh/`, `mesh2/` | Merger helpers |
| `camera/`, `camera_lambda/` | Camera heightmap |
| `warscape_height/` | Terrain height query |

**Tools.** Ghidra 12.1 and JDK 21 are installed portably in `Z:\Claude\Tools`, with the project in `ghidra_projects\bob`.

- **`ghidra_run.sh <dll> <outdir> <names~alt> <strings~alt> [max] [callee depth]`** decompiles functions from the saved project. Use `~` for regex alternation and `\s` for spaces, because the Windows batch launcher splits arguments on `;`, `,` and spaces.
- **`research/bob_re/disasm_calls.py`** shows the argument setup before a given call.
- **`research/bob_re/disasm_grep.py`** greps a disassembled function and resolves RIP-relative float constants.

## Camera heightmap (`TOOLDATABUILDER::generate_camera_height_map`, tooldatabuilder 0x180069e80)

**Settings** (`CAMERA_HEIGHT_MAP_SETTINGS`):

| Offset | Meaning |
|---|---|
| +0 | Samples per unit |
| +4 | Resolution scale relative to `terrain_size_in_tiles` |
| +8 | Blur on/off |
| +0xc | Kernel size |
| +0x10 | Sigma |

**Sampling:**
- Grid = tiles × scale. cellW = world width / cols, cellH = world height / rows.
- **Cell (x, y):** the rectangle is centred on (x·cellW, y·cellH) with half-size 0.5 × cell. Output cell (x, y) is element [y·cols + x].
- **Samples** (`FUN_18006bf20`): n = ceil(extent × samplesPerUnit) per axis, sampled from the min corner in steps of extent/n. The cell value is the max of `height(x, z)`, starting from −1.
- **Height query:** the scene terrain object's vtable slot 0xd0. See the terrain height section below.

**Output:**
- Highest = max over all cells, printed as "Highest Sampled Height".
- Pixel = ceil(max(h / highest, 0) × 65535).
- `height_scale` = highest × 1/65535.
- Optional separable blur, then saved as a 16-bit PNG.

**Native version** (`CameraHeightmapStep`):
- It uses lf max(h, 0) over 4×4 lf blocks plus rasterised props, with ceil conversion.
- This sampling fits vanilla best on prop-free terrain (80% of cells within 0.05). The corner-centred rectangle came out slightly worse, probably because BOB samples with bilinear interpolation.
- Over mountains, vanilla dlc07 follows an older prop layout, so it can't be matched there.

## Terrain height query (`WARSCAPE::TERRAIN_RENDER_SETUP::get_height_worker`, warscape 0x180371030)

- **Formula:** height = lf part + tile HF part, for the tile instance covering the point, as placed from `tile_list.bin`.
- **Tile-local coordinates:** tile px = x / tileSize − offset. The tile rectangle is (x, y, w, h) with w and h swapped for orientation 0x20 and 0x80. The local sub-tile index is rotated by the orientation (0x10, 0x20, 0x40 or 0x80).
- **Masking:** if the tile is masked and the sub-tile isn't valid, the tile contributes nothing at that point.
- **lf part:** a bilinear sample of the lf map × scale − offset.
- **HF part:** comes from `hf_height_map.compressed_map` (`get_high_frequency_height_new`), multiplied by the campaign HF scale (`this + 800`). If the tile has no HF raw data, the height comes from the tile mesh's high-frequency positions instead.
- **Vanilla campaign tiles:** mountain tiles have all-zero HF maps and flat `TerrainBase0` meshes (y = 0, skirts at −10). The relief is in the mountain **props**. Road and river tiles have small HF maps (range −1..0).

## Global mesh (`FUN_180124ed0`, driven by `TOOLDATABUILDER::process_terrain_global_mesh`)

### Tiling
- Battle size in tiles = `battle_size_in_tiles`, the tile-map grid (1784 × 1405 on dlc07).
- **Cells per mesh:** max(tiles) × 0.125 = 223. Grid vertices = 224 × 224 per mesh.
- **Meshes per axis:** 2 × max(tiles) / 223 = 16.
- **Cell size:** extent / (2 × max(tiles)), where extent = max(world w, h) = 595.1, so 0.16679.
- Meshes are built in a loop "Building mesh k of 256". Empty ones are skipped.

### Height grid
- Built by a parallel lambda (`FUN_180147cf0` / `FUN_180134a00`) into a float grid of 224², with −20.0 (`DAT_1804e3e14`) marking a hole.
- The heights come from the terrain query `FUN_18016ae30`. **Not yet decompiled.**

### Vertices
- Row-major: j (z) outer, i (x) inner.
- 0x94-byte records: +4 x = (i + mesh col × 223) × cell, +8 y = grid height, +0xc z = (j + mesh row × 223) × cell.
- Normals are at +0x44..+0x4c, computed by `FUN_180147860(heights, verts, 224, 0.33)`. **Not yet decompiled.**

### Triangles
- Visit quads (j, i) row-major, for i, j ≤ 223, where none of the four corners is −20.
- With a = j·224+i, b = a+1, c = a+224, d = c+1, emit [a, c, b] then [c, d, b].

### TRIANGLE_MERGER (`rigidmodel_optimise.cpp`)

**Call:** `process(factor = cos(conversion_params.angle × π/180), 64.0, FLT_MAX, flags)`. The log prints the factor as 0.9999.

**Setup:**
- Iterations N = min((uint)(64 × 1/6), 50) = 10. Step = 64 / N = 6.4.
- Initial vertex→triangle adjacency: `cfdb0` copies triangles into 12-byte records and appends each triangle's index to each corner's list, in triangle order.

**Iteration k** (k = 1..N): the edge limit is L = k × 6.4. The counter jumps by 10 when a pass removes nothing four times in a row. Then, for each vertex v in index order, `d0550(v)` runs:
1. If flag[v] < 2, skip.
2. **Removable** (`cf400`): for every live triangle around v, both other corners a and b need |n_v · n_a| ≥ factor. Unless flag[v] == 4, a neighbour whose flag isn't 1 or 4 must also have |y − y_v| ≤ tolerance (FLT_MAX, so this check never fails).
3. **Candidates** (`cfa40`): for every live triangle around v, each other corner w that passes `cf5c0(v, w)`. They're sorted by an MSVC `std::sort` comparator; the key appears to be distance to v in x/z (`FUN_180133020`, comparator in `FUN_180130020` and related), still to be confirmed. The first candidate is the target.
4. **`cf5c0(v, w)`**, flag rules:
   - flag 0 → never.
   - flag 3 → w must have flag 3 or 0.
   - flag 4 → w must have flag 4 or 1.
   - Otherwise any w.
   
   Then for every live triangle around v **and** around w, with v replaced by w:
   - If flag[w] > 1 and the triangle becomes degenerate, reject unless all three corners have flag ≥ 2.
   - Reject if `cf140` (the normalised edges' x/z cross product is < 0.1 in absolute value, i.e. nearly collinear).
   - Reject if `cf290` (any x/z edge is longer than L, or the x/z orientation cross is > 0).
5. **Collapse:** merge v's adjacency list into w's (`FUN_1800a6a00`), clear v's list, replace v by w in v's triangles, and zero any triangle that becomes degenerate.

**Compaction** (`cf7b0`): live triangles are kept in original order, called after every iteration. The log line is "X triangles merged to Y".

**After the merger:** the builder swaps the first two indices of every triangle, which flips the winding.

### Confirmed details (prototype `research/derived_maps/merger_proto.py`)

**Vertex flags** (grid lambda `FUN_18016b2f0`):
- The default is 2.
- A valid vertex gets 2 from `FUN_1801471b0` if all 8 neighbours one cell away (±DAT_1806b2c04 = extent / maxTiles × 0.5, i.e. one cell) are valid, and 0 otherwise.
- **Mesh-border vertex** (i or j is 0 or 223): the flag starts at 0. If exactly 3 of the 4 axis neighbours are valid (a map edge), it becomes 3, except at a multiple of 32 along that edge.
- **Sea option** (`param_1[10]`): vertices with (i & 3) == 0 or (j & 3) == 0 get 0.

**Height query** (`FUN_18016ae30`):
- Query the tiles near the point (terrain quadtree). Skip any whose tile set is `exclude_from_global_mesh` or whose `use_alt_lf` ≠ the mesh kind (sea meshes use alt lf).
- The first tile with valid `get_height` wins. Otherwise take the minimum over 4 diagonal probes (±DAT_180456360). With nothing valid, the result is −20 (a hole).
- Holes follow tile coverage. Example: the jagged hex edge on the south map border, where x mod 8 in 4..7 on rows 0–1.

**Normals:** Sobel ÷ (k² − 1) = ÷8 (`FUN_180134080` returns sum / (k·k − 1)), with nz = 1/0.33. So n = normalise(Sx/8, Sy/8, 3.0303).

**Grid positions:** x = f32(I × (double)f32(595.1) / 3568) with I the global column, **computed in double**. This is bit-exact on all columns. f32(I) × f32 cell is not.

**lf height** (`TERRAIN_RENDER_SETUP::get_height_worker` + bilinear `FUN_1803a1e30`):
- u = (x − minX)/(maxX − minX) and v = 1 − (z − minZ)/(maxZ − minZ).
- fx = u·W, fy = v·H. Top row = int((v − 1/H)·H), right column = int((u + 1/W)·W).
- Lerp columns by fx − floor(fx), then rows by fy − floor(fy).
- value = u16 × f32(1/65535).
- height = (l × 5500) × f − f × 1200, with f = (1/128) × tileSize (tileSize = 595.1/1784).
- The prototype reproduces vanilla vertex y bit-exactly on about 60% of vertices; the rest are mostly 2 ulps off. **Open.**

**Merger:**
- The input triangle count reproduces BOB's log exactly (99014 on mesh 0).
- With exact normals, flags and double-precision positions, the output matches vanilla's first 210 triangles.
- The prototype makes 8152 triangles against vanilla's 7191.
- The remaining causes are being narrowed down: hole validity (the prototype uses vanilla quad coverage, not real tile coverage) and exact heights.

### Still to do
- Vertex flags (`[rbp+0x58]` in the builder).
- `FUN_180147860` normals.
- `FUN_18016ae30` height.
- The `std::sort` comparator.
- VERTEX_LIST_CLEANER (`FUN_1800d0700`).
- Skirts: the builder code after the cleaner (lines 890–1300 of `180124ed0`, using 0.01 and 1.0 offsets).
- MESH_SPLITTER.
- The `land_mesh_N.compressed_map` writer.
- Sea meshes.
