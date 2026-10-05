#!/usr/bin/env python3
"""Run BOB "Generate Camera Height Map" headless with frida_camera.js attached; save BOB's float pixel buffer.
Out: research/bob_re/frida_out/<label>.f32 (W*H float32, row j = z index j) + <label>.json (W, H, steps, settings,
height provider). Optional probe points file (json [[x, z], ...]) evaluated through BOB's height provider while BOB
is paused after the pass -> <label>_probe.json.
usage: frida_camera.py <ak root> <kit path> <action> <label> [probe.json] [extra run_bob args]"""
import json, subprocess, sys, time, threading
from pathlib import Path
import frida, psutil
HERE = Path(__file__).parent
AK, KPATH, ACTION, LABEL = sys.argv[1:5]
PROBE = sys.argv[5] if len(sys.argv) > 5 and sys.argv[5].endswith(".json") else None
EXTRA = sys.argv[6:] if PROBE else sys.argv[5:]
OUT = HERE / "frida_out"; OUT.mkdir(exist_ok=True)
pre = {p.pid for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower().startswith("bob")}
import os
if "--gui" in EXTRA:
    code = ("import sys, json; sys.path.insert(0, '.'); import server; f = getattr(server.bob_run_action, 'fn', server.bob_run_action); "
            f"print(json.dumps(f({KPATH!r}, {ACTION!r}, timeout=3400, mode='gui', capture_label={LABEL!r}, allow_helpers=['Initialise warscape', 'Shutdown warscape', 'Finalise', 'Clean up warscape']), indent=1, default=str))")
    proc = subprocess.Popen([sys.executable, "-c", code], cwd=r"Z:/Claude/TerryClone/tools/bob_mcp", env={**os.environ, "BOB_AK": AK},
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
else:
    proc = subprocess.Popen([sys.executable, r"Z:/Claude/TerryClone/tools/bob_mcp/run_bob.py", "--ak", AK, KPATH, ACTION,
                             "--timeout", "3500", "--label", LABEL] + EXTRA, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
pid, t0 = None, time.time()
while pid is None and time.time() - t0 < 120:
    for p in psutil.process_iter(["name"]):
        if (p.info["name"] or "").lower() == "bob.retail.x64.exe" and p.pid not in pre: pid = p.pid; break
    else: time.sleep(0.02)
if pid is None: print("BOB never started"); print(proc.communicate()[0][-2000:]); sys.exit(1)
sess = frida.attach(pid)
got = threading.Event()
def on_msg(msg, data):
    if msg["type"] != "send": print("frida:", msg, flush=True); return
    p = msg["payload"]
    if p["kind"] not in ("patches", "blocks", "probe", "qtree", "qnodes", "tileinst"): print(time.strftime("%T"), {k: v for k, v in p.items()}, flush=True)
    if p["kind"] in ("blocks", "probe", "qtree", "qnodes", "tileinst"):
        (OUT / f"{LABEL}_{p['kind']}.json").write_text(json.dumps(p)); print(p["kind"], len(p.get("blocks", p.get("heights", p.get("lists", p.get("nodes", p.get("inst", [])))))), flush=True); return
    if p["kind"] == "patches":
        (OUT / f"{LABEL}_patches.json").write_text(json.dumps(p)); print("patch objects", p["n"], flush=True); return
    if p["kind"] == "pass":
        (OUT / f"{LABEL}.f32").write_bytes(data)
        (OUT / f"{LABEL}.json").write_text(json.dumps(p, indent=1))
        got.set()
scr = sess.create_script(open(HERE / "frida_camera.js", encoding="utf-8").read())
scr.on("message", on_msg); scr.load()
if "--patches" in EXTRA:                                   # second script: BOB's height-patch objects
    scr2 = sess.create_script(open(HERE / "frida_campatch.js", encoding="utf-8").read()); scr2.on("message", on_msg); scr2.load()
EXTRA = [e for e in EXTRA if e != "--patches"]
print(f"attached to {pid} after {time.time() - t0:.2f}s", flush=True)
if PROBE: scr.post({"type": "points", "points": json.load(open(PROBE))})
out = proc.communicate()[0]
print(out[:1500]); print("..."); print(out[-600:])
