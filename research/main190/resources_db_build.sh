#!/bin/bash
# Resource re-theme DB build (2026-10-04): retemplate_x15 on db_out/ak_db -> kit DB -> pack DB -> startpos. No map/terrain steps.
# into the kit, BOB, camera, extras, stage, pack, startpos. Run after terrain_main/dem_fill/coast_carve/class_fill/korea_fix.
set -e
export PYTHONIOENCODING=utf-8 PATH="$PATH:/c/Windows/System32:/c/Windows/System32/WindowsPowerShell/v1.0"
cd /z/Claude/TerryClone/research/main190
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
bob() { (cd /z/Claude/TerryClone/tools/bob_mcp && timeout 3550 python run_bob.py --ak "$AK" "$1" "$2" --timeout 3500 --label "$3" 2>&1 | python -c 'import json,sys; d=json.load(sys.stdin); print({k:d.get(k) for k in ("result","seconds","failed_to_find_tile","bob_error_log_lines","reason")})'); }
if powershell.exe -NoProfile -Command "if (Get-Process Three_Kingdoms -ErrorAction SilentlyContinue) { exit 1 }"; then :; else echo "GAME RUNNING - abort"; exit 1; fi
touch /z/Claude/Headless/HOLD
B=/z/Claude/TerryClone/output/backups/main190_resources_$(date +%Y%m%d_%H%M%S); mkdir -p "$B"
cp "$DD/!!190_expanded_region_test_main190.pack" "$B/"; cp -r db_out "$B/db_out"; cp -r ak_db "$B/ak_db"; echo "backups in $B"
echo "=== retemplate (resource re-theme) $(date +%T)"
python -c "import retemplate_x15; retemplate_x15.main()" 2>&1 | tail -6
echo "=== kit DB $(date +%T)"
python install_ak.py --db-only 2>&1 | tail -3
for base in db EmpireDesignData; do cp ak_db/region_to_province_junctions.xml "$K/raw_data/$base/region_to_province_junctions.xml"; done
echo "=== pack DB $(date +%T)"
for f in $(cd db_out && find db text -name "*.tsv"); do add -t "$S" -f "$(cygpath -w "$PWD/db_out/$f");${f%.tsv}"; done | tail -3
for i in 1 2 3 4 5; do /z/RPFM/rpfm_cli.exe --game three_kingdoms pack delete -p "$P" -f "campaigns/3k_main_campaign_map/startpos_historical.esf" -f "campaigns/3k_main_campaign_map/startpos_romance.esf" >/tmp/hb_add.log 2>&1 && break; sleep 15; done
echo "=== startpos $(date +%T)"
powershell.exe -NoProfile -Command "if (-not (Get-NetTCPConnection -LocalPort 45127 -State Listen -ErrorAction SilentlyContinue)) { Start-Process -FilePath Z:\RPFM\rpfm_server.exe -WorkingDirectory Z:\RPFM -WindowStyle Minimized; Start-Sleep 6 }; 'rpfm ok'"
mode 4 "$PACKS3"
SP=/z/Claude/TerryClone/research/main190/sp_build7.py
cd /z/Claude/TerryClone/research/guandu
python $SP open 2>&1 | tail -1 | cut -c1-80
python $SP build1 2>&1 | tail -1 | cut -c1-300
python $SP post 2>&1 | cut -c1-110
BL=/z/Claude/TerryClone/output/backups/main190_res_startpos_loose_$(date +%Y%m%d_%H%M%S); mkdir -p "$BL"
mv "$DD/campaigns/3k_main_campaign_map" "$BL/c" 2>/dev/null || true; [ -d "$DD/campaign_maps/$NEW" ] && mv "$DD/campaign_maps/$NEW" "$BL/m"; rmdir "$DD/campaign_maps" 2>/dev/null || true
mode 3 "$PACKS3"
/z/RPFM/rpfm_cli.exe --game three_kingdoms pack list -p "$P" 2>/dev/null | grep -E "campaigns/3k_main_campaign_map/startpos"
cp "$DD/!!190_expanded_region_test_main190.pack" /z/Claude/TerryClone/output/backups/main190_resources_built_$(date +%Y%m%d_%H%M).pack && echo "backed up"
rm -f /z/Claude/Headless/HOLD
echo "=== done $(date +%T)"
