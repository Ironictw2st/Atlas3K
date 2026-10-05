import sys, glob, os, numpy as np
sys.path.insert(0,'.')
from grid_cmp import *
seq=bob_sequence(); h,mg=bob_dumps()
nat={os.path.basename(f)[:-6]: np.fromfile(f,np.float32) for f in glob.glob(NAT+'*.y.bin')}
res=[]
for (kind,k,name),d in list(zip(seq,h))[:40]:
    b=np.fromfile(BIN+d['file'],np.float32)
    best=max((n for n in nat if n.startswith(kind)), key=lambda n: (np.abs(nat[n]-b)<1e-3).mean())
    res.append((kind,k,name,best,(np.abs(nat[best]-b)<1e-3).mean(), (nat[best]==b).mean()))
for r in res: print(r)
