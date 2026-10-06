"""Read constants from a kit DLL by virtual address. usage: veg_dllconst.py <dll name> <va> [f|i|d|q] [count]"""
import struct, sys
import pefile

KIT = r"C:/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/assembly_kit/binaries/"
_pe = {}


def read(dll, va, n):
    pe = _pe.get(dll) or _pe.setdefault(dll, pefile.PE(KIT + dll, fast_load=True))
    rva = va - pe.OPTIONAL_HEADER.ImageBase
    return pe.get_data(rva, n)


def f(dll, va):
    return struct.unpack("<f", read(dll, va, 4))[0]


if __name__ == "__main__":
    dll, va = sys.argv[1], int(sys.argv[2], 16)
    kind = sys.argv[3] if len(sys.argv) > 3 else "f"
    cnt = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    sz = {"f": 4, "i": 4, "d": 8, "q": 8}[kind]
    vals = struct.unpack("<" + kind * cnt, read(dll, va, sz * cnt))
    print(*[repr(v) for v in vals])
