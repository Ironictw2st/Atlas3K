# Battle map editor (campaign-battle terrain)

Atlas3K's battle mode edits the **BOB sources** of a campaign-battle terrain: the land that campaign battles are
composed from, picked by `campaign_map_playable_areas.terrain_folder` (vanilla: `terrain/battles/3k_main_map/`).
CA ships only the compiled files. The sources were reverse-engineered in the BattleMaps project; the formats are in
`Z:\Claude\BattleMaps\docs\bob-battle-terrain-sources.md`, and a ready-made source package for vanilla `3k_main_map`
is in `Z:\Claude\BattleMaps\out\share\3k_main_map_bob_sources`.

## Opening

| Way | How |
|---|---|
| Directly | `Atlas3K.App.exe --battle "<kit>\raw_data\terrain\battles\<map>"` (only the battle editor opens) |
| From the campaign editor | *File → Open battle project…*, then pick the folder holding the `.terry` |

A project folder holds:
- `<map>.terry` and its catchment `.layer`
- `tile_map.png` and `climate_map.png`
- `explicit_tiles.txt`
- the height TIFFs: Terry-named `<map>.height.<id>.tif` / `.sea_height.<id>.tif`, plus `lf_heights.tif` / `lf_sea_heights.tif` for BOB
- `battle_location_map_meta_data.xml` + `blm_land.png`
- `rules.bob`

The palette needs the kit's `raw_data\terrain\battles\tile_placement_groups.xml` and the extracted battle tile
database (default `Z:\Claude\TerryClone\Vanilla\terrain\tiles\battle\_tile_database`).

## Tools

| Tool | Use |
|---|---|
| Paint tile map | Paints the selected palette colour. Exact colours only: BOB matches RGB exactly, and anything else (e.g. black) places no tile. Option: paint only over the colour where the stroke starts. |
| Fill region | Recolours a connected patch of one colour. |
| Eyedropper | Picks the colour under the cursor. |
| Raise / Lower / Smooth / Flatten / Noise | Height brushes on the land or sea raster (*Height brushes edit*). Water shows where the sea is above land. |
| Settlement/resource tiles: select, move | Click a tile to select it and drag to move it. **R** rotates, **Del** deletes. |
| Settlement/resource tiles: place | Pick a tile in the list; a ghost follows the cursor; click to place. **R** turns the ghost. |
| Catchment areas: select, move, resize | Click an area (the smallest one under the cursor; **Tab** cycles overlapping ones). Drag inside to move it, drag an edge or corner to resize, drag the cross to move the infield centre. **Del** deletes. Types, redirect, culture and exact numbers are in the side panel (*Apply*). |
| Catchment areas: draw new | Drag out a box; it gets the ticked types and a new id. |

Encampment areas are not edited: BOB generates one per road-corner tile on land.

Explicit tiles that overlap another tile or leave the map are drawn red (*Build → Check explicit tiles*). BOB stops
at the first such tile.

## Saving and building

- **Ctrl+S** writes only what changed. Both height copies are written. Every overwritten file is first copied to
  `output\backups\battle_<map>_<time>`.
- **Build → Build with BOB** works only for a project inside a kit (`<kit>\raw_data\terrain\battles\<map>`). It:
  1. checks that `rules.bob` has `save_meta_data_map = true`, and offers to write it;
  2. warns about explicit-tile overlaps;
  3. refuses while BOB is running in the same kit, and asks when one is running from another kit;
  4. saves;
  5. runs BOB headless: *Terrain / Tilemap*, then *Terrain / Low frequency data*.

  Output goes to `<kit>\working_data\terrain\battles\<map>`. Pack it together with the vanilla `tile_map.bmd` (a
  static file).
- **Build → Compare…** reports build vs. a reference folder:
  - which files are identical;
  - each catchment list, area by area, plus the land grid;
  - the % of cells with the same tile set;
  - settlement/resource tiles in the same place and rotation.

  After a build it compares automatically when the extracted vanilla map exists under
  `Vanilla\terrain\battles\<map>`.

A vanilla rebuild from the package gives a byte-identical `battle_locations_map.bin`, `climate_map.cm` and height
DDS files, all settlement/resource tiles in place, and ~92% of cells on the same tile set. The rest is BOB's random
choice within mixed groups.

## Code

- `Atlas3K.Formats/Battle/`
  - `BattleTileDatabase` (sets, climates, tiles, masks)
  - `BattlePalette`
  - `ExplicitTilesFile`
  - `BattleCatchmentLayer` (read/write layer entities)
  - `BattleCompiledFiles` (compiled `battle_locations_map.bin`, `tile_map.tiles` — the path index is **1-based**)
- `Atlas3K.Core/Battle/`
  - `BattleProject` (load / changed parts / save)
  - `BattleTools` (paint, fill, height adapter)
  - `BattleObjects` (explicit-tile footprints and conflicts, list undo)
  - `BattleRenderer`
  - `BobBattleBuild` (rules, headless BOB, compare)
- `Atlas3K.App/`
  - `BattleWindow` (+ `.Objects.cs`)
  - `BattleMapView`
  - `BattleInteractions`
- Tests: `BattleProjectTests`, `BattleObjectTests`. Footprints are checked against every settlement/resource tile in
  vanilla's compiled tile map.
