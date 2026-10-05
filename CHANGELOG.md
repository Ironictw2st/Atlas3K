# Changelog

## Unreleased

### Campaign battles (battle editor, phase 1)
- **New window** (start page tile *Campaign battles*, or `Atlas3K.exe --campaign-battles`): the campaign-battle terrain's catchment areas (`battle_locations_map.bin`) on a map, a status per settlement, and fixes. Ported from the BattleMaps `blm` / `blm-ui` tool.
- **Sources, read only:** the catchments come from the linked packs, then the game's packs (or a loose `.bin`). The campaign regions come from the map's `map_data.esf`. Names and suggested kinds come from an RPFM extract of the mod (*File › Mod data folder…*).
- **Catchment editor:** select, move and resize areas, draw new ones, or delete them. Every edit is one Ctrl+Z.
  - The area tab edits the name, redirect, defending faction, box, centre and approaches.
  - The map shows coverage gaps for the active list on the battle landmass, and settlement dots coloured by status.
- **Regions tab:** each settlement is *OK*, *No catchment*, *Half covered*, *Wrong type*, *Redirect missing*, *Redirect invalid* or *Off the battle grid*.
  - **Fix** covers the settlement in both siege lists and redirects new regions to the city, port or resource map their layout or primary building calls for. *Fix all listed* does the same for every listed region.
  - Redirect targets without an embedded centre prefab are refused, because they load with a hole in the middle.
  - A campaign map that is not the battle grid's size is reported, not "fixed": every region is marked off the grid. This is the case for the 1478×1133 `3k_190e_expanded_map`.
- **Redirects and battles_tables:** pick any battle-map folder from the packs. The window checks the battle type against the existing `battles_tables` rows: it reads every pack's binary table without a schema, plus RPFM TSVs.
  - Rows for redirect folders without one are written as an RPFM TSV, with both `specification` and `map_path` set to `terrain\battles\<folder>\`.
  - *Its pack ships the battles_tables row* turns the row off for maps that bring their own.
- **Saving never writes the packs:**
  - *Save* writes `battle_locations_map.bin` and the row TSV under `output\campaign_battles`.
  - *Export mod pack…* writes a new `.pack`.
  - *Write to kit* copies the file to the kit's `working_data`, after a backup.
  - Writing into the game's `data` folder or into a linked pack is refused. The title shows `*` while there are unsaved changes, and closing asks *Save / Don't save / Cancel*.
- Info cards on every control and a walkthrough. See `docs/battle_map_editor.md`. The plan for the later phases is in `docs/battle_editor_plan.md`.

### Walkthroughs
- **First-run tours:** the first time each window opens (start page, Settings, Scene editor, Tile map, Terrain painter, Build), a guided tour dims the window, rings one panel at a time and explains it in 1-2 sentences. Back / Next / Skip tour; Esc skips, Enter or → goes on. A step whose panel is hidden (a developer-only menu, the Build window's empty state once a project is open) is left out.
  - The start page tour opens with a welcome card on the very first start.
  - Replay with *Help › Walkthrough for this window* (F1) in every editor, the *Walkthrough* button in Build, or *Show the walkthrough* in Settings. *Help › Reset all walkthroughs* (start page) and *Settings › Reset walkthroughs* show every tour again.
  - Finished or skipped tours are remembered in `settings.json` (`toursSeen`). Self-tests and other command-line automation never get a tour.
  - The tour is its own transparent window over the editor, so it also covers the 3D view, and it takes the keyboard while open.
  - Panels are tagged with `element.Spot("key")`; the step texts are one table per window (`Walkthrough.*.cs`).
- **Testing:** the `ATLAS3K_SETTINGS_DIR` environment variable points the app at a throw-away settings folder. `Atlas3K.exe [--scene|--tile-editor|--painter|--build] --walkthrough-shots <dir> [settings]` saves every step of that window's tour as a PNG (rendered off-screen, no input sent) and quits.

### Scene editor
- **Layer filters:** filter the layer tree by name, region, entity type and visible / hidden. Parents of matches stay in the tree, and filtering never changes visibility.
- **Show all / Hide all / Show only filtered:** each is one undo step, and locked layers are left as they are.
- **Terrain & trees tab:** paint the kit's land and sea height maps and the CampaignTree map in the 2D view.
  - Height modes: raise, lower, smooth, flatten, set to value (sea-level preset) and noise.
  - Trees: paint, erase, and fill by connected species or by map.hex region.
  - Alt+click picks the value or species under the cursor.
  - Edited hexes' trees are regenerated as the build places them, and the 3D view re-meshes after each stroke.
  - Undo and redo work per stroke.
  - Save writes only the changed TIFs, in their own format: height TIFs are patched in place, so only pixel bytes change. The originals are backed up in `output\terrain_edits`.
  - The tab warns when the build output is older than the sources. See `docs/terry_entity_editing.md`.
- **Add props (Props tab):** an asset browser over the game packs and linked packs (16,440 models on vanilla). It has search, a flat-shaded preview with size and source pack, and campaign models only unless *All models* is ticked.
  - Pick a model, then click on the terrain in the 2D or 3D view to place a Terry campaign Prop (the same components as Terry's) in the active layer, standing on the ground.
  - Placement settings: yaw or random yaw, scale with ± % jitter, a y offset, and origin or model base on the ground.
  - Repeat mode keeps placing until Esc. Each placement is one undo step.
- **Clamp to ground:** *Edit › Clamp selected to ground* (Ctrl+G), *Clamp all in active layer* and *Clamp all in view* move props onto the ground as one undo step. The status line reports how many were lowered or raised and the largest move.
  - Ground sources:
    - BOB's scene height, the default: the byte-identical camera height field, with global mesh, tile, river and prop height patches. A prop's own patch is ignored.
    - The bare lf + tile hf.
    - The kit lf map.
  - A build of another map or an old build is detected and skipped.
  - Modes: origin on the ground, model base on the ground, or vanilla sink. Vanilla sink buries mountain and rock meshes by their per-model depth, learnt from the map or loaded from a JSON table.
  - Other options: an offset, and *only lower*. LF-offset mountains (y stored relative to the terrain) are handled.
- **Find floating props:** selects props whose lowest point is more than a threshold above the ground. Settlement pieces are skipped by default.
- **Unsaved edits:** the title shows `*` while Terrain & trees edits are unsaved, and *File › Save terrain and tree edits* (Ctrl+S) saves them. Closing the window or switching project asks *Save / Don't save / Cancel*.
  - A value typed into the inspector is committed before the window closes.
  - Entity edits are written to their layer files as they are made, so they never need saving. See `docs/scene_props_tools.md`.

### Tile map
- **Tile map source:** read `tile_map.png` from the kit (default), any file or folder, or an entry inside a `.pack`. Set it in *File > Tile map source…*, in Settings, or in the `.atlas3k` project (`tileMap`).
  - Packs are never written. Edits save to a loose `tile_map.png` in a chosen folder (default: the kit's map folder), with one journal per target.
  - The build's `tile_list` step reads the same source. It extracts a pack entry to the build output first and logs which file it used.

### Build window
- **Info cards:** hover any button, build row, compile step, tab, field or column header for a short card (bold title, 1-2 sentences) saying what it does, what it reads and writes, and when to use it. Compile-step cards name the BOB action each step replaces.
  - The card helper (`InfoCard.Card(key)`) and its text tables (`InfoCards.*.cs`, one per window) are shared, so other windows can use them.
- **Clearer labels:** the *Profile* tab is now *Project settings*; *Build segments* is *Build steps (run top to bottom)*; *Output* / *Pack* log buttons are *Output folder* / *Pack file*; profile fields *Accepted tile-map errors*, *Delete before compile*, *Terrain backup folder* and *Pack mode*.

### Start screen and Settings
- **Map selector:** the start page picks the assembly kit (`assembly_kit*` folders next to the game) and the map (kit maps with a `.terry`, plus maps in linked packs). The choice is remembered, and every editor opened from the start page uses that map.
- **Settings page:** reachable from the start page (*File › Settings* and a *Settings* tile) and from *Help › Settings* / *Window › Settings* in every editor. It covers all folders, linked packs, the tile map source, Prepare game data and developer mode, with info cards on every control.
- **Linked packs:** add, remove and reorder mod `.pack` files as read-only sources for compiled map files, DB tables and assets (`linkedPacks` in settings.json, used as the paths' mod packs).
- **Prepare game data lists every map:** vanilla, kit and linked-pack maps. It copies the chosen map from the linked packs first, then the vanilla packs. A map that is only in the kit says to build it or link its pack first.
- **Original files are never written:** a tested guard (`SourceGuard`) refuses writes into the game's `data` folder, a linked pack or any `.pack`. Prepare game data and Settings check it.
- Packs are read with the C# `PackFile` reader rather than RPFM's Rust `rpfm_lib` (see README, *Linked packs*).

## 0.1.0-alpha.2 (2026-10-05)

### Native build: byte-identical to BOB
Every compile step now reproduces BOB's output byte for byte. The only exceptions are a few bytes BOB itself leaves uninitialised; they differ between two BOB runs of the same input. See `research/README.md` for the method and `docs/native_campaign_build.md` for the rules per step.
- **tile_list / global_map:** identical on vanilla. BOB sorts the tile database before link targets exist, and its river flow stops at tiles with no entry link.
- **trees:** identical to BOB's Campaign Trees output on vanilla (205,767 of 205,767), using BOB's own height scale, per-tile hf heights and the tile-cell lookup.
- **camera_heightmap:** identical on vanilla. It samples BOB's scene (height patches, global mesh, tile fallback); the PNG is written with classic zlib's compressor.
- **global_props:** identical on main190. On vanilla only some river model numbers differ.
- **rivers and height_patches:** BOB's river geometry is now the default (`--river-geometry wide` keeps the old one). Rotated, reversed and terrain-relative rivers are covered.
- **global meshes:** identical on vanilla and main190, and now the default (`--global-mesh native` keeps the old path). Meshes over 65,000 vertices are split as BOB does.
- **build-campaign:** new `--fresh-trees` option; `trees` runs after `tile_list` when both are selected.

### Tile map
- **Tile error mode** (tile map editor › Errors tab, F8):
  - Every tile-map error is highlighted and listed by type, each with a recommended fix.
  - The fix is previewed on the map and applied in one click, or applied in bulk.
  - Before it is offered, each fix is checked with BOB's tile matching around it, so it cannot open new holes.
- **Find holes:** whole-map tile matching, available to everyone, not just in developer mode.
- **Command line and MCP:** `tiles-errors` and `tiles-fix`; terry MCP tools `tile_errors` and `fix_tiles`.
- **Build window:** *Show tile errors* when Validate or `tile_list` reports tile-map problems.

## 0.1.0-alpha.1 (2026-10)

First alpha. This project was developed internally as "TerryClone".

### Build
- **Build window:**
  - One-click Build all (F5).
  - Run selected (one segment, compile step or custom step).
  - Pack only, and Cancel.
  - Live per-step status and timing.
  - A filterable log.
- **Map projects (`.atlas3k`):**
  - Map, assembly kit and mod packs.
  - Compile steps and accepted tile-map codes.
  - Clean folders and a rolling backup.
  - Custom steps.
  - Pack (new or merge) and install.
- Custom steps run external commands at four points in the build, with path tokens and environment variables.
- **Pack and install:**
  - Native PFH5 packs: a new pack, or a merge into an existing mod pack with stale folders replaced.
  - Install copies the pack into the game's data folder with a backup, and refuses while the game is running.
- **Command line:** `build --project`, `new-project`, `setup`. The terry MCP server has a `build_project` tool.

### Setup
- **First-run setup:**
  - Finds the game through Steam.
  - Extracts the chosen map's compiled files and the tree DB tables from the user's own packs.
  - No RPFM needed.
- Settings are stored in `%AppData%\Atlas3K` and data in `%LocalAppData%\Atlas3K`; nothing is hard-coded to one machine.

### Interface
- **Start page:** editors, recent projects, getting started.
- **Look and menus:**
  - One dark theme across every window: menus, lists, combo boxes, scroll bars, tabs, grids.
  - The same Build, Window and Help menus in every editor.
  - An About box.
- **Window behaviour:**
  - The app icon.
  - Remembered window placement.
  - Resizable side panels.
  - Collapsible sections in the terrain painter.
- **Errors:** friendly error dialogs with copyable details. Errors are logged to `%LocalAppData%\Atlas3K\logs`.
- **Developer mode** (Settings) holds the BOB launcher, tile-matching simulation, build comparison and self-tests,
  which are hidden by default.
- **Tile error mode** (tile map editor › Errors tab, F8):
  - Every tile-map error is highlighted and listed by type, each with a recommended fix.
  - The fix is previewed on the map and applied in one click, or applied in bulk.
  - Before it is offered, each fix is checked with BOB's tile matching around it, so it cannot open new holes.
- **Find holes:** whole-map tile matching, available to everyone, not just in developer mode.
- **Command line and MCP:** `tiles-errors` and `tiles-fix`; terry MCP tools `tile_errors` and `fix_tiles`.
- **Build window:** *Show tile errors* when Validate or `tile_list` reports tile-map problems.

## 0.1.0-alpha.1 (2026-10)

First alpha. This project was developed internally as "TerryClone".

### Build
- **Build window:**
  - One-click Build all (F5).
  - Run selected (one segment, compile step or custom step).
  - Pack only, and Cancel.
  - Live per-step status and timing.
  - A filterable log.
- **Map projects (`.atlas3k`):**
  - Map, assembly kit and mod packs.
  - Compile steps and accepted tile-map codes.
  - Clean folders and a rolling backup.
  - Custom steps.
  - Pack (new or merge) and install.
- Custom steps run external commands at four points in the build, with path tokens and environment variables.
- **Pack and install:**
  - Native PFH5 packs: a new pack, or a merge into an existing mod pack with stale folders replaced.
  - Install copies the pack into the game's data folder with a backup, and refuses while the game is running.
- **Command line:** `build --project`, `new-project`, `setup`. The terry MCP server has a `build_project` tool.

### Setup
- **First-run setup:**
  - Finds the game through Steam.
  - Extracts the chosen map's compiled files and the tree DB tables from the user's own packs.
  - No RPFM needed.
- Settings are stored in `%AppData%\Atlas3K` and data in `%LocalAppData%\Atlas3K`; nothing is hard-coded to one machine.

### Interface
- **Start page:** editors, recent projects, getting started.
- **Look and menus:**
  - One dark theme across every window: menus, lists, combo boxes, scroll bars, tabs, grids.
  - The same Build, Window and Help menus in every editor.
  - An About box.
- **Window behaviour:**
  - The app icon.
  - Remembered window placement.
  - Resizable side panels.
  - Collapsible sections in the terrain painter.
- **Errors:** friendly error dialogs with copyable details. Errors are logged to `%LocalAppData%\Atlas3K\logs`.
- **Developer mode** (Settings) holds the BOB launcher, tile-matching simulation, build comparison and self-tests,
  which are hidden by default.
