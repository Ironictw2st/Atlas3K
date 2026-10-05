"""Pixel-level comparison: float buffer -> BOB's encode (ceil(max(h/highest,0)*65535)) vs BOB's PNG.
usage: px_cmp.py <bob.png> <buffer .f32 or .npy> [W H]"""
import struct, sys, zlib
import numpy as np
F = np.float32
def png16(p):
    b = open(p, 'rb').read(); o = 8; idat = b''; text = {}
    w, h = struct.unpack_from('>II', b, 16)
    while o < len(b):
        n, t = struct.unpack_from('>I4s', b, o); d = b[o + 8:o + 8 + n]
        if t == b'IDAT': idat += d
        if t == b'tEXt': k, v = d.split(b'\0'); text[k.decode()] = v.decode()
        o += 12 + n
    raw = np.frombuffer(zlib.decompress(idat), np.uint8).reshape(h, w * 2 + 1)
    bpp = 2; out = np.zeros((h, w * 2), np.int32); prev = np.zeros(w * 2, np.int32)
    for y in range(h):
        f = raw[y, 0]; cur = raw[y, 1:].astype(np.int32)
        if f == 0: rec = cur
        elif f == 2: rec = (cur + prev) & 255
        else:
            rec = np.zeros_like(cur)
            for x in range(w * 2):
                a = rec[x - bpp] if x >= bpp else 0; c = prev[x - bpp] if x >= bpp else 0; bb = prev[x]
                if f == 1: p = a
                elif f == 3: p = (a + bb) >> 1
                else:
                    pa, pb, pc = abs(bb - c), abs(a - c), abs(a + bb - 2 * c)
                    p = a if pa <= pb and pa <= pc else (bb if pb <= pc else c)
                rec[x] = (cur[x] + p) & 255
        out[y] = rec; prev = rec
    return (out[:, 0::2] * 256 + out[:, 1::2]).astype(np.uint16), text
def encode(buf):
    hi = buf.max(); r = np.maximum((buf / hi).astype(F), F(0)); return np.ceil((r * F(65535)).astype(F)).astype(np.uint16), hi
if __name__ == "__main__":
    bobpx, text = png16(sys.argv[1])
    H, W = bobpx.shape
    np.save(sys.argv[1] + ".npy", bobpx)
    buf = np.load(sys.argv[2]) if sys.argv[2].endswith('.npy') else np.fromfile(sys.argv[2], np.float32).reshape(H, W)
    px, hi = encode(buf.astype(F))
    print(f"text {text}  highest {hi!r} -> {float(hi * F(1/65535)):f}")
    print(f"pixels identical {(px == bobpx).mean():.6%}  max |d| {np.abs(px.astype(int) - bobpx).max()}")
