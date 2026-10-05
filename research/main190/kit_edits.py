#!/usr/bin/env python3
"""Replay the hand / audit edits made directly in the kit with TerryClone (2026-10-04) after a pipeline install.

relief_build.sh / props_only.sh / hexi_build.sh regenerate the kit's layers (ak_main.py) and height map
(terrain/<map>.height.*.tif) from the research sources, which drops anything edited in the kit itself. Each build
script runs this right after it installs layers + height into the kit and before the native build, so the edits come
back every time. All steps go through the TerryClone CLI (journaled, entity-undo works as usual).

EDITS, in order:
 1. kit_edits/01_sink_floating_mountains.json - 50 LF-offset mountains that floated in game (y only: x, z stay
    where the current pipeline put them).
 2. lake-build --apply - the raised lakes (Qinghai, Dunhuang, Yuanquan, Juyan x2) as one flat water mesh each with
    the shore shaped. Replaces lake_props.py's small_lake_1 discs (ak_main no longer adds those). Writes the lake
    models to output/lake_assets/<map>/, which the build scripts pack.
 3. sea-carve - the Korea sea inlet (903.8, 539.43) carved below sea level so the game's sea water fills it.
 3b. terrain-scale - Tamna (Jeju) heights above sea level x0.6 (user 2026-10-04: "flatten out Tamna a bit"); its
    absolute-height props follow the ground.
 4. kit_edits/04_trees_crowding_towns.json - map-audit on-city-footprint batch (106 trees on new towns' hexes).
 5-8. kit_edits/05..08 (2026-10-04, new-areas look-over): Yingtao vegetation (20), inherited duplicate props (159),
    floating rocks (2, y only), buried mountains (3, y only).
Deterministic: from the same research height map (SHA-1 5217E349...) this reproduces the 2026-10-04 kit exactly.
Ops whose entity is no longer in the kit are skipped and counted (ids are stable while the source layers are).
To add an edit: put its ops json in kit_edits/ and a line in EDITS.
"""
import json, os, re, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).parent
CLI = r"Z:/Claude/TerryClone/src/TerryClone.Cli/bin/Release/net9.0/TerryClone.Cli.exe"
AK = os.environ.get("KIT_EDITS_AK", r"C:/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/assembly_kit_190E")  # sandbox tests
PACK = r"C:/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/data/!!190_expanded_region_test_main190_native.pack"
MAP = "3k_190e_expanded_map"
RT = Path(AK) / "raw_data" / "terrain" / "campaigns" / MAP

EDITS = [
    ("ops", "01_sink_floating_mountains.json", "kit_edits: sink floating mountains", "y_only"),
    ("cli", ["lake-build", "--pack", PACK, "--apply"], "lake-build"),
    ("cli", ["sea-carve", "--at", "903.8,539.43", "--radius", "3", "--apply"], "sea-carve Korea inlet"),
    ("cli", ["terrain-scale", "--pack", PACK, "--at", "869.0,489.52", "--radius", "25", "--factor", "0.6", "--apply"], "flatten Tamna x0.6"),
    ("cli", ["river-bed", "--min-depth", "0.9", "--rect", "426,604,446,640", "--apply"], "Yellow River bed by Xihe (pale water)"),
    ("ops", "04_trees_crowding_towns.json", "kit_edits: trees crowding new towns", None),
    ("ops", "05_yingtao_trees.json", "kit_edits: clear trees around Yingtao", None),
    ("ops", "06_remove_duplicates_new_areas.json", "kit_edits: duplicate props (new areas)", None),
    ("ops", "07_seat_floating_rocks.json", "kit_edits: seat floating rocks", "y_only"),
    ("ops", "08_lift_buried_mountains.json", "kit_edits: lift buried mountains", "y_only"),
    ("ops", "09_seat_floating_rocks_2.json", "kit_edits: seat floating rocks (after polish)", "y_only"),
    ("ops", "10_pass_gates_x1_5.json", "kit_edits: pass gates x1.5 (1x-map proportions)", None),
    ("ops", "11_pass_gate_tops_raise.json", "kit_edits: pass gate tops onto the x1.5 gatehouses", "y_only"),
]


def cli(args):
    r = subprocess.run([CLI, *args, "--ak", AK, "--map", MAP], capture_output=True, text=True, encoding="utf-8")
    out = r.stdout.strip()
    if r.returncode != 0 or out.startswith('{\n  "error"') or '"error":' in out[:200]:
        sys.exit(f"kit_edits: {' '.join(args[:1])} failed:\n{out[-1500:]}\n{r.stderr[-800:]}")
    return out


def positions(layer_id):
    """entity id -> ECTransform position string, in the kit's copy of one layer."""
    p = RT / f"{MAP}.{layer_id}.layer"
    if not p.exists(): return {}
    t = p.read_text(encoding="utf-8")
    return {m.group(1): m.group(2) for m in re.finditer(r'<entity id="([0-9a-f]+)">.*?<ECTransform position="([^"]*)"', t, re.S)}


def replay_ops(name, label, mode):
    ops = json.load(open(HERE / "kit_edits" / name, encoding="utf-8"))
    cache, keep, skipped = {}, [], 0
    for op in ops:
        layer = op.get("in_layer")
        pos = cache.setdefault(layer, positions(layer))
        if op["id"] not in pos: skipped += 1; continue
        if mode == "y_only" and "ECTransform.position" in op.get("fields", {}):
            x, _, z = pos[op["id"]].split(); y = op["fields"]["ECTransform.position"].split()[1]
            op = {**op, "fields": {**op["fields"], "ECTransform.position": f"{x} {y} {z}"}}
        keep.append(op)
    if keep:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(keep, f); tmp = f.name
        try: cli(["entity-edit", "--ops", tmp, "--label", label])
        finally: os.unlink(tmp)
    print(f"  {label}: {len(keep)} applied, {skipped} skipped (entity not in the kit)")


PENDING = RT / ".kit_edits_pending"   # written by the build scripts right after they install fresh layers + height


def main():
    # lake-build and terrain-scale are NOT idempotent (a second pass re-shapes / re-flattens): only replay over a
    # fresh install (2026-10-04: a second run on an already-replayed kit flattened Tamna twice; undone via the journal)
    if not PENDING.exists() and "--force" not in sys.argv:
        sys.exit(f"kit_edits: no {PENDING.name} in the kit - the edits are already replayed over the last install "
                 f"(a second pass would re-shape the lakes and flatten Tamna again). Use --force only on a fresh install.")
    for e in EDITS:
        if e[0] == "ops": replay_ops(e[1], e[2], e[3])
        else:
            out = cli(e[1])
            j = json.loads(out[out.index("{"):])
            print(f"  {e[2]}: " + ", ".join(f"{k} {v}" for k, v in j.items() if k in ("deletes", "creates", "cells_lowered", "discs_removed", "cells", "props_moved", "bed_cells_lowered")))


if __name__ == "__main__":
    main()
    PENDING.unlink(missing_ok=True)
