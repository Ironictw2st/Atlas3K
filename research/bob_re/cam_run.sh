#!/bin/bash
# cam_run.sh <label>: run BOB "Generate Camera Height Map" (vanilla kit, GUI mode) with frida_camera.js, retrying when the
# GUI tick doesn't register (the refused run leaves its BOB open: close it first). Prints the result lines.
L=$1
AK='C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\assembly_kit'
ACT='Terrain / Generate Camera Height Map  ( c:/program files (x86)/steam/steamapps/common/total war three kingdoms/assembly_kit/raw_data/terrain/campaigns/3k_dlc07_main_map/3k_dlc07_main_map.terry)'
closebob() { (cd /z/Claude/TerryClone/tools/bob_mcp && BOB_AK="$AK" python -c "
import sys; sys.path.insert(0,'.'); import server
f=getattr(server.bob_close,'fn',server.bob_close); print(f())" 2>/dev/null | tail -1); }
cd /z/Claude/TerryClone/research/bob_re
for try in 1 2 3 4; do
  closebob; sleep 2
  PYTHONIOENCODING=utf-8 python frida_camera.py "$AK" raw_data/terrain/campaigns/3k_dlc07_main_map "$ACT" "$L" ${PROBEFILE} --gui --patches > "frida_$L.log" 2>&1
  if grep -q '"ticked": \[\]' "frida_$L.log"; then echo "try $try: tick did not register, retrying"; continue; fi
  break
done
closebob
grep -E "'pass'|\"result\"|\"seconds\"|reason|never|frida:|aborted" "frida_$L.log" | cut -c1-700 | head -8
