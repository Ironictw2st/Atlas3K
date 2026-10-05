#!/usr/bin/env python3
"""Watch an RPFM startpos build: every INTERVAL s log the game processes, CPU, memory, new crash dumps, new
output files, and where the busiest thread is (flags the allocator spin-lock that deadlocked the 15:25 run).
Exits when no Three_Kingdoms.exe has run for 90 s after one was seen, or after MAX_MIN minutes.
Log: output/watch_build.log (also printed)."""
import os, sys, time, glob, subprocess, ctypes, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sample_threads as S

INTERVAL, MAX_MIN = 60, 180
SPIN = (0x6b6df3, 0x6b6e34)                              # Three_Kingdoms.exe allocator spin-wait (see docs)
CRASH = os.path.expandvars(r"%APPDATA%\The Creative Assembly\ThreeKingdoms\crash_report")
DATA = r"C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\data"
LOG = r"Z:\Claude\TerryClone\output\watch_build.log"


def games():
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Three_Kingdoms.exe", "/FO", "CSV", "/NH"], capture_output=True, text=True).stdout
    return [int(l.split('","')[1]) for l in out.strip().splitlines() if l.startswith('"Three_Kingdoms')]


def hot_rip(pid, n=8):
    k32 = S.k32; hp = k32.OpenProcess(0x10 | 0x400, False, pid); mods = S.modules(hp)
    snap = k32.CreateToolhelp32Snapshot(4, 0); te = S.THREADENTRY32(); te.dwSize = ctypes.sizeof(te); tids = []
    ok = k32.Thread32First(snap, ctypes.byref(te))
    while ok:
        if te.th32OwnerProcessID == pid: tids.append(te.th32ThreadID)
        ok = k32.Thread32Next(snap, ctypes.byref(te))
    def cpu(h):
        import ctypes.wintypes as wt
        c, e, kt, ut = (wt.FILETIME() for _ in range(4)); k32.GetThreadTimes(h, ctypes.byref(c), ctypes.byref(e), ctypes.byref(kt), ctypes.byref(ut))
        return ((kt.dwHighDateTime << 32 | kt.dwLowDateTime) + (ut.dwHighDateTime << 32 | ut.dwLowDateTime)) / 1e7
    hs = {t: k32.OpenThread(0x1F03FF, False, t) for t in tids}
    c0 = {t: cpu(h) for t, h in hs.items()}; time.sleep(1); c1 = {t: cpu(h) for t, h in hs.items()}
    hot = max(tids, key=lambda t: c1[t] - c0[t]); busy = c1[hot] - c0[hot]; th = hs[hot]; rips = collections.Counter()
    for _ in range(n):
        k32.SuspendThread(th); ctx = S.CONTEXT(); ctx.ContextFlags = 0x10000B; k32.GetThreadContext(th, ctypes.byref(ctx)); k32.ResumeThread(th)
        w = S.where(ctx.Rip, mods) or hex(ctx.Rip); rips[w] += 1; time.sleep(0.1)
    spin = sum(c for w, c in rips.items() if w.startswith("Three_Kingdoms.exe+") and SPIN[0] <= int(w.split("+")[1], 16) < SPIN[1])
    return busy, rips.most_common(3), spin


def main():
    t0 = time.time(); seen = False; last_seen = time.time()
    crash0 = set(os.listdir(CRASH)); spins = 0
    def log(s):
        line = time.strftime("%H:%M:%S ") + s; print(line, flush=True); open(LOG, "a", encoding="utf-8").write(line + "\n")
    log("watch start")
    while time.time() - t0 < MAX_MIN * 60:
        g = games()
        new_crash = sorted(set(os.listdir(CRASH)) - crash0)
        fresh = [f for f in glob.glob(DATA + r"\**\*", recursive=True) if os.path.isfile(f) and os.path.getmtime(f) > t0 and not f.endswith(".pack")]
        if g:
            seen = True; last_seen = time.time()
            for pid in g:
                try:
                    busy, top, spin = hot_rip(pid)
                    spins = spins + 1 if spin >= 6 else 0
                    log(f"pid {pid}: hot thread {busy:.2f} cores; rip {top}; spin-lock {spin}/8"
                        + (f"  <-- SPINNING ({spins} checks in a row)" if spin >= 6 else ""))
                except Exception as e:
                    log(f"pid {pid}: sample failed {e}")
        else:
            log("no game process")
        if new_crash: log(f"NEW CRASH FILES: {new_crash}")
        if fresh: log("new files in data: " + ", ".join(f"{os.path.relpath(f, DATA)} ({os.path.getsize(f):,})" for f in fresh[:12]))
        if seen and not g and time.time() - last_seen > 90: log("game gone for 90 s - done"); break
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
