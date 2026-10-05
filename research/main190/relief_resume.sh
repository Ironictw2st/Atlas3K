#!/bin/bash
# Resume of relief_build.sh after the tile list (tile_list.bin already fresh in the kit). Terrain relief rebuild (ranges_relief.py; 2026-10-03).
# native global map + meshes, rivers, global_props, camera_heightmap -> tree list -> pack. No tile list / CAIME / startpos.
# 2026-10-04: BOB (Global Mesh x2, Terry file) replaced by the native build (checked in game); BOB version: relief_resume.sh.bob_20261004.
set -e
export PYTHONIOENCODING=utf-8 PATH="$PATH:/c/Windows/System32:/c/Windows/System32/WindowsPowerShell/v1.0"
cd /z/Claude/TerryClone/research/main190
DD="/c/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/data"
AK='C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\assembly_kit_190E'
K="/c/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/assembly_kit_190E"
NEW=3k_190e_expanded_map; OLD=3k_dlc07_main_map; WT="$K/working_data/terrain/campaigns/$NEW"; RT="$K/raw_data/terrain/campaigns/$NEW"
P='C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\data\!!190_expanded_region_test_main190.pack'
CLI=/z/Claude/TerryClone/src/TerryClone.Cli/bin/Release/net9.0/TerryClone.Cli.exe
OUTW='Z:\Claude\TerryClone\research\main190\build_newmap'
mode() { (cd "$DD" && python - "$1" "$2" <<'PY'
import struct, sys
t = int(sys.argv[1])
for n in sys.argv[2].split(","):
    with open(n, "r+b") as f:
        f.seek(4); v = struct.unpack("<I", f.read(4))[0]; f.seek(4); f.write(struct.pack("<I", (v & ~15) | t)); print(n, "type", t)
PY
); }
add() { for i in 1 2 3 4 5; do /z/RPFM/rpfm_cli.exe --game three_kingdoms pack add -p "$P" "$@" >/tmp/hb_add.log 2>&1 && { echo "  added ${2##*;}"; return 0; }; sleep 20; done; echo "  FAILED $2"; tail -3 /tmp/hb_add.log; exit 1; }
KW="$(cygpath -w "$K/working_data")"; WC="$K/working_data/campaign_maps/$NEW"
# native campaign build straight into the kit's working_data, where BOB wrote; stops the script if any step fails
native() { echo "=== native $1 $(date +%T)"; "$CLI" build-campaign --ak "$AK" --map $NEW --accept-tilemap layout.mesh_columns --steps "$1" --out "$KW" > /tmp/native_build.log 2>&1 || { grep -v "^\[" /tmp/native_build.log | tail -30; exit 1; }; grep -v "^\[" /tmp/native_build.log; }
touch /z/Claude/Headless/HOLD
python tile_holes.py "$WT/tile_list.bin" hex/map.hex holes/rr_tile.png --all --top 10 | grep -E "uncovered" || true
# native writes complete sets of these (its river patch names differ from BOB's); relief_build.sh backed them up
rm -rf "$WT/global_meshes" "$WT/height_patches" "$WT/models"
native global_map,global_mesh,rivers,global_props,camera_heightmap

echo "=== tree list $(date +%T)"
python -c "import extras_main; extras_main.trees()" 2>&1 | tail -1
python tree_clear.py 2>&1 | grep "tree list" || true
TL=map_extras/campaign_maps/$NEW/display/trees/trees.campaign_tree_list
rm -rf stage_hx_terrain; mkdir stage_hx_terrain; cp -r "$WT/." stage_hx_terrain/; cp stage_newmap_terrain/environment_collection.xml stage_hx_terrain/
[ -d stage_hx_terrain/ambient_light_probes ] || cp -r stage_newmap_terrain/ambient_light_probes stage_hx_terrain/
sleep 5
echo "=== pack $(date +%T)"
for i in 1 2 3 4 5; do /z/RPFM/rpfm_cli.exe --game three_kingdoms pack delete -p "$P" -F "terrain/campaigns/$NEW" -f "campaign_maps/$NEW/camera_heightmap.png" -f "campaign_maps/$NEW/display/trees/trees.campaign_tree_list" >/tmp/hb_add.log 2>&1 && break; sleep 15; done
add -F "$(cygpath -w "$PWD/stage_hx_terrain");terrain/campaigns/$NEW"
add -f "$(cygpath -w "$WC/camera_heightmap.png");campaign_maps/$NEW/camera_heightmap.png"
add -f "$(cygpath -w "$PWD/$TL");campaign_maps/$NEW/display/trees/trees.campaign_tree_list"
cp "$DD/!!190_expanded_region_test_main190.pack" /z/Claude/TerryClone/output/backups/main190_relief_built_$(date +%Y%m%d_%H%M).pack && echo "backed up"
rm -f /z/Claude/Headless/HOLD
echo "=== done $(date +%T)"
