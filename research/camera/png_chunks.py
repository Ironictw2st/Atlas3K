import struct, sys, zlib
for p in sys.argv[1:]:
    b = open(p, 'rb').read(); o = 8; idat = b''
    print(p, len(b))
    while o < len(b):
        n, t = struct.unpack_from('>I4s', b, o); d = b[o + 8:o + 8 + n]
        if t != b'IDAT': print(' ', t, n, d[:60])
        else: idat += d
        o += 12 + n
    print('  IDAT total', len(idat), 'zlib hdr', idat[:2].hex(), 'chunks?')
    raw = zlib.decompress(idat); w, h = struct.unpack_from('>II', b, 16)
    stride = w * 2 + 1; import collections
    print('  filters', collections.Counter(raw[i * stride] for i in range(h)).most_common(6))
