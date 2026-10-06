# Battle-map BOB parity corpus: scripts

The ground-truth corpus for the native battle-map build is in `Z:\Claude\BattleMaps\out\battle_parity\`, outside the
repo because it is generated from game data. Its `README.md` documents:
- the BOB action order and which action writes which file;
- determinism, masks and record-order variants;
- the projects.

Compare a native build with it:

```
Atlas3K.Cli battle-parity Z:\Claude\BattleMaps\out\battle_parity\<id> <native out dir>     # one project
Atlas3K.Cli battle-parity Z:\Claude\BattleMaps\out\battle_parity <native root>             # every project, <native root>\<id>
```

`<native out dir>` can use the corpus layout (`map/`, `tile/`, `tile_db/`) or a working_data-like tree
(`terrain/battles/<id>`, `terrain/tiles/battle/_assembly_kit/<id>`, `terrain/tiles/battle/_tile_database/TILES`).
Exit code 0 means everything matched: identical, masked-identical, or identical to another BOB run.

## Scripts

| Script | What it does |
|---|---|
| `snapshot.py <kit> <id> <src\|existing\|bob_runN>` | Copies a kit project's sources (raw_data) or outputs (working_data + tile database entry) into the corpus |
| `run_bob_battle_export.py <kit> <id> <label> [--keep-outputs]` | Runs the full BOB export with Terry's "Process with BOB" configuration, without the Pack processor. It deletes the old outputs first (but keeps the Terry-written rules.bob and tile database entry) and copies the logs to the corpus |
| `restore.py <kit> <id> [snapshot]` | Puts the kit's working_data outputs back to a snapshot (default `existing`) |
| `make_masks.py` | Diffs every `bob_run*` of each project. Uninitialised words go to `masks.json`; files whose record order varies between runs go to `_order_variants` |
| `make_rich_project.py <corpus project> <kit> <guid> [--remove]` | Builds the "rich" project as a COPY under a new GUID: a vista map folder plus capture-point and deployment prefabs, both as references and inlined |
| `make_round2_project.py <spec> <kit> install\|remove [--atlas exe]` | Round-2 projects (specs `r2_tmp_forest`, `r2_cld_siege`, `r2_multi_climate` in the script): COPIES of corpus sources with a painted blend map (procedural trees), another vista / climate_mask, hand-placed ECVegetation, extra rivers, wall / gate / siege-AI prefabs. The Terry-written inputs come from `build-battle --only terry_save` |

Round 2 (procedural trees, cold, siege, several climates, several rivers) and why round 1 placed no procedural objects
are in the corpus README ("Round 2"); the native-vs-BOB results per file are in `docs/native_battle_build.md`
("Round 2 corpus").

Every assembly-kit tile in the kit's tile database is a tile-matching candidate, so other kit maps installed during a
run change `tile_list.bin`. Round 2's cold and multi-climate runs had the sibling round-2 projects installed: their
tile database entries are recorded in `<corpus>/<id>/kit_tile_db/`, which `build-battle --corpus` and the tests read as
extra loose entries (`BattleBuildContext.ExtraTileDbDirs`). Install one project at a time for new runs.

Typical sequence for a new project:
1. Take the BOB lock: `mkdir Z:/Claude/Headless/bob_lock` plus an owner file.
2. `snapshot.py … src`, then `snapshot.py … existing`.
3. `run_bob_battle_export.py … runN` followed by `snapshot.py … bob_runN`, at least 3 times.
4. `restore.py …`.
5. Remove the lock.
6. Run `make_masks.py`.
