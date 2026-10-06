"""Runs BOB's battle export (run_bob_battle_export.py, --keep-outputs) with a Frida script attached as soon as
bob.retail.x64.exe starts. Messages -> <out>/<label>.jsonl, binary payloads -> <out>/<label>_bin/.
Take the BOB lock first; restore the kit outputs with restore.py afterwards.
usage: frida_run_battle.py <script.js> <kit root> <guid> <label> [--out dir]"""
import json, os, subprocess, sys, time
import frida, psutil

HERE = os.path.dirname(os.path.abspath(__file__))
script, ak, gid, label = sys.argv[1:5]
out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else r"Z:/Claude/BattleMaps/research/bob_re/frida_battle"
os.makedirs(out, exist_ok=True)
log = open(os.path.join(out, f"{label}.jsonl"), "w", encoding="utf-8")
pre = {p.pid for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower().startswith("bob")}
proc = subprocess.Popen([sys.executable, os.path.join(HERE, "run_bob_battle_export.py"), ak, gid, label, "--keep-outputs"],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
pid, t0 = None, time.time()
while pid is None and time.time() - t0 < 120:
    for p in psutil.process_iter(["name"]):
        if (p.info["name"] or "").lower() == "bob.retail.x64.exe" and p.pid not in pre:
            pid = p.pid
            break
    else:
        time.sleep(0.01)
if pid is None:
    print("BOB never started", proc.communicate()[0][-2000:]); sys.exit(1)
sess = frida.attach(pid)
n = [0]


def on_msg(msg, data):
    if msg["type"] != "send":
        print("frida:", msg, flush=True); return
    p = msg["payload"]; n[0] += 1
    if data is not None:
        d = os.path.join(out, f"{label}_bin"); os.makedirs(d, exist_ok=True)
        fn = f"{n[0]:05d}_{p['kind']}.bin"; open(os.path.join(d, fn), "wb").write(data); p = {**p, "file": fn}
    log.write(json.dumps(p) + "\n"); log.flush()
    print({k: (v if not isinstance(v, list) or len(v) < 20 else f"[{len(v)}]") for k, v in p.items()}, flush=True)


scr = sess.create_script(open(script, encoding="utf-8").read())
scr.on("message", on_msg)
scr.load()
print(f"attached to {pid} after {time.time() - t0:.2f}s", flush=True)
print(proc.communicate()[0][-1500:])
