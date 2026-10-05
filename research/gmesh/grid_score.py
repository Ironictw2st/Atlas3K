import numpy as np, glob, os, sys
B='Z:/Claude/TerryClone/output/mesh_parity/gmesh_bob_grids/'; N=sys.argv[1] if len(sys.argv)>1 else 'Z:/Claude/TerryClone/output/mesh_parity/gmesh_native_dump2/'
tot=eqv=nv=meq=n=0
for f in sorted(glob.glob(B+'*.bob.bin')):
    k=os.path.basename(f)[:-8]; b=np.fromfile(f,np.float32); p=N+k+'.y.bin'
    if not os.path.exists(p): continue
    a=np.fromfile(p,np.float32); tot+=((a==-20)!=(b==-20)).sum(); n+=1; meq+=np.array_equal(a,b)
    m=(b!=-20)&(a!=-20); eqv+=(a[m]==b[m]).sum(); nv+=m.sum()
print(f'hole mismatches {tot}; heights equal {eqv}/{nv} = {eqv/nv:.2%}; grids identical {meq}/{n}')
