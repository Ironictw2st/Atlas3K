import sys, numpy as np
sys.path.insert(0,'.')
import gheight_cmp as G, lf_probe as P
F=np.float32
c=G.calls
xs=np.unique(c['x']); s=set(xs.tolist())
cent=[x for x in xs if (float(F(x+F(0.001))) in s) and (float(F(x-F(0.001))) in s)]
print(len(cent), cent[:12])
d=np.diff(np.array(cent,np.float64)); print('cell diffs', np.unique(np.round(d,7))[:5])
tw,th=P.W//4,P.H//4; total=2*max(tw,th); print('tw th total', tw, th, total)
T=F(595.1)/F(1784); Tp=F(F(F(1)/F(tw))*F(F(tw)*T))
for nm,ext in (('tw*T',F(F(tw)*T)),('tw*Tp',F(F(tw)*Tp))):
  for fn,f in (('dbl',lambda I: F(I*float(ext)/total)),('cell',lambda I: F(F(I)*F(ext/F(total)))),('mul-div',lambda I: F(F(F(I)*ext)/F(total)))):
    g={float(f(I)) for I in range(total+1)}
    print(nm,fn,sum(1 for x in cent if x in g), len(cent))
