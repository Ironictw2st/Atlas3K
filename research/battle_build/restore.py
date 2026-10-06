"""Put a kit battle project's working_data outputs back to a corpus snapshot (default: 'existing').
usage: restore.py <kit root> <guid> [snapshot name] [corpus root]"""
import glob, os, shutil, sys

AK, GID = sys.argv[1:3]
WHAT = sys.argv[3] if len(sys.argv) > 3 else "existing"
CORPUS = sys.argv[4] if len(sys.argv) > 4 else r"Z:/Claude/BattleMaps/out/battle_parity"
snap = os.path.join(CORPUS, GID, WHAT)
targets = {"map": f"working_data/terrain/battles/{GID}", "tile": f"working_data/terrain/tiles/battle/_assembly_kit/{GID}"}
for k, rel in targets.items():
    dst = os.path.join(AK, rel)
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    if os.path.isdir(os.path.join(snap, k)):
        shutil.copytree(os.path.join(snap, k), dst)
tdb = os.path.join(AK, "working_data/terrain/tiles/battle/_tile_database/TILES")
for f in glob.glob(os.path.join(tdb, f"_assembly_kit_{GID}.*")):
    os.remove(f)
for f in glob.glob(os.path.join(snap, "tile_db", "*")):
    shutil.copy2(f, tdb)
print(f"restored {GID} from {snap}")
