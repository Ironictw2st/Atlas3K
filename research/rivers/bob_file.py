"""BOB's river .rigid_model_v2 from the raw 32-byte vertices + indices of FUN_18015e9e0 (bob_mesh.build):
FUN_180146460 (halves -> floats, NTB bytes decoded b/255*2-1), VERTEX_LIST_CLEANER (vertices renumbered by first use
in the index list), MODEL_PROCESSOR::write (winding flipped, NTB re-encoded trunc((v+1)*127.5), pivot = bbox centre).
Compares with BOB's files. usage: bob_file.py [jsonl] [bob models dir]"""
import struct, sys, glob, numpy as np
F = np.float32
UNINIT = [0xA5, 0xA6, 0xA7, 0x31A, 0x31B]      # uninitialised memory in BOB: differs between BOB runs of the same input


def ntb(b):
    t = F(F(b) * F(1 / 255.)); v = F(F(t + t) - F(1))
    return int(F(F(v + F(1)) * F(127.5))) & 0xff


def build_file(raw, idx):
    order, remap = [], {}
    for i in idx:
        if i not in remap: remap[i] = len(order); order.append(i)
    r = raw[order]; n = len(order)
    pos = r[:, 0:6].copy().view(np.float16).astype(np.float32)
    lo, hi = pos.min(0), pos.max(0)
    piv = ((lo + hi) * F(0.5)).astype(F)
    p = (pos - piv).astype(F)
    V = np.zeros((n, 48), np.uint8)
    fl = np.zeros((n, 8), np.float32)
    fl[:, 0:3] = p; fl[:, 3] = 1
    fl[:, 4:8] = r[:, 8:16].copy().view(np.float16).astype(np.float32)
    V[:, :32] = fl.view(np.uint8).reshape(n, 32)
    enc = np.vectorize(ntb, otypes=[np.uint8])
    for g in range(3):
        V[:, 32 + 4 * g:35 + 4 * g] = enc(r[:, 16 + 4 * g:19 + 4 * g])
    tri = [remap[i] for t in range(0, len(idx), 3) for i in (idx[t], idx[t + 2], idx[t + 1])]
    hdr = bytearray(0xA8 + 0x50 + 860)
    struct.pack_into('<4sII', hdr, 0, b'RMV2', 8, 1)
    struct.pack_into('<IIIIf', hdr, 0x8C, 1, n * 48, len(tri) * 2, 0xA8, 1e6)
    vo = 0x50 + 860; io = vo + n * 48
    struct.pack_into('<HHIIIII', hdr, 0xA8, 68, 0, io + len(tri) * 2, vo, n, io, len(tri))
    struct.pack_into('<6f', hdr, 0xC0, *lo, *hi)        # world bbox (before the pivot)
    hdr[0xD8:0xD8 + 13] = b'rigid_default'; hdr[0xE7] = 0x8D
    hdr[0xF0:0xF2] = b'\x9e\xd4'
    m = 0xF8
    struct.pack_into('<H', hdr, m, 13); hdr[m + 2:m + 7] = b'River'; hdr[m + 34] = ord('/')
    o = m + 0x224
    struct.pack_into('<3f', hdr, o, *piv); o += 12
    for k in range(3):
        for rr in range(3): struct.pack_into('<f', hdr, o + (rr * 4 + rr) * 4, 1.0)
        o += 48
    struct.pack_into('<ii', hdr, o, -1, -1)
    return bytes(hdr) + V.tobytes() + np.array(tri, np.uint16).tobytes()


def diff(a, b):
    n = max(len(a), len(b))
    return [i for i in range(n) if i >= len(a) or i >= len(b) or a[i] != b[i]]


if __name__ == "__main__":
    sys.path.insert(0, '.')
    from raw_cmp import load
    D = load(sys.argv[1] if len(sys.argv) > 1 else '../bob_re/frida_out/frida_rivers2_main190.jsonl')
    ref = sys.argv[2] if len(sys.argv) > 2 else 'Z:/Claude/TerryClone/output/bob_runs/frida_rivers2_main190_bob_terrain/models'
    files = {f: open(f, 'rb').read() for f in glob.glob(ref + '/*.rigid_model_v2')}
    same = det = 0
    for i, d in enumerate(D):
        mine = build_file(d['raw'], list(d['idx']))
        best = min(files, key=lambda f: len(diff(mine, files[f])) if len(files[f]) == len(mine) else 10 ** 9)
        dd = diff(mine, files[best]); real = [x for x in dd if x not in UNINIT]
        same += not dd; det += not real
        print(f"dump {i:2d} -> {best.split(chr(92))[-1].split('/')[-1]:32s} bytes {len(mine)} differ {len(dd)} (excl. uninitialised {len(real)}) {[hex(x) for x in real[:8]]}")
    print(f"identical files {same}/{len(D)}; identical apart from BOB's uninitialised bytes {det}/{len(D)}")
