import struct, zlib
import numpy as np
b = open('../bob_re/frida_out/cam_png/bob_s4.png', 'rb').read(); o = 8; idat = b''
while o < len(b):
    n, t = struct.unpack_from('>I4s', b, o)
    if t == b'IDAT': idat += b[o + 8:o + 8 + n]
    o += 12 + n
w, h = struct.unpack_from('>II', b, 16); raw = np.frombuffer(zlib.decompress(idat), np.uint8).reshape(h, w * 2 + 1)
px = np.load('../bob_re/frida_out/cam_png/bob_s4.png.npy')
rows = np.zeros((h, w * 2), np.uint8); rows[:, 0::2] = px >> 8; rows[:, 1::2] = px & 255
def filt(cur, prev, f):
    cur = cur.astype(np.int32); prev = prev.astype(np.int32)
    a = np.concatenate([[0, 0], cur[:-2]]); c = np.concatenate([[0, 0], prev[:-2]]); bb = prev
    if f == 0: r = cur
    elif f == 1: r = cur - a
    elif f == 2: r = cur - bb
    elif f == 3: r = cur - ((a + bb) >> 1)
    else:
        pa = np.abs(bb - c); pb = np.abs(a - c); pc = np.abs(a + bb - 2 * c)
        p = np.where((pa <= pb) & (pa <= pc), a, np.where(pb <= pc, bb, c)); r = cur - p
    return (r & 255).astype(np.uint8)
def score(r): r = r.astype(np.int32); return int(np.where(r < 128, r, 256 - r).sum())
ok = 0; bad = []
prev = np.zeros(w * 2, np.uint8)
for y in range(h):
    sc = [score(filt(rows[y], prev, f)) for f in range(5)]
    best = min(range(5), key=lambda f: (sc[f], f))
    if best == raw[y, 0] and (filt(rows[y], prev, best) == raw[y, 1:]).all(): ok += 1
    else: bad.append((y, raw[y, 0], best, sc))
    prev = rows[y]
print('rows matching minsum heuristic', ok, '/', h); print(bad[:5])
