import sys, numpy as np
sys.path.insert(0,'.')
from grid_cmp import *
seq=bob_sequence(); h,mg=bob_dumps()
for idx in [int(a) for a in sys.argv[1:]]:
    kind,k,name=seq[idx]; d=h[idx]; n=d['n']
    b=np.fromfile(BIN+d['file'],np.float32).reshape(n,n); a=np.fromfile(NAT+f'{kind}_{k//16}_{k%16}.y.bin',np.float32).reshape(n,n)
    m=(b!=-20)&(a!=-20); du=np.abs(a.view(np.int32).astype(np.int64)-b.view(np.int32).astype(np.int64))[m]
    print(name,'eq',(a[m]==b[m]).mean(),'ulp<=2',(du<=2).mean(),'max|d|',np.abs(a-b)[m].max(), 'holes', ((a==-20)!=(b==-20)).sum())
    j,i=np.argwhere(m&(a!=b))[0]; print('  first diff at', j,i, a[j,i], b[j,i])
