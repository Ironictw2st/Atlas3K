"""DLL oracle for the landmark search's visited set CAI_SPARSE_MAP<1024,64,bool,0>
(ctor FUN_18042f0b0, set_value FUN_1805fe620, get_value FUN_1805e9ec0): which in-range cell does an out-of-range
coordinate share its flag with?"""
import ctypes, os, sys
B = r"C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\assembly_kit\binaries"
os.add_dll_directory(B)
dll = ctypes.WinDLL(os.path.join(B, "empirecampaign.modder.x64.dll"))
base = dll._handle
def fn(va, res, *args): return ctypes.CFUNCTYPE(res, *args)(base + va - 0x180000000)
ctor = fn(0x18042f0b0, ctypes.c_void_p, ctypes.c_void_p)
setv = fn(0x1805fe620, None, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint8)
getv = fn(0x1805e9ec0, ctypes.c_uint8, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32)
def fresh():
    buf = ctypes.create_string_buffer(0x2000); ctor(ctypes.addressof(buf)); return buf
for x, y in [(1024, 7), (1030, 7), (1087, 7), (1088, 7), (1147, 255), (1477, 600), (7, 1034), (872, 1034), (1439, 1095)]:
    buf = fresh(); m = ctypes.addressof(buf)
    setv(m, x, y, 1)
    hits = [(cx, cy) for cx in range(0, 1024) for cy in ([y] if y < 1024 else range(900, 1024)) if getv(m, cx, cy)]
    print((x, y), "->", hits[:5], "self", getv(m, x, y), flush=True)
