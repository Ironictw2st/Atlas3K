"""Dump an RMV2 file's header, LOD/mesh headers and (material 96/terrain) vertex/index stats.
usage: rmv2_dump.py <file.rigid_model_v2> [--verts N]"""
import struct, sys
import numpy as np

def read(path):
    b = open(path, 'rb').read()
    assert b[:4] == b'RMV2', 'not rmv2'
    ver, nlod = struct.unpack_from('<II', b, 4)
    skel = b[12:140].split(b'\0')[0]
    lods = []
    for l in range(nlod):
        h = struct.unpack_from('<IIIIfII', b, 140 + l * 28)
        meshes = []
        off = h[3]
        for m in range(h[0]):
            mh = struct.unpack_from('<HHIIIII6f', b, off)
            mat, rf, size, voff, vcount, ioff, icount = mh[:7]
            bmin, bmax = mh[7:10], mh[10:13]
            shader = b[off+48:off+60].split(b'\0')[0]
            meshes.append(dict(off=off, mat=mat, rf=rf, size=size, voff=voff, vcount=vcount, ioff=ioff, icount=icount,
                               bmin=bmin, bmax=bmax, shader=shader, hdr=b[off:off+80], mblock=b[off+80:off+voff]))
            off += size
        lods.append(dict(hdr=h, meshes=meshes))
    return b, ver, skel, lods

def verts(b, m):
    stride = (m['ioff'] - m['voff']) // max(1, m['vcount'])
    raw = np.frombuffer(b, np.uint8, m['vcount'] * stride, m['off'] + m['voff']).reshape(m['vcount'], stride)
    idx = np.frombuffer(b, np.uint16, m['icount'], m['off'] + m['ioff'])
    return stride, raw, idx

if __name__ == '__main__':
    b, ver, skel, lods = read(sys.argv[1])
    print(f'RMV2 v{ver} lods={len(lods)} skel={skel!r} size={len(b)}')
    for li, L in enumerate(lods):
        print(' lod', li, L['hdr'])
        for m in L['meshes']:
            print(f"  mesh off={m['off']} mat={m['mat']} rf={m['rf']} size={m['size']} voff={m['voff']} v={m['vcount']} ioff={m['ioff']} i={m['icount']} shader={m['shader']} bmin={m['bmin']} bmax={m['bmax']}")
            print('   material block', m['mblock'][:96].hex(' '))
            if m['vcount']:
                stride, raw, idx = verts(b, m)
                print('   stride', stride, 'idx max', idx.max(), 'tris', len(idx)//3)
                if stride == 8:
                    h = raw.view(np.float16).astype(np.float32)
                    print('   x', h[:,0].min(), h[:,0].max(), 'y', h[:,1].min(), h[:,1].max(), 'z', h[:,2].min(), h[:,2].max(), 'w uniq', np.unique(h[:,3])[:10])
                n = int(sys.argv[sys.argv.index('--verts')+1]) if '--verts' in sys.argv else 0
                for i in range(n): print('   v', i, raw[i].tobytes().hex(' '))
