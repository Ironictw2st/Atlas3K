"""Open BOB's hidden "BOB - Preferences Editor".

The Preferences button on BOB's main window ("Select Data Files To Build") exists but is hidden (zero size) in the
retail kit, so it is pressed through UI Automation. Starts BOB from the kit's binaries folder when it is not running.

usage: bob_prefs.py [--ak <assembly kit root>]      (default: BOB_AK env var, else the vanilla assembly_kit)
"""
import argparse, os, subprocess, sys, time
from pywinauto import Application

DEFAULT_AK = r"C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\assembly_kit"
LOCK = r"Z:\Claude\Headless\bob_lock"
MAIN = "BOB - Select Data Files To Build"
PREFS = "BOB - Preferences Editor"


def bob_pid():
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq bob.retail.x64.exe", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True).stdout
    for line in out.splitlines():
        parts = line.strip('"').split('","')
        if len(parts) > 1 and parts[0].lower() == "bob.retail.x64.exe":
            return int(parts[1])
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ak", default=os.environ.get("BOB_AK") or DEFAULT_AK)
    args = ap.parse_args()

    if os.path.isdir(LOCK):
        print(f"note: the BOB lock ({LOCK}) is held; another session may be running BOB.")
    pid = bob_pid()
    if pid is None:
        binaries = os.path.join(args.ak, "binaries")
        subprocess.Popen([os.path.join(binaries, "bob.retail.x64.exe"), "/nosplashscreen"], cwd=binaries)
        for _ in range(60):
            time.sleep(1)
            pid = bob_pid()
            if pid: break
        if pid is None: sys.exit("BOB did not start")

    app = Application(backend="uia").connect(process=pid)
    for _ in range(60):  # wait for the main window to finish loading
        if app.window(title=PREFS).exists(): break
        main_win = app.window(title=MAIN)
        if main_win.exists():
            main_win.child_window(title="Preferences", control_type="Button").invoke()
            break
        time.sleep(1)
    else:
        sys.exit(f"'{MAIN}' window not found (is BOB showing another screen?)")

    prefs = app.window(title=PREFS)
    prefs.wait("exists visible", timeout=15)
    prefs.set_focus()
    print(f"opened '{PREFS}' (BOB pid {pid})")


if __name__ == "__main__":
    main()
