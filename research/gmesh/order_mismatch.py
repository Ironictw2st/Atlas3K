"""Mismatched grid points of Land_10_0 (BOB grid vs native dump): BOB's tile visiting order there vs the native tree
key order, and what each tile answers (from BOB's own call dump)."""
import sys, collections, numpy as np
sys.argv=['tree_fit.py']
src=open('tree_fit.py',encoding='utf-8').read().replace("for depth in range(4, 13):","for depth in []:")
exec(compile(src,'tree_fit.py','exec'))
B_DIR='Z:/Claude/TerryClone/output/mesh_parity/gmesh_bob_grids/'; N_DIR='Z:/Claude/TerryClone/output/mesh_parity2/dump_trace/'
bg=np.fromfile(B_DIR+'Land_10_0.bob.bin',np.float32).reshape(370,370); ng=np.fromfile(N_DIR+'Land_10_0.y.bin',np.float32).reshape(370,370)
k=keys(8,(0,1,2,3),roots["(-1,-1)..(maxX,maxZ)"])
mis=np.argwhere((bg!=ng)&(bg!=-20)&(ng!=-20))
print('mismatched points', len(mis))
stats=collections.Counter(); shown=0
for j,i in mis:
    x=float(F(F(int(i))*cell)); z=float(F(F(3690+int(j))*cell))
    s=seqs.get((x,z))
    if s is None: stats['no bob seq']+=1; continue
    if -1 in s: stats['unknown tile']+=1; continue
    kk=[i2 for i2 in s if i2 in k]
    nat=sorted(kk,key=lambda r:k[r])
    stats['bob order == native order' if nat==s else 'order differs']+=1
    if shown<6 and nat!=s:
        shown+=1; print((x,z),'bob',[(r,paths[rec[r]['path']].split(chr(92))[3],k[r][0]) for r in s],'\n   native',[(r,k[r][0]) for r in nat])
print(stats)
