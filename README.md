# Atlas3K

A campaign map editor and builder for **Total War: THREE KINGDOMS**. It works on the Assembly Kit's own sources
(the `.terry` project, its layers and maps) and compiles the map **natively**, without BOB.

> **Alpha.** Back up your assembly kit (`raw_data\terrain\campaigns\<map>`, `working_data`) and your packs before
> building over them.

## What it does

| Part | What for |
|---|---|
| **Scene editor** | Props, entities, prefabs and layers of the campaign `.terry`, in a 2D top view and a 3D view (forests, water, rivers, seasons). |
| **Tile map** | Paint the campaign `tile_map.png` hex by hex. Every stroke is validated against BOB's tile-matching rules. |
| **Terrain painter** | Heights, ground textures and trees on the compiled map. |
| **Build** | Compile the map (rasters, tile list, global map and meshes, rivers, global props, camera heightmap, trees, lookup), run your own steps, pack and install. One click, or one step at a time. |

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

The **Profile** tab edits everything else:
- the compile output (default: the kit's `working_data`, as BOB did)
- tile-map codes to accept
- folders to clean before compiling
- a rolling backup folder
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

## Building from source

```
dotnet build Atlas3K.slnx -c Release
dotnet test src/Atlas3K.Tests
powershell -ExecutionPolicy Bypass -File tools\publish.ps1   # self-contained zip in dist\
```

The source needs the .NET 9 SDK (pinned in `global.json`).

See [KNOWN_ISSUES.md](KNOWN_ISSUES.md) and [CHANGELOG.md](CHANGELOG.md).

Not affiliated with Creative Assembly or SEGA. Total War: THREE KINGDOMS and its Assembly Kit are their property.
