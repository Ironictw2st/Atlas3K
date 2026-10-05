"""Decompress a CAAB startpos.esf (COMPRESSED_DATA: LZMA payload) to a plain ESF. usage: startpos_unpack.py in.esf out.esf"""
import os
import struct
import sys
import lzma

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from esf_flat import cauleb

b = open(sys.argv[1], 'rb').read()
noff = struct.unpack_from('<I', b, 12)[0]
best = None
for p in range(16, noff - 5):
    if b[p] == 0x46:
        try:
            n, q = cauleb(b, p + 1)
        except Exception:
            continue
        if 100000 < n <= noff - q and (best is None or n > best[1]):
            best = (p, n, q)
p, n, q = best
data = b[q:q + n]
t = b[q + n:q + n + 40]
i = 3  # COMPRESSED_DATA_INFO record header (marker, name, size)
if t[i] == 0x08:
    size = struct.unpack_from('<I', t, i + 1)[0]; i += 5
elif t[i] == 0x18:
    size = int.from_bytes(t[i + 1:i + 4], 'big'); i += 4
elif t[i] == 0x17:
    size = struct.unpack_from('<H', t, i + 1)[0]; i += 3
else:
    raise SystemExit(f"unexpected size marker {t[i]:#x}")
j = t.index(0x46, i)
props = t[j + 2:j + 7]
out = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE).decompress(props + struct.pack('<Q', size) + data)
open(sys.argv[2], 'wb').write(out)
print("unpacked", len(out), "expected", size, out[:4].hex())
