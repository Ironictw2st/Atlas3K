"""Native global_meshes vs BOB's, per file: rigid_model_v2 structure (header bytes, bounds, vertices, indices) and
compressed_map bytes. Ignores BOB's uninitialised bytes 0x148..0x14B (+0xA5..0xA7 on sea meshes).
usage: file_cmp.py <native global_meshes> [<bob global_meshes>]"""
import os, sys, struct, collections, numpy as np
N = sys.argv[1]; B = sys.argv[2] if len(sys.argv) > 2 else 'Z:/Claude/TerryClone/output/bob_runs/frida_gmesh2_main190_bob/global_meshes'
def rm(b):
    vo, vc, io, ic = struct.unpack_from('<4I', b, 0xB0)
    v = np.frombuffer(b, np.float32, vc * 4, 0xA8 + vo).reshape(-1, 4); i = np.frombuffer(b, np.uint16, ic, 0xA8 + io)
    return v, i, struct.unpack_from('<6f', b, 0xC0)
ign = lambda f, k: 0x148 <= k <= 0x14B or (f.startswith('sea') and 0xA5 <= k <= 0xA7)
same = collections.Counter(); kinds = collections.Counter(); ex = collections.defaultdict(list)
for f in sorted(os.listdir(B)):
    b = open(os.path.join(B, f), 'rb').read(); p = os.path.join(N, f)
    ext = f.split('.')[1]
    if not os.path.exists(p): kinds[(ext, 'missing')] += 1; continue
    a = open(p, 'rb').read()
    if len(a) == len(b) and all(a[k] == b[k] or ign(f, k) for k in range(len(a))): same[ext] += 1; continue
    if ext == 'rigid_model_v2':
        va, ia, ba = rm(a); vb, ib, bb = rm(b)
        why = []
        if len(va) != len(vb): why.append('vcount')
        elif not np.array_equal(va, vb): why.append('verts')
        if len(ia) != len(ib): why.append('icount')
        elif not np.array_equal(ia, ib): why.append('idx')
        if ba != bb: why.append('bounds')
        if not why:
            d = [k for k in range(min(len(a), len(b))) if a[k] != b[k] and not ign(f, k)]
            why.append('header ' + ' '.join(hex(k) for k in d[:6]))
        key = (ext, ' '.join(why))
        ex[key].append((f, len(vb), len(va), len(ib) // 3, len(ia) // 3))
    else:
        key = (ext, 'size' if len(a) != len(b) else 'bytes')
        ex[key].append((f, len(b), len(a)))
    kinds[key] += 1
print('identical', dict(same))
for k, v in kinds.most_common(): print(v, k, ex[k][:3])
