#!/usr/bin/env python3
"""Run BOB "Tilemap" (run_bob.py, headless) and attach frida_tilemap.js as soon as bob.retail.x64.exe appears.
Messages -> research/bob_re/frida_out/<label>.jsonl. usage: frida_tilemap.py <ak root> <kit path> [label]"""
import json, subprocess, sys, time
from pathlib import Path
import frida, psutil
HERE = Path(__file__).parent
AK, KPATH = sys.argv[1], sys.argv[2]
LABEL = sys.argv[3] if len(sys.argv) > 3 else time.strftime("tilemap_%Y%m%d_%H%M%S")
OUT = HERE / "frida_out"; OUT.mkdir(exist_ok=True)
log = open(OUT / f"{LABEL}.jsonl", "w", encoding="utf-8")
pre = {p.pid for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower().startswith("bob")}
proc = subprocess.Popen([sys.executable, str(Path(r"Z:/Claude/TerryClone/tools/bob_mcp/run_bob.py")), "--ak", AK, KPATH, "Tilemap",
                         "--timeout", "3500", "--label", LABEL], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
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
        log.write(json.dumps(p) + "\n"); log.flush()
        if p["kind"] in ("hooked", "loaded", "pass_start", "modules"): print(time.strftime("%T"), p, flush=True)
        elif "tiles" in p: print(time.strftime("%T"), p["kind"], p.get("pass"), len(p["tiles"]), flush=True)
    else: print("frida:", msg, flush=True)
scr = sess.create_script(open(HERE / "frida_tilemap.js", encoding="utf-8").read())
scr.on("message", on_msg); scr.load()
print(f"attached to {pid} after {time.time() - t0:.2f}s", flush=True)
import threading
def watch():                                                # log every new process while BOB runs
    fam, told = {pid}, set()
    while proc.poll() is None:
        for q in psutil.process_iter(["name", "ppid"]):
            if q.info["ppid"] in fam and q.pid not in fam:
                fam.add(q.pid); print(time.strftime("%T"), "BOB child process", q.pid, q.info["name"], flush=True)
        time.sleep(0.2)
threading.Thread(target=watch, daemon=True).start()
out = proc.communicate()[0]
print(out[-1500:]); print("counts", counts)
