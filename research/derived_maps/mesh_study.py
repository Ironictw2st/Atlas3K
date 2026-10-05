"""Structure of vanilla land_mesh_N: grid alignment, vertex order, triangle order, skirts."""
import struct, sys
import numpy as np

V = r"Z:\Claude\TerryClone\Vanilla\Map\terrain\campaigns\3k_dlc07_main_map"
n = int(sys.argv[1]) if len(sys.argv) > 1 else 0
kind = sys.argv[2] if len(sys.argv) > 2 else 'land'
b = open(fr"{V}\global_meshes\{kind}_mesh_{n}.rigid_model_v2", 'rb').read()
vc, = struct.unpack_from('<I', b, 0xB4)
io, ic = struct.unpack_from('<II', b, 0xB8)
bb = struct.unpack_from('<6f', b, 0xC0)
v = np.frombuffer(b, '<f4', count=vc * 4, offset=0x150).reshape(-1, 4)[:, :3].astype(np.float64)
idx = np.frombuffer(b, '<u2', count=ic, offset=0xA8 + io).reshape(-1, 3)
print(f'{kind}_mesh_{n}: {vc} verts, {len(idx)} tris, bbox {bb}')
cell = 0.166788  # world units per mesh cell (2 lf px)
ox, oz = bb[0], bb[2]
gx = (v[:, 0] - ox) / (bb[3] - bb[0]) * 223
gz = (v[:, 2] - oz) / (bb[5] - bb[2]) * 223
print('grid x frac max dev', np.abs(gx - np.round(gx)).max(), ' z', np.abs(gz - np.round(gz)).max())
gi, gj = np.round(gx).astype(int), np.round(gz).astype(int)
# vertex order
print('first 30 verts (i,j,y):', [(int(a), int(c), round(float(y), 3)) for a, c, y in zip(gi[:30], gj[:30], v[:30, 1])])
# duplicates in xz = skirt vertices
key = gi * 1000 + gj
uniq, first = np.unique(key, return_index=True)
print('distinct xz', len(uniq), ' first index of a repeated xz', np.setdiff1d(np.arange(vc), first)[:5])
# triangle classification
p = v[idx]
area = np.abs((p[:, 1, 0] - p[:, 0, 0]) * (p[:, 2, 2] - p[:, 0, 2]) - (p[:, 2, 0] - p[:, 0, 0]) * (p[:, 1, 2] - p[:, 0, 2]))
flat = area > 1e-9
print('surface tris', flat.sum(), ' vertical (skirt) tris', (~flat).sum(), ' first skirt tri at', np.argmax(~flat))
print('first 12 tris:', idx[:12].tolist())
# winding: normals up?
nrm = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
print('surface normals y>0 frac', (nrm[flat, 1] > 0).mean())
# triangle footprint sizes in cells
ext = np.stack([gi[idx].max(1) - gi[idx].min(1), gj[idx].max(1) - gj[idx].min(1)], 1)[flat]
u, c = np.unique(ext, axis=0, return_counts=True)
print('footprint (di,dj) counts top:', sorted(zip(c.tolist(), map(tuple, u.tolist())), reverse=True)[:12])
