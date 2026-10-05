#!/bin/bash
# Hexi west pad (map only, 2026-10-01): everything after the terrain chain - tile map, kit + extents, CAIME, native lf
# into the kit, BOB, camera, extras, stage, pack, startpos. Run after terrain_main/dem_fill/coast_carve/class_fill/korea_fix.
set -e
export PYTHONIOENCODING=utf-8 PATH="$PATH:/c/Windows/System32:/c/Windows/System32/WindowsPowerShell/v1.0"
cd /z/Claude/TerryClone/research/main190
if tasklist | grep -qi Three_Kingdoms; then echo "GAME RUNNING - abort"; exit 1; fi
DD="/c/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/data"
AK='C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\assembly_kit_190E'
K="/c/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/assembly_kit_190E"
NEW=3k_190e_expanded_map; WC="$K/working_data/campaign_maps/$NEW"; WT="$K/working_data/terrain/campaigns/$NEW"
P='C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\data\!!190_expanded_region_test_main190.pack'
S="$(cygpath -w "$APPDATA")\\FrodoWazEre\\rpfm\\config\\schemas\\schema_3k.ron"
EXE='Z:\Claude\TerryClone\output\caime_upscaler\CAIME\bin\CAIME.exe'; CDIR='Z:\Claude\TerryClone\output\caime_upscaler\CAIME\bin'
MAP="$(cygpath -w "$K/raw_data/EmpireDesignData/campaign_maps/$NEW/map.hex")"
L=/z/Claude/TerryClone/output/caime_upscaler/CAIME/bin/tool.log
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
PACKS3='!!190_expanded_region_test_main190.pack,!!190_expanded_with_charactersIntrex.pack,mtu_startpos_ironic.pack'
add() { for i in 1 2 3 4 5; do /z/RPFM/rpfm_cli.exe --game three_kingdoms pack add -p "$P" "$@" >/tmp/hb_add.log 2>&1 && { echo "  added ${2##*;}"; return 0; }; sleep 20; done; echo "  FAILED $2"; tail -3 /tmp/hb_add.log; exit 1; }
caime() {
  powershell.exe -NoProfile -Command "\$p = Start-Process -FilePath '$EXE' -ArgumentList @('process','--map','\"$MAP\"','$1') -WorkingDirectory '$CDIR' -PassThru -Wait; '$1 exit ' + \$p.ExitCode; while (Get-Process CAIME -ErrorAction SilentlyContinue) { Start-Sleep 2 }"
  grep -E "^Error" $L | head -3 || true
}
bob() { (cd /z/Claude/TerryClone/tools/bob_mcp && timeout 3550 python run_bob.py --ak "$AK" "$1" "$2" --timeout 3500 --label "$3" 2>&1 | python -c 'import json,sys; d=json.load(sys.stdin); print({k:d.get(k) for k in ("result","seconds","failed_to_find_tile","bob_error_log_lines","reason")})'); }
killbob() { powershell.exe -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { \$_.Name -match '^bob' -and \$_.CommandLine -match '_bobmcp_gui' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force }" || true; }


echo "fix-campaign-maps-pack-entry: x15 build (BOB onward)" > /z/Claude/Headless/HOLD
echo "=== BOB $(date +%T)"; mode 4 '!!190_expanded_region_test_main190.pack'
bob "raw_data/terrain/campaigns/$NEW" Tilemap hx_tile
python tile_holes.py "$WT/tile_list.bin" hex/map.hex holes/hx_tile.png --top 0 | grep uncovered || true
for n in 1 2; do echo "=== GM$n $(date +%T)"; bob "raw_data/terrain/campaigns/$NEW" "Global Mesh" hx_gm$n; done
killbob
echo "=== Terry file $(date +%T)"; touch /tmp/hxtf
(cd /z/Claude/TerryClone/tools/bob_mcp && BOB_AK="$AK" timeout 3550 python - "$NEW" <<'PY' 2>&1 | grep -v Warn | tail -1
import sys; sys.path.insert(0, '.')
import server
new = sys.argv[1]
f = getattr(server.bob_run_action, 'fn', server.bob_run_action)
r = f(f'raw_data/terrain/campaigns/{new}', f'Terrain / Terry file  (c:/program files (x86)/steam/steamapps/common/total war three kingdoms/assembly_kit_190e/raw_data/terrain/campaigns/{new}/{new}.terry)', timeout=3400, mode='gui', capture_label='hx_terryfile')
print({k: r.get(k) for k in ('result', 'seconds', 'bob_error_log_lines', 'reason')})
PY
)
killbob
echo "  models fresh $(find "$WT/models" -newer /tmp/hxtf -type f | wc -l)/$(ls "$WT/models" | wc -l), patches fresh $(find "$WT/height_patches" -newer /tmp/hxtf -type f | wc -l)"
bob "working_data/campaign_maps/$NEW/3k_main_campaign_map_lookup.bmp" "Convert lookup texture" hx_lookup
mode 3 '!!190_expanded_region_test_main190.pack'

echo "=== camera / extras / startpos chars $(date +%T)"
$CLI build-campaign --steps camera_heightmap --ak "$AK" --map $NEW --out "$OUTW" | tail -1
python extras_main.py 2>&1 | tail -3; python tree_clear.py 2>&1 | tail -1
python startpos_shift.py 2>&1 | head -1

echo "=== stage $(date +%T)"
rm -rf stage_hx; mkdir -p stage_hx/$NEW/display/borders stage_hx/$NEW/display/trees; SU=stage_hx/$NEW
cp -r map_extras/campaign_maps/$NEW/. "$SU/"
cp "$WC/map_data.esf" "$WC/pathfinding.ppd" "$WC/trade_routes.ptd" "$SU/"
cp "$WC/display/borders/borders.pbd" "$SU/display/borders/"; cp "$WC/display/borders/borders.pbd" "$SU/borders.pbd"
cp -r stage_up/$NEW/display/borders/textures "$SU/display/borders/" 2>/dev/null || true
cp stage_up/$NEW/display/area_of_interest_spline.dds "$SU/display/"
for x in dds tga; do cp "$WC/3k_main_campaign_map_lookup.$x" "$SU/"; cp "$WC/3k_main_campaign_map_lookup.$x" "$SU/3k_main_lookup.$x"; done
cp "$WC/3k_main_campaign_map_lookup_minimap.tga" "$SU/"; cp "$WC/3k_main_campaign_map_lookup_minimap.tga" "$SU/3k_main_lookup_minimap.tga"
cp build_newmap/campaign_maps/$NEW/camera_heightmap.png "$SU/"
rm -rf stage_hx_terrain; mkdir stage_hx_terrain; cp -r "$WT/." stage_hx_terrain/; cp stage_newmap_terrain/environment_collection.xml stage_hx_terrain/
echo "  stale terrain files: $(find stage_hx_terrain -type f ! -newer /tmp/hxtf ! -path '*ambient_light_probes*' ! -name environment_collection.xml ! -name 'lf_*' ! -name climate_map.cm ! -name tile_list.bin ! -path '*global_meshes*' ! -path '*global_map*' | wc -l)"
sleep 10

echo "=== pack $(date +%T)"
for i in 1 2 3 4 5; do /z/RPFM/rpfm_cli.exe --game three_kingdoms pack delete -p "$P" -F "terrain/campaigns/$NEW" -F "campaign_maps/$NEW" -f "campaigns/3k_main_campaign_map/startpos_historical.esf" -f "campaigns/3k_main_campaign_map/startpos_romance.esf" >/tmp/hb_add.log 2>&1 && break; sleep 15; done
add -F "$(cygpath -w "$PWD/stage_hx_terrain");terrain/campaigns/$NEW"
add -F "$(cygpath -w "$PWD/$SU");campaign_maps/$NEW"
for f in $(cd db_out && find db text -name "*.tsv"); do add -t "$S" -f "$(cygpath -w "$PWD/db_out/$f");${f%.tsv}"; done
for f in $(cd db_scale && find db -name "*.tsv"); do add -t "$S" -f "$(cygpath -w "$PWD/db_scale/$f");${f%.tsv}"; done

echo "=== startpos $(date +%T)"
powershell.exe -NoProfile -Command "if (-not (Get-NetTCPConnection -LocalPort 45127 -State Listen -ErrorAction SilentlyContinue)) { Start-Process -FilePath Z:\RPFM\rpfm_server.exe -WorkingDirectory Z:\RPFM -WindowStyle Minimized; Start-Sleep 6 }; 'rpfm ok'"
mode 4 "$PACKS3"
cd /z/Claude/TerryClone/research/guandu
python /tmp/sp_build7.py open 2>&1 | tail -1 | cut -c1-80
python /tmp/sp_build7.py build1 2>&1 | tail -1 | cut -c1-300
ls -la "$DD/campaigns/3k_main_campaign_map" "$DD/campaign_maps/$NEW" 2>&1 | grep -i "esf\|cannot" || true
python /tmp/sp_build7.py post 2>&1 | cut -c1-110
BL=/z/Claude/TerryClone/output/backups/main190_hx_startpos_loose_$(date +%Y%m%d_%H%M%S); mkdir -p "$BL"
mv "$DD/campaigns/3k_main_campaign_map" "$BL/c" 2>/dev/null || true; [ -d "$DD/campaign_maps/$NEW" ] && mv "$DD/campaign_maps/$NEW" "$BL/m"; rmdir "$DD/campaign_maps" 2>/dev/null || true
mode 3 "$PACKS3"
/z/RPFM/rpfm_cli.exe --game three_kingdoms pack list -p "$P" 2>/dev/null | grep -E "campaigns/3k_main_campaign_map/startpos|$NEW/(hlp|spd|map_data|pathfinding)"
cp "$DD/!!190_expanded_region_test_main190.pack" /z/Claude/TerryClone/output/backups/main190_hexi_pad_built_$(date +%Y%m%d_%H%M).pack && echo "backed up"
python /z/Claude/TerryClone/research/main190/caime_prefs.py restore
rm -f /z/Claude/Headless/HOLD
echo "=== done $(date +%T)"
