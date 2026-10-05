"""FASTBIN0 TABLE_INDEXED compressed_map reader (port of src/Atlas3K.Formats/Maps/CompressedMap.Decode):
returns (u16 raster [h, w] with row 0 = north, header floats)."""
import struct
import numpy as np


def _bits_for(n):
    b = 0
    while (1 << b) < n: b += 1
    return b


def _read_bits(data, start, count, bits):
    out = np.empty(count, np.int64); acc = 0; nacc = 0; pos = start; mask = (1 << bits) - 1
    for i in range(count):
        while nacc < bits:
            acc |= data[pos] << nacc; pos += 1; nacc += 8
        out[i] = acc & mask; acc >>= bits; nacc -= bits
    return out


def read(path):
    b = open(path, "rb").read()
    assert b[:8] == b"FASTBIN0"
    w, h, tw, th = struct.unpack_from("<IIII", b, 10)
    header = struct.unpack_from("<6f", b, 26)
    pos = 50; nl = struct.unpack_from("<H", b, pos)[0]; pos += 2 + nl
    cnt = struct.unpack_from("<I", b, pos)[0]; offs = struct.unpack_from(f"<{cnt}I", b, pos + 4); pos += 4 + 4 * cnt
    sc = struct.unpack_from("<I", b, pos)[0]; sizes = struct.unpack_from(f"<{sc}H", b, pos + 4); pos += 4 + 2 * sc
    pos += 4; data = b[pos:]
    cols = (w + tw - 1) // tw; n = tw * th
    out = np.zeros((h, w), np.uint16)
    for t in range(cnt):
        d = data[offs[t]:offs[t] + sizes[t]]
        if len(d) == 1 + 2 * n:
            tile = np.frombuffer(d, np.uint16, n, 1)
        elif d[0] >= 128:
            bits = d[0] - 127; base = struct.unpack_from("<H", d, 1)[0]
            tile = (base + _read_bits(d, 3, n, bits)).astype(np.uint16)
        else:
            c = d[0] + 1; pal = np.frombuffer(d, np.uint16, c, 1); pb = _bits_for(c)
            tile = np.full(n, pal[0], np.uint16) if pb == 0 else pal[_read_bits(d, 1 + 2 * c, n, pb)]
        row, col = divmod(t, cols); tile = tile.reshape(th, tw)
        ys, xs = row * th, col * tw
        out[ys:min(ys + th, h), xs:min(xs + tw, w)] = tile[:min(th, h - ys), :min(tw, w - xs)]
    return out, header
