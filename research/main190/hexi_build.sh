#!/bin/bash
# Hexi west pad (map only, 2026-10-01): everything after the terrain chain - tile map, kit + extents, CAIME, native
# campaign build into the kit, extras, stage, pack, startpos. Run after terrain_main/dem_fill/coast_carve/class_fill/korea_fix.
# 2026-10-04: BOB (Tilemap, Global Mesh x2, Terry file, lookup; ~20 min) replaced by the native build (~4 min, all cores;
# checked in game). The BOB version is hexi_build.sh.bob_20261004.
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
CLI=/z/Claude/TerryClone/src/Atlas3K.Cli/bin/Release/net9.0/Atlas3K.Cli.exe
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
KW="$(cygpath -w "$K/working_data")"
# native campaign build straight into the kit's working_data, where BOB wrote; stops the script if any step fails
native() { echo "=== native $1 $(date +%T)"; "$CLI" build-campaign --ak "$AK" --map $NEW --accept-tilemap layout.mesh_columns --steps "$1" --out "$KW" > /tmp/native_build.log 2>&1 || { grep -v "^\[" /tmp/native_build.log | tail -30; exit 1; }; grep -v "^\[" /tmp/native_build.log; }

B="$(cat /tmp/upscale_backup_dir)/hexi_pad"; mkdir -p "$B"
cp "$DD/!!190_expanded_region_test_main190.pack" "$B/pack_before.pack"
[ -d "$B/kit_working_terrain" ] || cp -r "$WT" "$B/kit_working_terrain" 2>/dev/null || true
[ -d "$B/kit_working_cmaps" ] || cp -r "$WC" "$B/kit_working_cmaps" 2>/dev/null || true
mkdir -p "$WT" "$WC"
echo "backups in $B"

echo "=== tree_clear / tilemap / ak $(date +%T)"
python tree_clear.py 2>&1 | tail -2
python caime_tilemap.py hex/map.hex caime_tilemap/tile_map_hexi.png --raw caime_tilemap/raw/caime_hexi.png --reexport --preview caime_tilemap/preview_hexi.png 2>&1 | grep -E "grid|reference|areas|hexi zone|final|wrote" | cut -c1-200
cp caime_tilemap/tile_map_hexi.png tile_map_rebuilt.png
python ak_main.py 2>&1 | tail -3

echo "=== kit install: region DB + extents $(date +%T)"
python install_ak.py --db-only 2>&1 | tail -10
for base in db EmpireDesignData; do cp ak_db/region_to_province_junctions.xml "$K/raw_data/$base/region_to_province_junctions.xml"; done
echo "  junctions: full x15 table installed (db + EmpireDesignData)"
python newmap_install.py 2>&1 | tail -4
touch "$K/raw_data/terrain/campaigns/$NEW/.kit_edits_pending"   # fresh install: replay allowed
python kit_edits.py || exit 1   # 2026-10-04: re-apply the kit edits (mountains, lakes, Korea inlet, town trees) over the fresh install
python newmap_packdb.py 2>&1 | tail -4; cat newmap.json; echo
grep -A8 "record_key=\"$NEW\"" "$K/raw_data/db/campaign_maps.xml" | grep -E "maxx|maxy"
for f in $(cd newmap_db/out && find db -name "*.tsv"); do add -t "$S" -f "$(cygpath -w "$PWD/newmap_db/out/$f");${f%.tsv}"; done

echo "=== CAIME $(date +%T)"; python caime_prefs.py set
rm -f $L; powershell.exe -NoProfile -Command "Start-Process -FilePath '$EXE' -ArgumentList @('validate','--map','\"$MAP\"','--all') -WorkingDirectory '$CDIR'; Start-Sleep 10; \$last=0; \$st=0; while ((Get-Process CAIME -ErrorAction SilentlyContinue) -and \$st -lt 25) { Start-Sleep 2; \$s=(Get-Item '$(cygpath -w $L)' -ErrorAction SilentlyContinue).Length; if (\$s -eq \$last) { \$st+=2 } else { \$st=0; \$last=\$s } }; Stop-Process -Name CAIME -Force -ErrorAction SilentlyContinue; exit 0"
cp $L caime_x15_validate.log; echo "  validate errors: $(grep -c '^Error' $L)"; grep "^Error" $L | sed -E 's/Hex\([0-9, ]+\)/Hex/g; s/[0-9]+/N/g' | sort | uniq -c | sort -rn | head -8
for t in --map-data --pathfinding --trade-routes --lookup; do caime $t; done
(cd /z/Claude/TerryClone/output/caime_upscaler && BORDERS_SRC="$MAP" BORDERS_OUT="$(cygpath -w "$WC")\\" dotnet test CAIME.Tests/CAIME.Tests.csproj --no-build -c Release --filter "FullyQualifiedName~ZzBordersExport" --logger "console;verbosity=detailed" 2>&1 | grep -E "borders exported|Failed")

touch /tmp/hxtf
# the generated folders are backed up above; native writes complete sets (its river patch names differ from BOB's)
rm -rf "$WT/global_meshes" "$WT/height_patches" "$WT/models"
native rasters,tile_list,global_map,global_mesh,rivers,global_props,camera_heightmap,lookup
python tile_holes.py "$WT/tile_list.bin" hex/map.hex holes/hx_tile.png --top 0 | grep uncovered || true

echo "=== extras / startpos chars $(date +%T)"
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
cp "$WC/camera_heightmap.png" "$SU/"
rm -rf stage_hx_terrain; mkdir stage_hx_terrain; cp -r "$WT/." stage_hx_terrain/; cp stage_newmap_terrain/environment_collection.xml stage_hx_terrain/
[ -d stage_hx_terrain/ambient_light_probes ] || cp -r stage_newmap_terrain/ambient_light_probes stage_hx_terrain/
echo "  stale terrain files: $(find stage_hx_terrain -type f ! -newer /tmp/hxtf ! -path '*ambient_light_probes*' ! -name environment_collection.xml ! -name 'lf_*' ! -name climate_map.cm ! -name tile_list.bin ! -path '*global_meshes*' ! -path '*global_map*' | wc -l)"
sleep 10

echo "=== pack $(date +%T)"
for i in 1 2 3 4 5; do /z/RPFM/rpfm_cli.exe --game three_kingdoms pack delete -p "$P" -F "terrain/campaigns/$NEW" -F "campaign_maps/$NEW" -f "campaigns/3k_main_campaign_map/startpos_historical.esf" -f "campaigns/3k_main_campaign_map/startpos_romance.esf" >/tmp/hb_add.log 2>&1 && break; sleep 15; done
add -F "$(cygpath -w "$PWD/stage_hx_terrain");terrain/campaigns/$NEW"
add -F "$(cygpath -w "$PWD/$SU");campaign_maps/$NEW"
for f in /z/Claude/TerryClone/output/lake_assets/$NEW/rigidmodels/campaign/props/lakes/190e_lake_*; do add -f "$(cygpath -w "$f");rigidmodels/campaign/props/lakes/$(basename "$f")"; done   # kit_edits.py lake-build models
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
