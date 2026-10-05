"""Character (LOCOMOTABLE) world positions in an unpacked startpos -> hexes, near given points.
usage: sp_chars.py <startpos.pkl> <map_data.esf> W x,y[,r] ..."""
import sys, math; sys.path.insert(0,'Z:/Claude/TerryClone/research/hlp_spd')
import pickle
from esf_tree import read, node, find
root,s8,s16=pickle.load(open(sys.argv[1],'rb'))
b,names,_,_=read(sys.argv[2]); md,_=node(b,16,names,True)
th=find(md,'CAMPAIGN_THEATRE')[0]; v=[c[2] for c in th[3][0] if c[0]=='VAL']
(mnx,mny),(mxx,mxy)=v[0],v[1]
W=int(sys.argv[3]); s=0.6666667/(W-1)*(mxx-mnx); half=s*0.8660254; row=2*half; col=1.5*s
pos=[]
for lc in find(root,'LOCOMOTABLE'):
    c=[x for x in lc[3][0] if x[0]=='VAL' and x[1]==0x0c]
    if not c: continue
    wx,wy=c[0][2]
    hx=round((wx-mnx)/col); hy=round((wy-mny-(half if hx&1 else 0))/row)
    pos.append((hx,hy,wx,wy))
print(len(pos),"characters")
for q in sys.argv[4:]:
    t=list(map(int,q.split(','))); r=t[2] if len(t)>2 else 12
    near=[p for p in pos if abs(p[0]-t[0])<=r and abs(p[1]-t[1])<=r]
    print(q, near)
