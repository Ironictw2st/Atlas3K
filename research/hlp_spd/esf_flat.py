"""Tokenise a CAAB (0xABCA) ESF whose root record holds a flat stream of primitives
(hlp_data.esf / spd_data.esf). Returns a list of (type_code, value) tokens.

usage: esf_flat.py <file.esf> [max_tokens]   -> prints tokens with offsets
"""
import struct, sys


def cauleb(b, p):
    v = 0
    while True:
        c = b[p]; p += 1
        v = (v << 7) | (c & 0x7F)
        if not c & 0x80:
            return v, p


def header(b):
    magic, unk, ts, names_off = struct.unpack_from("<IIII", b, 0)
    assert magic == 0xABCA, hex(magic)
    p = 16
    assert b[p] == 0x80
    name, ver = struct.unpack_from("<HB", b, p + 1)
    size, p = cauleb(b, p + 4)
    return dict(unk=unk, ts=ts, names_off=names_off, root_name=name, root_ver=ver,
                body=p, end=p + size)


SIZES = {0x01: 1, 0x02: 1, 0x03: 2, 0x04: 4, 0x05: 8, 0x06: 1, 0x07: 2, 0x08: 4, 0x09: 8, 0x0a: 4, 0x0b: 8,
         0x0c: 8, 0x0d: 12, 0x10: 2, 0x12: 0, 0x13: 0, 0x14: 0, 0x15: 0, 0x16: 1, 0x17: 2, 0x18: 3,
         0x19: 0, 0x1a: 1, 0x1b: 2, 0x1c: 3, 0x1d: 0}


def tokens(b, start, end, limit=None):
    p = start
    out = []
    while p < end and (limit is None or len(out) < limit):
        t = b[p]; q = p + 1
        if t in (0x12, 0x13):
            v = t == 0x12
        elif t == 0x14:
            v = 0
        elif t == 0x15:
            v = 1
        elif t in (0x16, 0x06):
            v = b[q]
        elif t in (0x17, 0x07):
            v = b[q] | b[q + 1] << 8
        elif t == 0x18:
            v = b[q] << 16 | b[q + 1] << 8 | b[q + 2]  # 24-bit compact ints are big-endian
        elif t == 0x08:
            v = struct.unpack_from("<I", b, q)[0]
        elif t == 0x04:
            v = struct.unpack_from("<i", b, q)[0]
        elif t == 0x0a:
            v = struct.unpack_from("<f", b, q)[0]
        elif t == 0x19:
            v = 0
        elif t == 0x1a:
            v = struct.unpack_from("<b", b, q)[0]
        elif t == 0x1b:
            v = struct.unpack_from("<h", b, q)[0]
        elif t == 0x1d:
            v = 0.0
        elif t == 0x01:
            v = bool(b[q])
        elif t == 0x0c:
            v = struct.unpack_from("<ff", b, q)
        elif t >= 0x40 and t < 0x80:
            n, q2 = cauleb(b, q)
            out.append((p, t, bytes(b[q2:q2 + n])))
            p = q2 + n
            continue
        else:
            raise ValueError(f"type {t:#x} at {p:#x}")
        out.append((p, t, v))
        p = q + SIZES[t]
    return out, p


if __name__ == "__main__":
    b = open(sys.argv[1], "rb").read()
    h = header(b)
    print(h)
    lim = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    toks, _ = tokens(b, h["body"], h["end"], lim)
    for off, t, v in toks:
        print(f"{off:08x} {t:02x} {v}")
