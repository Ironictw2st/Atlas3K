"""Run BOB's full battle-map export the way Terry's "Process with BOB" does, minus the Pack processor (nothing is
written to the game's data folder).

usage: run_bob_battle_export.py <kit root> <guid> <label> [--keep-outputs] [--timeout s]

Config = Terry's _terry_auto_configuration.xml for a battle map (processors TerryTile, Cs2, Vegetation, Terrain;
consumers = the tile .terry + <raw>/terrain/battles/<id>/...), written as binaries/BOB/_battle_parity_configuration.xml.
By default the project's working_data outputs are deleted first so every file is regenerated; snapshot them with
snapshot.py <kit> <id> existing beforehand and restore with restore.py afterwards. bob*.log are copied to
<corpus>/<id>/logs/<label>/. Take the BOB lock (Z:/Claude/Headless/bob_lock) before running.
"""
import argparse, glob, os, shutil, subprocess, sys, time

ap = argparse.ArgumentParser()
ap.add_argument("ak"); ap.add_argument("gid"); ap.add_argument("label")
ap.add_argument("--keep-outputs", action="store_true"); ap.add_argument("--timeout", type=int, default=3600)
ap.add_argument("--corpus", default=r"Z:/Claude/BattleMaps/out/battle_parity")
a = ap.parse_args()
AK, GID = a.ak, a.gid
BIN = os.path.join(AK, "binaries")
NAME = "_battle_parity"
tile_raw = os.path.join(AK, "raw_data/terrain/tiles/battle/_assembly_kit", GID)
terry = sorted(glob.glob(os.path.join(tile_raw, "*.terry")))
if len(terry) != 1:
    sys.exit(f"expected one .terry in {tile_raw}, found {terry}")
terry_name = os.path.basename(terry[0])
esc = lambda s: s.replace("&", "&amp;").replace("<", "&lt;")
dirs = [f"<raw>/terrain/tiles/battle/_assembly_kit/{GID}", f"<working>/terrain/tiles/battle/_assembly_kit/{GID}",
        "<raw>/art/prefabs/battle/", f"<raw>/terrain/battles/{GID}", f"<working>/terrain/battles/{GID}", "<working>/"]
consumers = [f"<raw>/terrain/tiles/battle/_assembly_kit/{GID}/{terry_name}", f"<raw>/terrain/battles/{GID}/..."]
cfg = ["<bob_configuration>", "    <processors>"] + [f"        <processor>{p}</processor>" for p in
                                                       ("TerryTile", "Cs2", "Vegetation", "Terrain")] + [
    "    </processors>", "    <directories>"] + [f"        <directory>{esc(d)}</directory>" for d in dirs] + [
    "    </directories>", "    <global_rules/>", "    <retail>1</retail>", "    <silent>1</silent>",
    "    <show_errors>0</show_errors>", "    <no_progress>1</no_progress>", "    <fail_on_assert>0</fail_on_assert>",
    "    <scan_perforce>0</scan_perforce>", "    <merge_for_checkin_mode>3</merge_for_checkin_mode>",
    "    <keep_output>1</keep_output>", "    <load_asset_graph>0</load_asset_graph>",
    "    <clean_asset_graph>0</clean_asset_graph>", "    <get_latest>0</get_latest>",
    "    <selected_providers/>", "    <selected_consumers>"] + [f"        <entry>{esc(c)}</entry>" for c in consumers] + [
    "    </selected_consumers>", "    <selected_actions/>", "</bob_configuration>"]
with open(os.path.join(BIN, "BOB", f"{NAME}_configuration.xml"), "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(cfg) + "\n")

# Terry (not BOB) writes the tile database entry (_tile_database/TILES/_assembly_kit_<id>.bin/.xml) and the
# working_data rules.bob files when the project is saved: they are inputs here and are kept.
if not a.keep_outputs:
    for rel in (f"working_data/terrain/battles/{GID}", f"working_data/terrain/tiles/battle/_assembly_kit/{GID}"):
        for root, _, files in os.walk(os.path.join(AK, rel)):
            for f in files:
                if f != "rules.bob":
                    os.remove(os.path.join(root, f))

log = os.path.join(BIN, "bob.log")
before = os.path.getmtime(log) if os.path.exists(log) else 0
t0 = time.time()
p = subprocess.Popen([os.path.join(BIN, "bob.retail.x64.exe"), f"/configuration:{NAME}", "/nosplashscreen",
                      "/dont_stop_on_error"], cwd=BIN)
while p.poll() is None and time.time() - t0 < a.timeout:
    time.sleep(1)
state = "exited" if p.poll() is not None else "TIMEOUT"
if state == "TIMEOUT":
    subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
out = os.path.join(a.corpus, GID, "logs", a.label)
os.makedirs(out, exist_ok=True)
for n in ("bob.log", "bob_error.log", "bob_warnings.log"):
    src = os.path.join(BIN, n)
    if os.path.exists(src) and os.path.getmtime(src) >= before:
        shutil.copy2(src, out)
print(f"{state} code={p.poll()} after {round(time.time() - t0, 1)} s; logs -> {out}")
