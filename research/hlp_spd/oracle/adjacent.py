"""Oracle: LOGICAL_POSITION_UTILITIES::adjacent_hexes (empireutility.modder.x64.dll) direction order."""
import ctypes, os
B = r"C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\assembly_kit\binaries"
os.add_dll_directory(B)
dll = ctypes.WinDLL(os.path.join(B, "empireutility.modder.x64.dll"))
f = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64)(dll._handle + 0x1325e0)
for x, y in [(10, 10), (11, 10)]:
    buf = ctypes.create_string_buffer(64)
    f(ctypes.addressof(buf), (y << 16) | x if False else (x | (y << 32)))
    raw = buf.raw
    print("int32 pairs", (x, y), [(int.from_bytes(raw[i:i+4], 'little', signed=True), int.from_bytes(raw[i+4:i+8], 'little', signed=True)) for i in range(0, 48, 8)])
    buf = ctypes.create_string_buffer(64)
    f(ctypes.addressof(buf), x | (y << 16))
    raw = buf.raw
    print("int16 pairs", (x, y), [(int.from_bytes(raw[i:i+2], 'little', signed=True), int.from_bytes(raw[i+2:i+4], 'little', signed=True)) for i in range(0, 24, 4)])
