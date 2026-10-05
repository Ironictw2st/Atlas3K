"""Read float/u32 constants at virtual addresses of a PE image. usage: pe_consts.py <dll> <va hex>..."""
import struct, sys
d = open(sys.argv[1], "rb").read()
pe = struct.unpack_from("<I", d, 0x3c)[0]; ns = struct.unpack_from("<H", d, pe + 6)[0]; opt = struct.unpack_from("<H", d, pe + 20)[0]
base = struct.unpack_from("<Q", d, pe + 24 + 24)[0]
secs = [struct.unpack_from("<8sIIII", d, pe + 24 + opt + 40 * i) for i in range(ns)]
def off(va):
    rva = va - base
    for name, vs, va0, rs, ro in secs:
        if va0 <= rva < va0 + max(vs, rs): return rva - va0 + ro
for a in sys.argv[2:]:
    o = off(int(a, 16)); raw = d[o:o + 16]
    print(a, raw.hex(), "f32", struct.unpack_from("<4f", raw), "f64", struct.unpack_from("<d", raw)[0])
