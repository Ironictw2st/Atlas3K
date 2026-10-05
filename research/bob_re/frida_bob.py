#!/usr/bin/env python3
"""Run one BOB action headless (tools/bob_mcp/run_bob.py) and attach a Frida script as soon as bob.retail.x64.exe
appears. Messages -> research/bob_re/frida_out/<label>.jsonl.
usage: frida_bob.py <script.js> <ak root> <kit path> <action> <label> [--gui | extra run_bob args, e.g. --no-filter]"""
import json, subprocess, sys, time
from pathlib import Path
import frida, psutil
HERE = Path(__file__).parent
SCRIPT, AK, KPATH, ACTION, LABEL = sys.argv[1:6]
OUT = HERE / "frida_out"; OUT.mkdir(exist_ok=True)
log = open(OUT / f"{LABEL}.jsonl", "w", encoding="utf-8")
pre = {p.pid for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower().startswith("bob")}
import os  # FRIDA_ALLOW_HELPERS='a;b': gui-mode helper actions BOB may add (bob_run_action allow_helpers)
if "--gui" in sys.argv[6:]:                      # GUI mode (Terry file is only found there), like the build scripts
    code = ("import sys, json; sys.path.insert(0, '.'); import server; f = getattr(server.bob_run_action, 'fn', server.bob_run_action); "
            f"print(json.dumps(f({KPATH!r}, {ACTION!r}, timeout=3400, mode='gui', capture_label={LABEL!r}, allow_helpers={[h for h in os.environ.get('FRIDA_ALLOW_HELPERS','').split(';') if h]!r}), indent=1, default=str))")
    proc = subprocess.Popen([sys.executable, "-c", code], cwd=r"Z:/Claude/TerryClone/tools/bob_mcp", env={**os.environ, "BOB_AK": AK},
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
else:
    proc = subprocess.Popen([sys.executable, r"Z:/Claude/TerryClone/tools/bob_mcp/run_bob.py", "--ak", AK, KPATH, ACTION,
                             "--timeout", "3500", "--label", LABEL] + sys.argv[6:], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
pid, t0 = None, time.time()
while pid is None and time.time() - t0 < 120:
    for p in psutil.process_iter(["name"]):
        if (p.info["name"] or "").lower() == "bob.retail.x64.exe" and p.pid not in pre: pid = p.pid; break
    else: time.sleep(0.02)
if pid is None: print("BOB never started"); print(proc.communicate()[0][-2000:]); sys.exit(1)
sess = frida.attach(pid)
counts = {}
def on_msg(msg, data):
    if msg["type"] == "send":
        p = msg["payload"]; counts[p["kind"]] = counts.get(p["kind"], 0) + 1
        if data is not None:                      # binary payloads -> frida_out/<label>_bin/<seq>.bin
            d = OUT / f"{LABEL}_bin"; d.mkdir(exist_ok=True)
            f = d / f"{sum(counts.values()):06d}_{p['kind']}.bin"; f.write_bytes(data); p = {**p, "file": f.name}
        log.write(json.dumps(p) + "\n"); log.flush()
        if p["kind"] not in ("hs",): print(time.strftime("%T"), {k: (v if not isinstance(v, list) else len(v)) for k, v in p.items()}, flush=True)
    else: print("frida:", msg, flush=True)
scr = sess.create_script(open(HERE / SCRIPT, encoding="utf-8").read())
scr.on("message", on_msg); scr.load()
print(f"attached to {pid} after {time.time() - t0:.2f}s", flush=True)
out = proc.communicate()[0]
try: scr.post({"type": "flush"})
except Exception: pass
print(out[-1500:]); print("counts", counts)
