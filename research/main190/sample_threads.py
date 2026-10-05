#!/usr/bin/env python3
"""Sample where a running process is spending time, without a debugger attach (works while cdb is attached).

python sample_threads.py <pid> [samples] [interval_s]
Finds the thread with the most CPU time, then repeatedly: SuspendThread -> GetThreadContext (RIP, RSP) ->
read 16 KB of its stack -> ResumeThread. Reports RIP as module+offset, a RIP histogram, and the return
addresses on the stack that point into loaded modules (a heuristic call stack).
"""
import ctypes, ctypes.wintypes as wt, sys, time, collections, struct

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)
TH32CS_SNAPTHREAD = 0x4
THREAD_ALL = 0x1F03FF
PROCESS_VM_READ, PROCESS_QUERY = 0x10, 0x400


class THREADENTRY32(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ThreadID", wt.DWORD), ("th32OwnerProcessID", wt.DWORD),
                ("tpBasePri", wt.LONG), ("tpDeltaPri", wt.LONG), ("dwFlags", wt.DWORD)]


class M128A(ctypes.Structure):
    _fields_ = [("Low", ctypes.c_uint64), ("High", ctypes.c_int64)]


class CONTEXT(ctypes.Structure):
    _pack_ = 16
    _fields_ = [("P1Home", ctypes.c_uint64), ("P2Home", ctypes.c_uint64), ("P3Home", ctypes.c_uint64), ("P4Home", ctypes.c_uint64),
                ("P5Home", ctypes.c_uint64), ("P6Home", ctypes.c_uint64), ("ContextFlags", wt.DWORD), ("MxCsr", wt.DWORD),
                ("SegCs", wt.WORD), ("SegDs", wt.WORD), ("SegEs", wt.WORD), ("SegFs", wt.WORD), ("SegGs", wt.WORD), ("SegSs", wt.WORD),
                ("EFlags", wt.DWORD), ("Dr0", ctypes.c_uint64), ("Dr1", ctypes.c_uint64), ("Dr2", ctypes.c_uint64), ("Dr3", ctypes.c_uint64),
                ("Dr6", ctypes.c_uint64), ("Dr7", ctypes.c_uint64), ("Rax", ctypes.c_uint64), ("Rcx", ctypes.c_uint64), ("Rdx", ctypes.c_uint64),
                ("Rbx", ctypes.c_uint64), ("Rsp", ctypes.c_uint64), ("Rbp", ctypes.c_uint64), ("Rsi", ctypes.c_uint64), ("Rdi", ctypes.c_uint64),
                ("R8", ctypes.c_uint64), ("R9", ctypes.c_uint64), ("R10", ctypes.c_uint64), ("R11", ctypes.c_uint64), ("R12", ctypes.c_uint64),
                ("R13", ctypes.c_uint64), ("R14", ctypes.c_uint64), ("R15", ctypes.c_uint64), ("Rip", ctypes.c_uint64),
                ("FltSave", ctypes.c_byte * 512), ("VectorRegister", M128A * 26), ("VectorControl", ctypes.c_uint64),
                ("DebugControl", ctypes.c_uint64), ("LastBranchToRip", ctypes.c_uint64), ("LastBranchFromRip", ctypes.c_uint64),
                ("LastExceptionToRip", ctypes.c_uint64), ("LastExceptionFromRip", ctypes.c_uint64)]


def modules(hp):
    arr = (ctypes.c_void_p * 1024)(); need = wt.DWORD()
    psapi.EnumProcessModulesEx(hp, arr, ctypes.sizeof(arr), ctypes.byref(need), 3)
    out = []
    for i in range(need.value // 8):
        name = ctypes.create_unicode_buffer(260); psapi.GetModuleBaseNameW(hp, ctypes.c_void_p(arr[i]), name, 260)
        class MI(ctypes.Structure): _fields_ = [("base", ctypes.c_void_p), ("size", wt.DWORD), ("entry", ctypes.c_void_p)]
        mi = MI(); psapi.GetModuleInformation(hp, ctypes.c_void_p(arr[i]), ctypes.byref(mi), ctypes.sizeof(mi))
        out.append((mi.base or 0, mi.size, name.value))
    return out


def where(addr, mods):
    for b, s, n in mods:
        if b <= addr < b + s: return f"{n}+0x{addr - b:x}"
    return None


def main():
    pid = int(sys.argv[1]); n = int(sys.argv[2]) if len(sys.argv) > 2 else 40; iv = float(sys.argv[3]) if len(sys.argv) > 3 else 0.25
    hp = k32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY, False, pid); mods = modules(hp)
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0); te = THREADENTRY32(); te.dwSize = ctypes.sizeof(te)
    tids = []; ok = k32.Thread32First(snap, ctypes.byref(te))
    while ok:
        if te.th32OwnerProcessID == pid: tids.append(te.th32ThreadID)
        ok = k32.Thread32Next(snap, ctypes.byref(te))
    def cpu(h):
        c, e, kt, ut = (wt.FILETIME() for _ in range(4)); k32.GetThreadTimes(h, ctypes.byref(c), ctypes.byref(e), ctypes.byref(kt), ctypes.byref(ut))
        return ((kt.dwHighDateTime << 32 | kt.dwLowDateTime) + (ut.dwHighDateTime << 32 | ut.dwLowDateTime)) / 1e7
    hs = {t: k32.OpenThread(THREAD_ALL, False, t) for t in tids}
    c0 = {t: cpu(h) for t, h in hs.items()}; time.sleep(2); c1 = {t: cpu(h) for t, h in hs.items()}
    hot = sorted(tids, key=lambda t: c1[t] - c0[t], reverse=True)
    print("busiest threads (cpu s in 2 s):", [(t, round(c1[t] - c0[t], 2), round(c1[t], 0)) for t in hot[:4]])
    th = hs[hot[0]]; rips = collections.Counter(); stacks = collections.Counter(); regs = []
    for i in range(n):
        k32.SuspendThread(th)
        ctx = CONTEXT(); ctx.ContextFlags = 0x10000B                       # CONTEXT_FULL (AMD64)
        k32.GetThreadContext(th, ctypes.byref(ctx))
        buf = ctypes.create_string_buffer(16384); got = ctypes.c_size_t()
        k32.ReadProcessMemory(hp, ctypes.c_void_p(ctx.Rsp), buf, 16384, ctypes.byref(got))
        k32.ResumeThread(th)
        rips[where(ctx.Rip, mods) or hex(ctx.Rip)] += 1
        rets = []
        for (q,) in struct.iter_unpack("<Q", buf.raw[:got.value - got.value % 8]):
            w = where(q, mods)
            if w and ("Three_Kingdoms" in w or ".dll" in w.lower()): rets.append(w)
            if len(rets) >= 10: break
        stacks[" <- ".join(rets[:8])] += 1
        if i < 3: regs.append({r: hex(getattr(ctx, r)) for r in ("Rip", "Rsp", "Rax", "Rcx", "Rdx", "R8", "R9")})
        time.sleep(iv)
    print(f"\nRIP histogram over {n} samples:"); [print(f"  {c:3d}  {r}") for r, c in rips.most_common(15)]
    print("\nheuristic stacks (return addresses found on the stack):"); [print(f"  {c:3d}  {s}") for s, c in stacks.most_common(5)]
    print("\nfirst samples' registers:", *regs, sep="\n  ")


if __name__ == "__main__":
    main()
