"""Run BOB's Terrain processor (Tilemap + Low frequency data) on one kit battle map under a Frida script, spawned so the
hooks are in before the work starts. Outputs stay in working_data (BOB is deterministic on these maps; the corpus has
the reference copies). Take the BOB lock (Z:/Claude/Headless/bob_lock) first.
usage: frida_battle_tilemap.py <kit root> <map id> <script.js> <out.jsonl> [timeout s]"""
import json, os, sys, time
import frida

AK, GID, SCRIPT, OUT = sys.argv[1:5]
TIMEOUT = int(sys.argv[5]) if len(sys.argv) > 5 else 900
BIN = os.path.join(AK, "binaries")
NAME = "_battle_a_tilemap"
esc = lambda s: s.replace("&", "&amp;").replace("<", "&lt;")
dirs = [f"<raw>/terrain/battles/{GID}", f"<working>/terrain/battles/{GID}", "<working>/"]
cfg = ["<bob_configuration>", "    <processors>", "        <processor>Terrain</processor>", "    </processors>",
       "    <directories>"] + [f"        <directory>{esc(d)}</directory>" for d in dirs] + [
    "    </directories>", "    <global_rules/>", "    <retail>1</retail>", "    <silent>1</silent>",
    "    <show_errors>0</show_errors>", "    <no_progress>1</no_progress>", "    <fail_on_assert>0</fail_on_assert>",
    "    <scan_perforce>0</scan_perforce>", "    <merge_for_checkin_mode>3</merge_for_checkin_mode>",
    "    <keep_output>1</keep_output>", "    <load_asset_graph>0</load_asset_graph>",
    "    <clean_asset_graph>0</clean_asset_graph>", "    <get_latest>0</get_latest>",
    "    <selected_providers/>", "    <selected_consumers>", f"        <entry>{esc(f'<raw>/terrain/battles/{GID}/...')}</entry>",
    "    </selected_consumers>", "    <selected_actions/>", "</bob_configuration>"]
with open(os.path.join(BIN, "BOB", f"{NAME}_configuration.xml"), "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(cfg) + "\n")

log = open(OUT, "w", encoding="utf-8")
counts = {}
done = {"exit": False}


def on_msg(msg, data):
    if msg["type"] == "send":
        p = msg["payload"]; counts[p["kind"]] = counts.get(p["kind"], 0) + 1
        if data is not None:                       # binary payloads -> <out>_bin/<n>_<kind>.bin
            d = OUT + "_bin"; os.makedirs(d, exist_ok=True)
            f = os.path.join(d, f"{sum(counts.values()):05d}_{p['kind']}.bin"); open(f, "wb").write(data); p = {**p, "file": f}
        log.write(json.dumps(p) + "\n")
    else:
        print("frida:", msg, flush=True)


pid = frida.spawn([os.path.join(BIN, "bob.retail.x64.exe"), f"/configuration:{NAME}", "/nosplashscreen", "/dont_stop_on_error"], cwd=BIN)
sess = frida.attach(pid)
sess.on("detached", lambda *a: done.__setitem__("exit", True))
scr = sess.create_script(open(SCRIPT, encoding="utf-8").read())
scr.on("message", on_msg)
scr.load()
frida.resume(pid)
t0 = time.time()
while not done["exit"] and time.time() - t0 < TIMEOUT:
    time.sleep(0.5)
if not done["exit"]:
    print("TIMEOUT; killing"); frida.kill(pid)
log.close()
os.remove(os.path.join(BIN, "BOB", f"{NAME}_configuration.xml"))
print(f"{time.time() - t0:.1f}s", counts)
