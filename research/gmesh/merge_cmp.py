"""Native merger output (ATLAS3K_GMESH_DUMP *.merged.bin, from BOB's grids) vs BOB's merged index lists."""
import os, glob, sys, numpy as np
B=os.environ.get('BOBGRIDS','Z:/Claude/TerryClone/output/mesh_parity/gmesh_bob_grids/'); N=sys.argv[1] if len(sys.argv)>1 else 'Z:/Claude/TerryClone/output/mesh_parity/gmesh_native_dump/'
same=tot=0; rows=[]
for f in sorted(glob.glob(B+'*.merged.bin')):
    k=os.path.basename(f)[:-11]; b=np.fromfile(f,np.uint32); p=N+k+'.merged.bin'
    if not os.path.exists(p): rows.append((k,len(b),None)); continue
    a=np.fromfile(p,np.uint32); tot+=1; e=len(a)==len(b) and np.array_equal(a,b); same+=e
    pre=0
    for x,y in zip(a,b):
        if x!=y: break
        pre+=1
    rows.append((k,len(b)//3,len(a)//3,e,pre//3))
for r in rows[:15]: print(r)
print(f'merged lists identical {same}/{tot}')
