import numpy as np, merger_proto as M
v_ref, idx_ref, bb = M.read_mesh(0)
valid = M.global_validity(); L = M.lf_heights()
xs, ys, zs, flags, nrm, tris = M.build(0, 0, L, valid)
out = M.merge(xs, ys, zs, flags, nrm, tris, np.float32(0.9999))
N=M.N; C=float(M.CELL)
ours=set(q for t in out for q in t)
gi=np.round(v_ref[:,0]/C).astype(int); gj=np.round(v_ref[:,2]/C).astype(int)
surf_ref=set()
p=v_ref[idx_ref].astype(float)
area=np.abs((p[:,1,0]-p[:,0,0])*(p[:,2,2]-p[:,0,2])-(p[:,2,0]-p[:,0,0])*(p[:,1,2]-p[:,0,2]))
for t in idx_ref[area>1e-9]:
    for q in t: surf_ref.add(gj[q]*N+gi[q])
print('ours verts',len(ours),'vanilla verts',len(surf_ref),'common',len(ours&surf_ref))
def show(S,name):
    print(name)
    for j in range(60,76):
        print(''.join('#' if j*N+i in S else '.' for i in range(60,130)))
show(surf_ref,'vanilla'); show(ours,'ours')
import collections
# normals around a vanilla-removed region
k=70*N+100
print('flags sample', flags[k], 'nrm', nrm[k], 'dots to 4-neigh', [float(abs(nrm[k]@nrm[k+d])) for d in (1,-1,N,-N)])
