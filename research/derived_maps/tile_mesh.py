"""Decode a campaign tile mesh (material 96, 8-byte vertices)."""
import os
import struct
import sys

import numpy as np

import tiles_lib as T


def read_tile_mesh(folder, name='mesh.rigid_model_v2', lod=0):
    f = os.path.join(T.VAN, folder, name)
    if not os.path.exists(f) or os.path.getsize(f) < 200:
        return None
    b = open(f, 'rb').read()
    mc, vb, ib, first, _ = struct.unpack_from('<IIIIf', b, 140 + lod * 28)
    mat, rf, sec, vo, vc, io, ic = struct.unpack_from('<HHIIIII', b, first)
    stride = (io - vo) // max(vc, 1)
    raw = np.frombuffer(b, np.uint8, count=vc * stride, offset=first + vo).reshape(vc, stride)
    idx = np.frombuffer(b, '<u2', count=ic, offset=first + io).reshape(-1, 3)
    return dict(mat=mat, stride=stride, raw=raw, idx=idx, first=first, vo=vo, bytes=b)


if __name__ == '__main__':
    for arg in sys.argv[1:]:
        folder = 'terrain\\tiles\\campaign\\' + arg.replace('/', '\\') + '\\'
        m = read_tile_mesh(folder)
        raw = m['raw']
        print(arg, 'mat', m['mat'], 'stride', m['stride'], 'verts', len(raw), 'tris', len(m['idx']))
        print('  header bytes after mesh header:', m['bytes'][m['first'] + 80:m['first'] + 80 + 64].hex())
        h = raw.view('<f2').astype(np.float32).reshape(len(raw), -1)
        u = raw.view('<u2').reshape(len(raw), -1)
        print('  as f16 min', h.min(0), 'max', h.max(0))
        print('  as u16 min', u.min(0), 'max', u.max(0))
        print('  first verts u16', u[:6].tolist())
