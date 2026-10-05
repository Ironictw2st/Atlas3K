import sys, numpy as np
sys.path.insert(0,'.')
from grid_cmp import *
seq=bob_sequence(); h,mg=bob_dumps()
tot=eq=0
for (kind,k,name),d in list(zip(seq,h))[:int(sys.argv[1]) if len(sys.argv)>1 else 60]:
    p=NAT+f'{kind}_{k//16}_{k%16}.y.bin'
    if not os.path.exists(p): continue
    a=np.fromfile(p,np.float32); b=np.fromfile(BIN+d['file'],np.float32)
    m=b!=-20; tot+=m.sum(); eq+=(a[m]==b[m]).sum()
print(f'valid points equal {eq}/{tot} = {eq/tot:.2%}')
