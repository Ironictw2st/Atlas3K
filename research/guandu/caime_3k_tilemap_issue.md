### Problem
**Tools → Export → Baseline Tilemap image** has no Three Kingdoms palette. Every game except Warhammer 3 falls into the
`//These for Attila, at least` branch of `BaselineTilemapExporter.CreateBitmap`, so a 3K tile map is written with
colours that are not tile sets in 3K's tile database. Some of the placement rules also differ from how 3K's own map
is painted.

**Result on a 3K map** (1094×785-hex custom map, BOB *Terrain / Tilemap* action):

| Tile map | "Failed to find tile for point" | Large tiles | Link-target tiles |
|---|---|---|---|
| CAIME baseline export | **3,235** | 2,692 | — (0 link targets) |
| Same map, 3K colours and rules (below) | **0** | 28,163 | 166,307 |
| Vanilla `3k_dlc07_main_map` (reference, 892×702) | 0 | 22,029 | 110,122 |

With the baseline map, Terry shows the wrong tiles almost everywhere.

The installed CAIME 1.0.0 build (`Z:\CAIME\CAIME`) also saved the file as an **uncompressed colour-mapped TGA**, even
though the file is named `tile_map.png` (it starts `00 01 01 00 …`, 256×32-bit palette). The current repo calls
`tilemapImage.Save(exportFilename, ImageFormat.Png)`, so this may already be fixed.

### How 3K reads the tile map colours
The colour → tile-set table is `terrain/tiles/campaign/_tile_database/_settings.bin` in `data/fast.pack`, a FASTBIN0
file. Each entry is a tile-set name followed by its colour as three `f32` (0–255), then a flag byte. Flag 1 marks
*linking* sets: lines that have to stay one hex wide and connected. Flag 0 marks area sets. Each tile in
`_tile_database/tiles/*.bin` matches neighbours by tile-set name (`TLT_EQUALS river`, `TLT_NOT_EQUALS generic_sea`,
…), not by colour.

| Colour | Tile set | Kind | Count in vanilla `tile_map.png` (px) |
|---|---|---|---|
| `96aa64` | generic (land) | area | 1,184,264 |
| `3971b7` | generic_sea | area | 828,895 |
| `1820c1` | mountains_cold | area | 164,463 |
| `53b021` | mountains_subtropical | area | 125,730 |
| `b69237` | mountains_temperate | area | 54,940 |
| `ffff7f` | mountains_yellow | area | 23,832 |
| `463a76` | mountains_terrace_farm | area | 6,305 |
| `10ffe4` | mountains_tea | area | 3,443 |
| `ffff00` | sea_coast (beach) | area | 17,860 |
| `f9ad69` | blockout_cliff | link | 10,978 |
| `9f222a` | blockout_cliff_ends | link | 566 |
| `0000ff` | river | link | 27,266 |
| `b4b4ff` | river_start | link | 348 |
| `ccccff` | river_mouth | link | 280 |
| `7f00ff` | river_crossing | link | 116 |
| `2c067f` | river_crossing_imperial | link | 96 |
| `da43ff` | river_crossing_track | link | 451 |
| `5d0018` | roads_tracks | link | 33,823 |
| `5d4218` | roads_paved | link | 13,820 |
| `c10018` | roads_imperial | link | 6,732 |
| `000068` | canal | link | 188 |
| `0037d0` | canal_links | link | 24 |
| `538dd5` | sea | link | (unused in vanilla) |
| `20ea16` / `008050` / `fa412d` | lakes / salt_pools / mines | link | (unused in vanilla) |
| `000000` | — (filler) | — | 1,784 |

### Layout (this part CAIME already gets right)
The tile map is the hex grid at 2×2 px per hex, `2W × (2H+1)`, with odd columns 1 px higher. Hex `(col, row)`
(row 0 = south) covers `x = 2·col + {0,1}` and `y = (2H) − (2·row + (col & 1) + {0,1})`. The pixels no hex covers (the
top row of even columns and the bottom row of odd columns) are black. On vanilla this matches the map.hex sea flag on
99.993% of pixels, and 99.94% of hexes are a single colour.

### Rules on the vanilla 3K map (measured against `3k_dlc07_main_map` map.hex)
- **Sea hex → `3971b7`** (generic_sea). CAIME writes `538dd5`, which is the `sea` linking set.
- **Beach hex → `ffff00`.** CAIME matches.
- **Cliff hex (map.hex IsCliff) → `f9ad69`.** CAIME writes `fe0000` and derives cliffs from "land hex with a sea
  neighbour". In 3K every land hex touching the sea is already a beach or cliff hex in the map.hex (7,427 of 7,427),
  so the hex's own cliff flag can be used directly.
- **Cliff hex touching a beach hex → `9f222a`** (cliff end): 142 of 142 on vanilla. CAIME's rule is the same, but it
  writes `fe0000`.
- **River hexes → `0000ff`** (1 hex wide, each hex has 2 river neighbours). CAIME matches.
- **River end with one river neighbour → `b4b4ff`** (river start): 87 of 87. CAIME matches.
- **River end next to the sea → `ccccff`** (river mouth): 70, all with one river neighbour. CAIME matches, but only for
  river hexes that are beaches.
- **Road × river → a crossing colour by road type:** `7f00ff` paved, `2c067f` imperial, `da43ff` track (each has 2
  river neighbours). CAIME writes `7f00ff` only.
- **Roads:** 3K has three road sets, and the map.hex has no road type. `5d0018` (tracks) is the most common and is a
  safe default. CAIME writes `956826`, which is not a 3K tile set.
- **Land → `96aa64`.** CAIME writes `5a7647`, which is not a 3K tile set.
- **Mountains:** `mountain` ground type (always impassable), with the set chosen by climate:

  | Climate | Tile set | Colour |
  |---|---|---|
  | cold | mountains_cold | `1820c1` |
  | temperate | mountains_temperate | `b69237` |
  | subtropical | mountains_subtropical | `53b021` |

  91% of vanilla mountain-ground hexes are one of these three (cold 41,099, subtropical 31,439, temperate 13,452).
  `mountains_yellow`, `mountains_terrace_farm` and `mountains_tea` are hand-painted variants. CAIME writes no mountain
  sets, so these areas come out as generic land.
- **Line width:** linking sets must stay one hex wide. Vanilla lines have 1–3 same-set neighbours per hex, never 4+.
  Painting any road hex as road can create 2-hex-thick spots where roads meet, which no tile matches.

### Suggested fix
Add a `three_kingdoms` branch to `CreateBitmap`, and give 3K its own rules in `CacheColours`:

| Palette entry | Colour |
|---|---|
| 1 road | `5d0018` |
| 2 river | `0000ff` |
| 3 cliff | `f9ad69` |
| 4 beach | `ffff00` |
| 5 land | `96aa64` |
| 6 sea | `3971b7` |
| 7 road over river | `da43ff` |
| 8 river mouth | `ccccff` |
| 9 cliff end | `9f222a` |
| 10 river source | `b4b4ff` |
| 11–13 (new) mountains cold / temperate / subtropical | `1820c1` / `b69237` / `53b021` |

- **Cliffs:** for 3K, take `hex.IsCliff` rather than "has a sea neighbour", and apply the cliff-end rule to cliff hexes
  touching a beach.
- **Mountains:** entries 11–13 come from `GroundTypeIndex == mountain` plus `ClimateIndex`.
- **Mouths:** check a river hex for a *sea* neighbour, not for `IsBeach`, since on 3K the mouth hex is the coast hex
  next to the sea.
- **File format:** keep writing a real PNG (the installed build wrote a TGA).

Evidence and a reference implementation: `research/guandu/build_tilemap.py` and `tilemap_hex.py`, and
`tile_colours.json` (the decoded `_settings.bin`).
