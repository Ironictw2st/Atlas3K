#!/bin/bash
# New-areas polish build (2026-10-04; docs/proposals/new_areas_lookover.md, user: "do all the proposal items in one rebuild").
# one-off raster polish (terrain_polish.py H1/M4/M5, blend_polish.py H2/H3; each refuses to run twice) -> trees raster
# (tree_clear.py -> trees_x15 incl. the H4/M1 step) -> ak_main (north_dress / village_dress M2/M3/M5/M6) -> kit layers +
# height + blend -> kit_edits.py replay (lakes, Korea inlet, Tamna, mountains, town trees, Yingtao, audit batches) ->
# kit_edits_build.sh (native build from the kit into the _native test pack, lake models).
# Same install as relief_build.sh, plus the blend copy; relief_build.sh packs into the non-native main190 pack.
set -e
export PYTHONIOENCODING=utf-8 PATH="$PATH:/c/Windows/System32:/c/Windows/System32/WindowsPowerShell/v1.0"
cd /z/Claude/TerryClone/research/main190
K="/c/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/assembly_kit_190E"
NEW=3k_190e_expanded_map; OLD=3k_dlc07_main_map; RT="$K/raw_data/terrain/campaigns/$NEW"
if powershell.exe -NoProfile -Command "if (Get-Process Three_Kingdoms -ErrorAction SilentlyContinue) { exit 1 }"; then :; else echo "GAME RUNNING - abort"; exit 1; fi
[ -f /z/Claude/Headless/HOLD ] && { echo "HOLD present (another build?) - abort"; exit 1; }

echo "=== raster polish $(date +%T)"
python terrain_polish.py 2>&1 | tail -6
python blend_polish.py 2>&1 | tail -6

echo "=== trees raster / ak_main $(date +%T)"
python tree_clear.py 2>&1 | grep -vi warn | tail -6
python ak_main.py > /tmp/ak_main.log 2>&1 || { tail -20 /tmp/ak_main.log; exit 1; }
grep -E "north_dress|village_dress|kept" /tmp/ak_main.log | cut -c1-300
[ -f ak/$OLD/$OLD.terry ] || { echo "no .terry written"; exit 1; }

echo "=== install into the kit $(date +%T)"
B=/z/Claude/TerryClone/output/backups/main190_polish_raw_terrain_$(date +%Y%m%d_%H%M%S); cp -r "$RT" "$B"; echo "  kit raw terrain backup: $B"
for f in ak/$OLD/*.layer; do b=$(basename "$f"); cp "$f" "$RT/${b/$OLD/$NEW}"; done
sed "s#terrain/campaigns/$OLD/#terrain/campaigns/$NEW/#g" ak/$OLD/$OLD.terry > "$RT/$NEW.terry"
cp terrain/$OLD.height.191fd803c1a801d.tif "$RT/$NEW.height.191fd803c1a801d.tif"
cp terrain/$OLD.blend.191fd8068da8020.tif "$RT/$NEW.blend.191fd8068da8020.tif"
echo "  layers + height + blend -> kit"
touch "$K/raw_data/terrain/campaigns/$NEW/.kit_edits_pending"   # fresh install: replay allowed
python kit_edits.py || exit 1

echo "=== native build + pack $(date +%T)"
bash kit_edits_build.sh
echo "=== polish build done $(date +%T)"
