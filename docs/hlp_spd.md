# hlp_data.esf / spd_data.esf: native generation

Three Kingdoms campaign maps ship two offline AI pathfinding files in `campaign_maps/<map>/`:

| file | record | contents |
|---|---|---|
| `spd_data.esf` | CAI_SIMPLE_PATH_DIRECTORY | landmark (ALT) table: per hex, the cost to/from 8 landmarks |
| `hlp_data.esf` | CAI_TRANSITION_DATA | high-level graph: per region area, the transitions into neighbour areas and an intra-area cost matrix |

The game normally writes both with `CAI_PATHFINDER::reprocess_spd_data` / `reprocess_hlp_data` (empirecampaign.modder.x64.dll) during a startpos build. Atlas3K now builds them without the game, BOB or any CA tool. The only inputs are:

- `pathfinding.ppd`
- `map_data.esf`
- three DB tables from the kit: campaign_map_roads, campaign_variables and campaign_map_playable_areas.

## Running it

- **Pipeline step:** `hlp_spd`, which runs after `lookup`. It reads `pathfinding.ppd` and `map_data.esf` from the build output's `campaign_maps/<map>` folder, falling back to the kit's `working_data`. It writes `spd_data.esf` and `hlp_data.esf` next to them.
- **CLI:**

```
Atlas3K.Cli --ak <kit> --map <map> hlp-spd [--in <dir>] [--out <dir>] [--compare <dir>]
            [--only hlp|spd] [--legacy-stl] [--threshold 0.4] [--threads n] [--verbose]
```

- `--compare` takes a folder holding CA's files. It reports byte identity for spd, plus field statistics for hlp.
- `--legacy-stl` reproduces the transition order of files built with the 2019 toolchain (dlc04, 8p).
- 190E example:

```
Atlas3K.Cli --ak "C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\assembly_kit_190E" \
    --map 3k_190e_expanded_map hlp-spd --in <folder with pathfinding.ppd + map_data.esf> --out <folder>
```

Code lives in `src/Atlas3K.Core/Campaign/AiPathfinding/`:

- `CampaignPathGrid` and `SpdBuilder` build spd.
- `AiPathGrid`, `AiSearch` and `HlpBuilder` build hlp.
- `MapDataRegions` reads map_data.
- `AiPathfindingStep` is the pipeline step.

The formats are in `src/Atlas3K.Formats/Esf/`: `CaabFlat`, `CampaignAiData` and `EsfTree`. Research scripts and Ghidra notes are in `research/hlp_spd/`.

## Parity (2026-10-05)

| map | spd | hlp: identical areas | hlp: transitions with same hexes + target + cost | hlp: matrix values |
|---|---|---|---|---|
| 3k_dlc07_main_map | byte-identical | 317 / 334 | 2372 / 2398 | 18640 / 18700 |
| 3k_dlc06_main_map | byte-identical | 322 / 339 | 2428 / 2454 | 19042 / 19102 |
| 3k_dlc04_main_map (`--legacy-stl`) | byte-identical | 300 / 321 | 2438 / 2470 | 20130 / 20190 |
| 8p_main_map (`--legacy-stl`) | byte-identical | 294 / 321 | 2438 / 2486 | 19766 / 19766 |
| 3k_190e_expanded_map | 99.997 % of values, same box + landmarks | 601 / 644 | 4561 / 4644 | 42192 / 42312 |

On every map these hlp fields match 100 %: node count, area set, centre, `a`, plus `b` (except 2 of the 190E areas). The matrix column counts only areas whose transition list is identical.

## Timing

Measured on this machine (Release build, all cores):

| map | spd | hlp | total (incl. reading inputs) |
|---|---|---|---|
| vanilla (892×702) | ≈0.3 s | ≈1.1–1.5 s | ≈2 s |
| 190E (1478×1133) | ≈0.7–0.9 s | ≈3.5 s | ≈4.7 s |

The Python research prototypes were much slower. What makes the C# versions fast:

- the 16 spd searches run in parallel, using Dial buckets on maps up to 1024 hexes;
- hlp phase 1 runs in parallel;
- gated edge sets are cached per (HLCI pair);
- searches use generation-stamped arrays (no per-search clears).

In the game, these files come out of a startpos build that takes many minutes.

## SPD algorithm (byte-identical)

1. **Bounding box.** Take the box of hexes whose type ≠ 2.
2. **Landmarks.** There are 8 targets: the 4 corners, then (mid x, min y), (mid x, max y), (min x, mid y) and (max x, mid y), where mid = ((max − min + 1) >> 1) + min. Each landmark is the passable hex nearest its target, scanning x outer, y inner, with a strict `<`.
3. **Edges and costs.**
   - Edges come from the ppd. Bit 6 is set equal to bit 7.
   - The cost table has 256 entries: the ppd costs repeated in 4 blocks of 64.
   - Slots 1 and 2 hold the beach costs (`pathfinding_land_to_sea` / `sea_to_land`). Slot 0x3E holds the road cost (the lowest campaign_map_roads threshold).
   - Road hexes use the road slot on their masked edges. A road hex on a river (type 6) uses it on all 6 edges, and on the edges coming back to it.
4. **Settlement slots.** Slot hexes are the map_data PRIMARY/PORT_SLOT_AREA_BLOCK hexes. Their edges to land, sea or other slot hexes cost 0 in both directions. A slot hex the ppd marks impassable becomes walkable.
5. **Moves.** A move is allowed only if the type-pair table allows it (FUN_1805fa120 + FUN_1805d3a70). Bridges (ppd bridge lists) link their two banks at cost 500.
6. **Searches.** Each landmark gets one outward search and one inward search.
   - On maps over 1024 hexes in either direction, the search copies FUN_18059f480 exactly: a binary heap of (hex, cost) ordered by cost only, with duplicates, and the game's pop and push sift rules.
   - The visited set is a `CAI_SPARSE_MAP<1024,64,bool>`: a coordinate c ≥ 1024 shares the flag of 960 + (c & 63).
   - Values are stored in a `CAI_SPARSE_MAP<1024,32>`: c ≥ 1024 aliases to 992 + (c & 31), and the last write wins. The output box is the box of written cells.
   - I confirmed both alias rules by loading the DLL in a Python harness and calling its sparse-map functions (`research/hlp_spd/oracle/`).
   - I also confirmed the neighbour order the same way. `LOGICAL_POSITION_UTILITIES::adjacent_hexes` in empireutility returns the same 6 directions as the ppd direction table.

**Why 190E is not byte-identical.** About 160 of its 948k cells differ (0.017 %). Every one is a hex whose visited flag or value cell is shared with an x/y ≥ 1024 hex, or lies downstream of one. In those places the exact settle order decides which write wins. One example is (999,670) slot 0: mine 95580 / ref 95700, and the slots 0 and 1 are swapped. Hex order, neighbour order and the heap code all match the decompile, so the remaining source is still open.

**Why the DLL cannot simply run the step.** The full `reprocess_spd_data` / `reprocess_hlp_data` entry needs a constructed CAMPAIGN_PATHFINDER and campaign model: DB tables, campaign setup and campaign variables. Those cannot be built outside the game.

## HLP algorithm (field-level)

1. **Nodes and areas.**
   - Nodes are regions. Each node keeps the areas of type 0, 3 or 4. Area id = region | areaIndex << 9.
   - The centre is the settlement when it lies inside the area, else the map_data area centre. `a` is the area's map_data id.
2. **Phase 1 (FIND_REGION_BORDER).**
   - A heuristic-free search runs from the centre over the AI grid.
   - The grid uses nav bit 7, the move-type table, and type-5 port links at 500.
   - Beaches are gated by the centre's HLCI.
   - `b` is the largest cost to a land or sea hex of the area itself.
   - Land or sea hexes of other areas (but not slot hexes) are recorded per neighbour area, in discovery order, and not expanded.
3. **Transitions.**
   - The first transition comes from the refined centre-to-centre path (refine threshold 0.4).
   - The others come from border clusters: an integer-mean centroid, nearest hexes on both sides, the 2·nearest-distance acceptance test, and erasing hexes within distance 10.
   - `cost` is the waypoint sum of the path (bridge crossing = 500). When both ends touch the same settlement, the path is costed without a faction.
   - `f1` = exactly one of the two areas is land (type 0). `f2` = `f1` and cost 0.
4. **Order.** Transitions are written in MSVC `unordered_multimap` iteration order: hash y·1016 + x, VS2019 rehash-before-insert, or VS2017 insert-then-rehash with `--legacy-stl`.
5. **Matrix.** Costs between the transitions of an area, in creation order. Each search stays inside the region, with settlement slots blocked and beaches off.

**Remaining HLP gaps:**

- **Missing pairs.** A few land/sea pairs across bridges over one-hex "sea" river pieces are missing (8 pairs on dlc07). Example: area 207 at (371,190), where CA has cost 500 / 1280 / 3300 land↔sea links through bridge hexes. The game's type or edge rules for bridges next to sea hexes are not fully known.
- **Cluster ties.** In some cases a different hex is chosen as the nearest cluster hex, for example (500,323) vs (500,324).
- **Knock-on effects.** Both problems above shift the `idx` values and the matrix of the affected areas.
- **190E sparse maps.** 2 of the 190E `b` values differ, probably from sparse-map effects beyond x 1024.

The game reads these files at campaign start. Small transition differences change AI route planning slightly, but the files stay structurally valid. Use the CA-built files when they are available.
