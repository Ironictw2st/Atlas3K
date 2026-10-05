import sys, json; sys.path[:0]=['.','../guandu','..']
from hexgrid import neighbour
import numpy as np, town_fix as T
_,_,w,h,_,f,names=T.load(sys.argv[1] if len(sys.argv)>1 and sys.argv[1].endswith('.hex') else 'hex/map.hex')
spr=f['sprawl']>0
stand=((f['terr']==0)|((f['terr']>1)&(spr|(f['bridge']>0)))) & ((f['river']==0)|spr) & (f['imp']==0) & (f['slot']<0)
def pinch(c,r):
    if not stand[r,c]: return None
    s=[]
    for d in range(6):
        nc,nr=neighbour(c,r,d)
        s.append(bool(0<=nc<w and 0<=nr<h and stand[nr,nc]))
    for d in range(6):
        a=[s[(d+i)%6] for i in range(6)]
        if not a[0] and a[1] and not a[2]: return '010'
        if not a[0] and a[1] and a[2] and not a[3] and a[4] and a[5]: return 'hourglass'
        if not any(a): return 'isolated'
    return None
def town_pinches(k, depth=2):
    i=names.index(k); F=T.footprint(f,i); area=set(F); ring=set(F)
    for _ in range(depth): ring=T.ring(area,w,h); area|=ring
    out=[(p,pinch(*p)) for p in area]
    return [(p,t,'F' if p in F else '') for p,t in out if t]
if __name__=='__main__':
    keys=[a for a in sys.argv[1:] if not a.endswith('.hex')]
    for k in keys: print(k, town_pinches(k))

def all_towns():
    ks=sorted({int(x) for x in np.unique(f['region'][f['slot']==0])})
    return {names[k]:town_pinches(names[k]) for k in ks}
