import numpy as np
F=np.float32
c=np.load('Z:/Claude/TerryClone/output/mesh_parity/gcalls.npy')
T=F(595.1)/F(1784); Tp=F(F(F(1)/F(2956))*F(F(2956)*T)); cell=F(F(F(2956)*Tp)/F(5912))
b=np.fromfile('Z:/Claude/TerryClone/output/mesh_parity/gmesh_bob_grids/Land_0_0.bob.bin',np.float32).reshape(370,370)
a=np.fromfile('Z:/Claude/TerryClone/output/mesh_parity/gmesh_native_dump2/Land_0_0.y.bin',np.float32).reshape(370,370)
keys=set(zip(c['x'].tolist(),c['z'].tolist()))
mis=np.argwhere(a!=b); print('mismatches', len(mis))
cov=[(j,i) for j,i in mis if (float(F(F(i)*cell)),float(F(F(j)*cell))) in keys]
print('covered', len(cov), cov[:10])
print('x range', c['x'].min(), c['x'].max(), 'z range', c['z'].min(), c['z'].max())
g={float(F(F(i)*cell)):i for i in range(371)}
pts=[(g[x],g[z]) for x,z in keys if x in g and z in g]
print('grid points covered', len(pts))
J=np.array([p[1] for p in pts]); I=np.array([p[0] for p in pts]); print('rows', J.min(), J.max(), 'cols', I.min(), I.max())
eq=sum(a[j,i]==b[j,i] for i,j in pts); print('equal among covered', eq)
print('mismatch rows', np.unique(mis[:,0])[:20], 'cols', np.unique(mis[:,1])[:20])
