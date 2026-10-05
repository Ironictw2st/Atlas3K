import sys, numpy as np
sys.path.insert(0,'.')
import gheight_cmp as G, lf_probe as P
F=np.float32
xs=set(np.unique(G.calls['x']).tolist())|set(np.unique(G.calls['z']).tolist())
tw=P.W//4; total=5912
T=F(595.1)/F(1784); Tp=F(F(F(1)/F(tw))*F(F(tw)*T))
cands={'tw*T':F(F(tw)*T),'tw*Tp':F(F(tw)*Tp),'986.05096':F(986.0509643554688),'986.051':F(986.051),'2*tw*Tp/2':F(F(2*tw)*F(Tp/F(2)))}
for nm,ext in cands.items():
    cell=F(ext/F(total))
    hits=sum(1 for I in range(total+1) if float(F(F(I)*cell)) in xs)
    hits2=sum(1 for I in range(total+1) if float(F(F(F(I))*F(Tp/F(2)))) in xs)
    print(nm, repr(ext), repr(cell), hits, 'Tp/2:', hits2)
