# Changelog

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
