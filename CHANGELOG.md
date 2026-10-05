# Changelog

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
