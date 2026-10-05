#!/bin/bash
# Native rebuild from the kit AS IT IS (2026-10-04): for edits made directly in the kit with Atlas3K (entity-edit,
# lake-build, sea-carve, map-audit batches). Unlike relief_build.sh / props_only.sh it does NOT run ranges_relief /
# ak_main or copy layers + height into the kit, which would overwrite those edits.
# native rasters, tile list, global map + meshes, rivers, global_props, camera_heightmap, trees -> tree filter ->
# pack into the native test pack, plus the lake models from output/lake_assets (lake-build).
set -e
export PYTHONIOENCODING=utf-8 PATH="$PATH:/c/Windows/System32:/c/Windows/System32/WindowsPowerShell/v1.0"
cd /z/Claude/TerryClone/research/main190
DD="/c/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/data"
AK='C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\assembly_kit_190E'
K="/c/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/assembly_kit_190E"
NEW=3k_190e_expanded_map; WT="$K/working_data/terrain/campaigns/$NEW"; RT="$K/raw_data/terrain/campaigns/$NEW"
PN='!!190_expanded_region_test_main190_native.pack'
P="C:\\Program Files (x86)\\Steam\\steamapps\\common\\Total War THREE KINGDOMS\\data\\$PN"
CLI=/z/Claude/TerryClone/src/Atlas3K.Cli/bin/Release/net9.0/Atlas3K.Cli.exe
LAKES=/z/Claude/TerryClone/output/lake_assets/$NEW/rigidmodels/campaign/props/lakes
add() { for i in 1 2 3 4 5; do /z/RPFM/rpfm_cli.exe --game three_kingdoms pack add -p "$P" "$@" >/tmp/kb_add.log 2>&1 && { echo "  added ${2##*;}"; return 0; }; sleep 20; done; echo "  FAILED $2"; tail -3 /tmp/kb_add.log; exit 1; }
KW="$(cygpath -w "$K/working_data")"; WC="$K/working_data/campaign_maps/$NEW"
native() { echo "=== native $1 $(date +%T)"; "$CLI" build-campaign --ak "$AK" --map $NEW --accept-tilemap layout.mesh_columns --steps "$1" --out "$KW" > /tmp/native_build.log 2>&1 || { grep -v "^\[" /tmp/native_build.log | tail -30; exit 1; }; grep -v "^\[" /tmp/native_build.log; }
# HOLD is shared with other sessions (BOB / game work): never run over someone else's, only remove our own
[ -f /z/Claude/Headless/HOLD ] && { echo "HOLD present (another session) - abort"; exit 1; }
touch /z/Claude/Headless/HOLD
if [ "$1" = "--resume" ]; then
  # after a stop at global_map: restore its folder (texture_arrays.xml is copied from there) and redo that step only
  B=/z/Claude/TerryClone/output/backups/main190_kit_edits_last; echo "resume, backups in $B"
  cp -n "$B/working_terrain/global_map/"* "$WT/global_map/" 2>/dev/null || { mkdir -p "$WT/global_map"; cp "$B/working_terrain/global_map/"* "$WT/global_map/"; }
  native global_map
else
  # one rolling terrain backup (overwritten each run) + one pack backup from before the first kit-edits build;
  # a full copy per run filled Z: on 2026-10-04 (7 x 4.8 GB). The 2026-10-04 original: main190_kit_edits_20261004_171002.
  B=/z/Claude/TerryClone/output/backups/main190_kit_edits_last; rm -rf "$B"; mkdir -p "$B"
  cp -r "$RT" "$B/raw_terrain"; cp -r "$WT" "$B/working_terrain"; echo "terrain backup in $B"
  PB="$(ls /z/Claude/TerryClone/output/backups/main190_kit_edits_20261004_171002/*.pack 2>/dev/null | head -1)"; PB=${PB:-/z/Claude/TerryClone/output/backups/main190_native_pre_kit_edits.pack}
  [ -f "$PB" ] || { cp "$DD/$PN" "$PB"; echo "pack backup $PB"; }
  # native writes complete sets of these (backed up above); global_map is kept: its texture_arrays.xml is the step's source
  rm -rf "$WT/global_meshes" "$WT/height_patches" "$WT/models"
  native rasters,tile_list,global_map,global_mesh,rivers,global_props,camera_heightmap,trees
fi
python tile_holes.py "$WT/tile_list.bin" hex/map.hex holes/rr_tile.png --all --top 10 | grep -E "uncovered" || true

echo "=== tree list $(date +%T)"
TL="$WC/display/trees/trees.campaign_tree_list"
python -c "
from pathlib import Path; from tree_clear import tree_mask, filter_tree_list
m, wh = tree_mask(); filter_tree_list(Path(r'''$(cygpath -w "$TL")'''), m, wh)"
rm -rf stage_hx_terrain; mkdir stage_hx_terrain; cp -r "$WT/." stage_hx_terrain/; cp stage_newmap_terrain/environment_collection.xml stage_hx_terrain/
[ -d stage_hx_terrain/ambient_light_probes ] || cp -r stage_newmap_terrain/ambient_light_probes stage_hx_terrain/
sleep 5
echo "=== pack $(date +%T)"
for i in 1 2 3 4 5; do /z/RPFM/rpfm_cli.exe --game three_kingdoms pack delete -p "$P" -F "terrain/campaigns/$NEW" -f "campaign_maps/$NEW/camera_heightmap.png" -f "campaign_maps/$NEW/display/trees/trees.campaign_tree_list" >/tmp/kb_add.log 2>&1 && break; sleep 15; done
add -F "$(cygpath -w "$PWD/stage_hx_terrain");terrain/campaigns/$NEW"
add -f "$(cygpath -w "$WC/camera_heightmap.png");campaign_maps/$NEW/camera_heightmap.png"
add -f "$(cygpath -w "$TL");campaign_maps/$NEW/display/trees/trees.campaign_tree_list"
for f in "$LAKES"/190e_lake_*; do add -f "$(cygpath -w "$f");rigidmodels/campaign/props/lakes/$(basename "$f")"; done
# (no per-run copy of the built pack: rebuild from the kit instead)
rm -f /z/Claude/Headless/HOLD
echo "=== done $(date +%T)"
