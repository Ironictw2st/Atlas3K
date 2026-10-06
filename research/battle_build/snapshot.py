"""Snapshot a kit battle project (sources + current BOB outputs) into the parity corpus.
usage: snapshot.py <kit root> <guid> <dest name: src|existing|bob_run1|bob_run2> [corpus root]
src      = raw_data/terrain/battles/<id> + raw_data/terrain/tiles/battle/_assembly_kit/<id>
others   = working_data/terrain/battles/<id> + working_data/terrain/tiles/battle/_assembly_kit/<id>
           + working_data/terrain/tiles/battle/_tile_database/TILES/_assembly_kit_<id>.*"""
import os, shutil, sys, glob
AK, GID, WHAT = sys.argv[1:4]
CORPUS = sys.argv[4] if len(sys.argv) > 4 else r"Z:/Claude/BattleMaps/out/battle_parity"
dst = os.path.join(CORPUS, GID, WHAT)
if os.path.exists(dst): shutil.rmtree(dst)
tree = "raw_data" if WHAT == "src" else "working_data"
parts = {"map": f"{tree}/terrain/battles/{GID}", "tile": f"{tree}/terrain/tiles/battle/_assembly_kit/{GID}"}
n = 0
for k, rel in parts.items():
    s = os.path.join(AK, rel)
    if os.path.isdir(s):
        shutil.copytree(s, os.path.join(dst, k)); n += sum(len(f) for _, _, f in os.walk(s))
if tree == "working_data":
    for f in glob.glob(os.path.join(AK, "working_data/terrain/tiles/battle/_tile_database/TILES", f"_assembly_kit_{GID}.*")):
        os.makedirs(os.path.join(dst, "tile_db"), exist_ok=True); shutil.copy2(f, os.path.join(dst, "tile_db")); n += 1
print(f"{WHAT}: {n} files -> {dst}")
