"""Which of the 223x223 grid quads does a vanilla land mesh's surface cover? And do vertex heights equal lf samples?"""
import struct
import sys

import numpy as np

V = r"Z:\Claude\TerryClone\Vanilla\Map\terrain\campaigns\3k_dlc07_main_map"
n = int(sys.argv[1]) if len(sys.argv) > 1 else 0
b = open(fr"{V}\global_meshes\land_mesh_{n}.rigid_model_v2", 'rb').read()
vc, = struct.unpack_from('<I', b, 0xB4)
io, ic = struct.unpack_from('<II', b, 0xB8)
bb = struct.unpack_from('<6f', b, 0xC0)
v = np.frombuffer(b, '<f4', count=vc * 4, offset=0x150).reshape(-1, 4)[:, :3].astype(np.float64)
idx = np.frombuffer(b, '<u2', count=ic, offset=0xA8 + io).reshape(-1, 3)
CELL = 595.1 / 3568
tc, tr = int(round(bb[0] / (223 * CELL))), int(round(bb[2] / (223 * CELL)))
gi = np.round(v[:, 0] / CELL).astype(int) - 223 * tc
gj = np.round(v[:, 2] / CELL).astype(int) - 223 * tr
p = v[idx]
area = (p[:, 1, 0] - p[:, 0, 0]) * (p[:, 2, 2] - p[:, 0, 2]) - (p[:, 2, 0] - p[:, 0, 0]) * (p[:, 1, 2] - p[:, 0, 2])
surf = np.abs(area) > 1e-9
cover = np.zeros((223, 223), bool)
for t in idx[surf]:
    xs, zs = gi[t], gj[t]
    # mark quads whose centre lies inside the triangle
    i0, i1, j0, j1 = xs.min(), xs.max(), zs.min(), zs.max()
    for j in range(j0, j1):
        for i in range(i0, i1):
            cx, cz = i + 0.5, j + 0.5
            (ax, bx, cx2), (az, bz, cz2) = xs, zs
            d = (bx - ax) * (cz2 - az) - (cx2 - ax) * (bz - az)
            u = ((bx - cx) * (cz2 - cz) - (cx2 - cx) * (bz - cz)) / d
            w = ((cx2 - cx) * (az - cz) - (ax - cx) * (cz2 - cz)) / d
            if u >= -1e-9 and w >= -1e-9 and 1 - u - w >= -1e-9:
                cover[j, i] = True
print(f'mesh {n} tile ({tc},{tr}): quads covered {cover.sum()} of {223 * 223}; uncovered {223 * 223 - cover.sum()}')
unc = np.argwhere(~cover)
print('uncovered rows (j) histogram:', np.bincount(unc[:, 0], minlength=223).nonzero()[0][:20], ' cols (i):', np.bincount(unc[:, 1], minlength=223).nonzero()[0][:20])
print('uncovered sample', unc[:10].tolist())
# heights vs lf
L = np.frombuffer(open(V + r"\lf_height_map.dds", 'rb').read(), '<u2', offset=128, count=7136 * 5620).reshape(5620, 7136)
rows = 5619 - 2 * (gj + 223 * tr)
cols = 2 * (gi + 223 * tc)
ok = (rows >= 0) & (cols < 7136)
lfy = L[rows[ok], cols[ok]].astype(np.float32) * np.float32(0.000218712) - np.float32(3.12725)
d = np.abs(v[ok, 1] - lfy)
top = v[:, 1] > -100
print('vertex y vs lf: max |d| %.6f, frac exact(<1e-5) %.4f' % (d[v[ok, 1] > -50].max(), (d < 1e-5).mean()))
