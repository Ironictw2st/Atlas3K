import sys, os, glob, struct, re
sys.path.insert(0, r"Z:\Claude\TerryClone\tools\bob_mcp")
import packindex
import numpy as np
D = r"C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\data"
IDX = {}
for p in sorted(glob.glob(os.path.join(D, "*.pack"))):
    try:
        for e in packindex.index(p):
            IDX[e[0].lower().replace('/', chr(92))] = (p, e)
    except Exception:
        pass
def read(path):
    k = path.lower().replace('/', chr(92))
    p, e = IDX[k]
    return packindex.read(p, e)
for name in sys.argv[1:]:
    b = read(name)
    if name.endswith('.wsmodel'):
        print(b.decode(errors='replace'))
        g = re.search(rb'<geometry>([^<]+)</geometry>', b).group(1).decode()
        b = read(g); print('->', g)
    ver, lods = struct.unpack_from('<II', b, 4)
    print('version', ver, 'lods', lods, 'size', len(b))
    for l in range(lods):
        mc, vb, ib, first, dist = struct.unpack_from('<IIIIf', b, 140 + l * 28)
        off = first
        for m in range(mc):
            mat, rf, sec, vo, vc, io, ic = struct.unpack_from('<HHIIIII', b, off)
            bb = struct.unpack_from('<6f', b, off + 24)
            stride = (io - vo) // vc if vc else 0
            vf = struct.unpack_from('<H', b, off + 80)[0] if mat not in (49, 101) else None
            piv = struct.unpack_from('<3f', b, off + 80 + 548) if mat not in (49, 101) else None
            print(f' lod{l} mesh{m} mat {mat} vf {vf} stride {stride} verts {vc} idx {ic} bbox {[round(x,2) for x in bb]} pivot {piv}')
            if l == 0 and m == 0 and stride:
                raw = np.frombuffer(b, np.uint16, count=vc * stride // 2, offset=off + vo).reshape(vc, stride // 2)
                pos = raw[:, :4].view(np.float16).astype(np.float32)
                print('   half xyzw min', pos.min(0), 'max', pos.max(0))
            off += sec
