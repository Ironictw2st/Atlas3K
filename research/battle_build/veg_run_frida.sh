#!/usr/bin/env bash
# Take the BOB lock, install a round-2 corpus project into the vanilla kit, run BOB's battle export with a Frida script
# (research/bob_re/<script>) attached, remove the project again and release the lock. Dumps go to
# Z:/Claude/BattleMaps/research/bob_re/frida_veg/<label>.jsonl (+ _bin/).
# usage: veg_run_frida.sh <spec name> <script.js> <label>
set -u
SPEC="$1"; JS="$2"; LABEL="$3"
AK="C:/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/assembly_kit"
BB="$(cygpath -m "$(cd "$(dirname "$0")" && pwd)")"
LOCK=/z/Claude/Headless/bob_lock
until mkdir "$LOCK" 2>/dev/null; do echo "waiting for BOB lock: $(cat $LOCK/* 2>/dev/null)"; sleep 20; done
echo "procedural-vegetation worker: frida $LABEL ($(date))" > "$LOCK/owner"
while [ -e /z/Claude/Headless/HOLD ]; do echo "HOLD present, waiting"; sleep 20; done
GID=$(python -c "import sys; sys.path.insert(0, r'$BB'); import make_round2_project as m; print(m.SPECS['$SPEC']['gid'])")
python "$BB/make_round2_project.py" "$SPEC" "$AK" install
python "$BB/frida_run_battle.py" "$BB/../bob_re/$JS" "$AK" "$GID" "$LABEL" --out "Z:/Claude/BattleMaps/research/bob_re/frida_veg"
python "$BB/make_round2_project.py" "$SPEC" "$AK" remove
rm -rf "$LOCK"
echo "released BOB lock"
