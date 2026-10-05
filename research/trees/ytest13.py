import pickle,sys,math,itertools,numpy as np
from collections import Counter
sys.path.insert(0,'research'); sys.path.insert(0,'research/trees')
exec(open('research/trees/ytest3.py').read().split("pts=[")[0])
pts=[(x,y,z) for n,i in types for (x,y,z,*_) in i[::401]]
def H_(l): return f32(f32(f32(l*f32(5500))*fct)-f32(fct*f32(1200)))
def nud(a,n):
    for _ in range(abs(n)): a=np.nextafter(a,f32(np.inf) if n>0 else f32(-np.inf))
    return f32(a)
fix=Counter(); miss=0
for x,y,z in pts:
    zz=f32(f32(z)/k); u=f32(f32(x)/mx); v=f32(f32(1)-f32(zz/mz))
    if H_(S.sample(u,v))==f32(y): continue
    miss+=1
    for what in ('zz','u','v'):
        for n in (-2,-1,1,2):
            zz2=nud(zz,n) if what=='zz' else zz
            u2=nud(u,n) if what=='u' else u
            v2=nud(v,n) if what=='v' else (f32(f32(1)-f32(zz2/mz)) if what=='zz' else v)
            if H_(S.sample(u2,v2))==f32(y): fix[(what,n)]+=1
print(miss, fix.most_common())
