"""Partial DLL oracle: drive empirecampaign.modder.x64.dll's CAI_SPARSE_MAP<1024,32,CAI_SIMPLE_PATH_DIRECTORY::ARRAY_WRAPPER>
(FUN_1805cd6f0 ctor, FUN_180600000 value_ref) in-process to see where coordinates >= 1024 land."""
import ctypes, os, sys
B = r"C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\assembly_kit\binaries"
os.add_dll_directory(B)
dll = ctypes.WinDLL(os.path.join(B, "empirecampaign.modder.x64.dll"))
base = dll._handle
def fn(va, res, *args):
    return ctypes.CFUNCTYPE(res, *args)(base + va - 0x180000000)
ctor = fn(0x1805cd6f0, ctypes.c_void_p, ctypes.c_void_p)
value_ref = fn(0x180600000, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32)
buf = ctypes.create_string_buffer(0x1000)
m = ctor(ctypes.addressof(buf))
coords = [int(a) for a in sys.argv[1:]] if len(sys.argv) > 1 else []
ptr = {}
for x, y in [(5, 5), (991, 7), (992, 7), (1000, 7), (1023, 7), (7, 1023)]:
    ptr[(x, y)] = value_ref(m, x, y)
print({k: hex(v) for k, v in ptr.items()}, flush=True)
for x, y in [(1024, 7), (1030, 7), (1055, 7), (1056, 7), (1477, 7), (7, 1100), (1200, 1100)]:
    v = value_ref(m, x, y)
    hits = [k for k, pv in ptr.items() if pv == v]
    # find alias by scanning candidates
    cand = None
    for cx in list(range(960, 1024)) + [x]:
        for cy in ([y] if y < 1024 else list(range(960, 1024))):
            if cx < 1024 and cy < 1024 and value_ref(m, cx, cy) == v: cand = (cx, cy); break
        if cand: break
    print((x, y), hex(v), "aliases", cand, flush=True)
