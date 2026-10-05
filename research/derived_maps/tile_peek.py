"""tile_peek.py <category/name> ...: tile DB size, mask, meshes and hf map of campaign tiles."""
import os
import struct
import sys

import tiles_lib as T

db = T.read_db()
for arg in sys.argv[1:]:
    p = 'terrain\\tiles\\campaign\\' + arg.replace('/', '\\') + '\\'
    d = db[p.lower()]
    print(p, d['w'], d['h'], 'mask', d['mask'][:40])
    for m in ['mesh.rigid_model_v2', 'outfield_mesh.rigid_model_v2']:
        f = os.path.join(T.VAN, p, m)
        if not os.path.exists(f):
            print('  no', m)
            continue
        b = open(f, 'rb').read()
        ver, lods = struct.unpack_from('<II', b, 4)
        mc, vb, ib, first, _ = struct.unpack_from('<IIIIf', b, 140)
        mat, rf, sec, vo, vc, io, ic = struct.unpack_from('<HHIIIII', b, first)
        bb = struct.unpack_from('<6f', b, first + 24)
        print('  ', m, 'lods', lods, 'meshes', mc, 'mat', mat, 'verts', vc, 'stride', (io - vo) // max(vc, 1), 'bbox', [round(x, 2) for x in bb])
    hm = T.hf_map(p)
    if hm is not None:
        r = hm[0]
        print('   hf', r.shape, 'min', r.min(), 'max', r.max(), [round(x, 3) for x in hm[1]])
