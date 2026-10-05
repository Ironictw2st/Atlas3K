#!/usr/bin/env python3
"""Class names from MSVC x64 RTTI, read from Three_Kingdoms.exe on disk.

rtti_name.py BASE ADDR [ADDR ...]
  BASE: runtime module base from the crash dump (lm m Three_Kingdoms)
  ADDR: runtime vtable address -> prints the class name ([vtable-8] = CompleteObjectLocator, +0xC = TypeDescriptor
        RVA, TypeDescriptor+0x10 = decorated name)
"""
import struct, sys

EXE = r"C:/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/Three_Kingdoms.exe"
d = open(EXE, "rb").read()
pe = struct.unpack_from("<I", d, 0x3C)[0]
nsec = struct.unpack_from("<H", d, pe + 6)[0]
opt = struct.unpack_from("<H", d, pe + 20)[0]
image_base = struct.unpack_from("<Q", d, pe + 24 + 24)[0]
secs = []
for i in range(nsec):
    o = pe + 24 + opt + 40 * i
    vs, va, rs, rp = struct.unpack_from("<IIII", d, o + 8)
    secs.append((va, max(vs, rs), rp))


def off(rva):
    for va, size, rp in secs:
        if va <= rva < va + size: return rp + rva - va
    raise ValueError(hex(rva))


def name(base, vt):
    col_va = struct.unpack_from("<Q", d, off(vt - base - 8))[0]
    col_rva = col_va - image_base
    td_rva = struct.unpack_from("<I", d, off(col_rva) + 12)[0]
    o = off(td_rva) + 16
    return d[o:d.index(b"\0", o)].decode()


if __name__ == "__main__":
    base = int(sys.argv[1], 16)
    for a in sys.argv[2:]:
        try: print(a, name(base, int(a.replace("`", ""), 16)))
        except Exception as e: print(a, "?", e)
