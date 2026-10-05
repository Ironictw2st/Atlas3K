# Atlas3K

A campaign map editor and builder for **Total War: THREE KINGDOMS**. It works on the Assembly Kit's own sources
(the `.terry` project, its layers and maps) and compiles the map **natively**, without BOB.

> **Alpha.** Back up your assembly kit (`raw_data\terrain\campaigns\<map>`, `working_data`) and your packs before
> building over them.

## What it does

| Part | What for |
|---|---|
| **Scene editor** | Props, entities, prefabs and layers of the campaign `.terry`, in a 2D top view and a 3D view (forests, water, rivers, seasons). The **Terrain & trees** tab paints the kit's land and sea height maps and the CampaignTree map, with undo and save. |
| **Tile map** | Paint the campaign `tile_map.png` hex by hex. Every stroke is validated against BOB's tile-matching rules. The **Errors** tab (F8) highlights every tile-map error and recommends a fix for it (details below). The tile map can be read from the kit, any file, or a `.pack` (*File > Tile map source…*); edits always save to a loose file. |
| **Terrain painter** | Heights, ground textures and trees on the compiled map. |
| **Build** | Compile the map (rasters, tile list, global map and meshes, rivers, global props, camera heightmap, trees, lookup), run your own steps, pack and install. One click, or one step at a time. |

## What the build generates

Each compile step writes the same files BOB's campaign actions write. "Match" is how much of Atlas3K's output is
identical to BOB's own output for the same inputs, checked byte by byte (`Atlas3K.Cli parity`) on the vanilla map
(`3k_dlc07_main_map`) or on a large modded map (190 Expanded, `main190`).

| Step | Generates (in `working_data`) | Replaces BOB action | Match with BOB | Checked on |
|---|---|---|---|---|
| `rasters` | `lf_height_map` / `lf_sea_height_map` (`.compressed_map`, `.dds`), `climate_map.cm` | height maps, climate map | 100% | vanilla |
| `tile_list` | `tile_list.bin` | Tilemap | 100% | vanilla |
| `global_map` | `global_map\global_blend.dds`, `texture_arrays.xml`, `tile_list.bin` | Global Mesh (global map part) | 100% | vanilla |
| `global_mesh` | `global_meshes\land_mesh_N`, `sea_mesh_N` (`.rigid_model_v2`, `.compressed_map`) | Global Mesh | 100% (494 / 494 files main190, 465 / 465 vanilla)* | main190, vanilla |
| `rivers` | `models\river_N` (`.wsmodel`, `.rigid_model_v2`), `height_patches\` | Terry file (rivers) | 100% (24 / 24 rivers, 87 / 87 height patches)* | main190 |
| `global_props` | `global_props.bin` | Terry file (props) | 100% (24,778,485 bytes, 12,465 entries) | main190 |
| `camera_heightmap` | `campaign_maps\<map>\camera_heightmap.png` | Generate Camera Height Map | 100% (2,506,520 / 2,506,520 cells) | vanilla |
| `trees` | `campaign_maps\<map>\display\trees\trees.campaign_tree_list` | Campaign Trees | 100% (205,767 / 205,767 trees) | vanilla |
| `lookup` | `campaign_maps\<map>\*lookup*.tga`, `.dds`, `_minimap.tga` | Convert lookup texture | 100% | vanilla |

\* Not counting the few bytes BOB leaves uninitialised (leftover memory). Those bytes differ between two BOB runs of
the same input too, so the parity tool masks them.

Meshes over BOB's 65,000-vertex limit are split the way BOB's mesh splitter does it, into extra meshes of the same
model.

## Install

1. Install Total War: THREE KINGDOMS and its **Assembly Kit** (Steam → Library → Tools).
2. Unzip `Atlas3K-<version>.zip` anywhere and run `Atlas3K.exe`. It needs Windows 10/11 x64 and a Direct3D 11 GPU, and no
   .NET install (the runtime is included).
3. The first start opens **Setup**:
   - It finds the game through Steam. Check the folders; a green tick means the folder was found.
   - Pick a map and press **Prepare game data**. This copies the map's compiled files and the tree tables out of
     your own game packs into `%LocalAppData%\Atlas3K`. Atlas3K ships none of the game's data.

Settings live in `%AppData%\Atlas3K\settings.json`. Change them later from **File › Settings** on the start page.

## Building a map

1. Open **Build** (Ctrl+B from any editor).
2. Click **New project** and save the `.atlas3k` file next to your mod's work.
3. Press **Build all** (F5). The left column shows each segment and step as it runs. The log shows everything; filter
   it, or tick *Selected row only*.

| Segment | Does |
|---|---|
| Validate | Checks inputs and the tile map before anything is written. Accept known tile-map codes in the profile. |
| Compile | The native steps. Tick only the ones you need; a step reads earlier steps' output from disk. |
| Custom steps | Your own commands (see below). |
| Pack | **New:** a pack with just the compiled map. **Merge:** your existing mod pack, with the map's folders replaced. |
| Install | Copies the pack into the game's `data` folder, keeping a backup of the old one. Refuses while the game runs. |

- **Run selected** runs only the highlighted row (one step, one custom step, or one segment).
- **Pack only** re-packs without compiling.
- **Cancel** stops at the next check.
- Every run writes a log and a JSON report to `<output>\build_logs`.

Hover any row, button or field for an info card on what it does. The **Project settings** tab edits everything else:
- the compile output (default: the kit's `working_data`, as BOB did)
- accepted tile-map errors
- folders to delete before compiling
- a terrain backup folder
- pack mode and contents
- install options

### Custom steps

Any program or script, run at one of these points: before compile, after compile, after pack, or after install.
Use them for CAIME, an RPFM start-position build, your own Python fix-ups, and so on.

**Tokens** in the command, arguments and working folder:

| Token | Becomes |
|---|---|
| `{project}` | the project file's folder |
| `{ak}` | the assembly kit |
| `{map}` | the map name |
| `{game}` | the game's `data` folder |
| `{out}` | the compile output |
| `{pack}` | the output pack |

**Environment variables:** `ATLAS3K_AK`, `ATLAS3K_MAP`, `ATLAS3K_OUT`, `ATLAS3K_GAME`, `ATLAS3K_PACK`,
`ATLAS3K_PROJECT` and `ATLAS3K_CLI` (the command-line tool).

A step's output goes to the build log. A non-zero exit stops the build unless *Continue on error* is ticked.

## Fixing tile-map errors

Open the tile map editor's **Errors** tab (F8). The Build window also offers *Show tile errors* when Validate or
`tile_list` finds problems.

**What it shows**
- Every problem hex is highlighted: red for errors, amber for warnings, magenta for holes. When zoomed out, each one
  is drawn as a dot.
- The list groups errors by type.
- **Find holes** runs BOB's tile matching on the whole map (1–3 minutes) to find spots that would get no tile in game.

**Working through it**
- Select an error (or press N / Shift+N). The map centres on it, and the recommended repaint is previewed with a
  dashed outline.
- Before you can apply a fix, Atlas3K runs BOB's tile matching on the area around it to check it opens no new hole.
  Fixes that would open a hole are dropped; the next-best one is offered, or the error is marked *manual* with advice.
- **Apply fix** (Enter) applies the fix. **Fix all of this type** and **Fix all safe** apply many fixes as one stroke.
- Every fix is an ordinary unsaved stroke: Ctrl+Z undoes it, and Ctrl+S saves it to the journal.

On the command line, use `tiles-errors [--simulate] [--codes a,b] [--ops-out fixes.json]` and
`tiles-fix [--codes a,b] [--dry-run]`.

## Command line

`Atlas3K.Cli.exe` runs the same builder headless:

```
Atlas3K.Cli.exe build --project my_map.atlas3k [--segments validate,compile,custom,pack,install] [--steps a,b] [--json]
Atlas3K.Cli.exe new-project my_map.atlas3k --map 3k_main_map
Atlas3K.Cli.exe setup --map 3k_main_map            # first-run data, as Settings › Prepare game data
Atlas3K.Cli.exe build-campaign --steps rasters,tile_list --out <dir>   # compile steps only
Atlas3K.Cli.exe validate-tilemap                   # tile-map pre-flight
```

Run it without arguments for every command.

## Research: building without BOB

The native build reproduces BOB's output byte for byte. [`research/README.md`](research/README.md) describes the method (Ghidra, Frida instrumentation of BOB, field-level diffs), the non-obvious rules for each step, and the tools, so the same can be done for other Warscape games. Per-step details: [`docs/native_campaign_build.md`](docs/native_campaign_build.md).

## Building from source

```
dotnet build Atlas3K.slnx -c Release
dotnet test src/Atlas3K.Tests
powershell -ExecutionPolicy Bypass -File tools\publish.ps1   # self-contained zip in dist\
```

The source needs the .NET 9 SDK (pinned in `global.json`).

See [KNOWN_ISSUES.md](KNOWN_ISSUES.md) and [CHANGELOG.md](CHANGELOG.md).

Not affiliated with Creative Assembly or SEGA. Total War: THREE KINGDOMS and its Assembly Kit are their property.
