"""Fit BOB's grid-lambda query coordinate on ALL points of Land_10_0 (mesh k=170, frida_gheight3 dump): per point, the
call coordinates within 3 ulps whose result equals BOB's grid value; score coordinate formulas against them."""
import collections, numpy as np
exec(open('calls_at.py',encoding='utf-8').read().split("print(len(mis)")[0])
byres=collections.defaultdict(list)
for r in b: byres[float(r['res'])].append((F(r['x']),F(r['z'])))
s=cell; D595=float(F(595.1))
def ul(a,c): return int(F(a).view(np.int32))-int(F(c).view(np.int32))
pts=[]
for j in range(370):
    for i in range(370):
        v=float(bg[j,i])
        if v==-20: continue
        x0=F(F(i)*s); z0=F(F(3690+j)*s)
        hs={(ul(a,x0),ul(c,z0)) for a,c in byres.get(v,[]) if abs(ul(a,x0))<=3 and abs(ul(c,z0))<=3}
        if hs: pts.append((i,j,hs))
print(len(pts),'points with hits')
print(collections.Counter(tuple(sorted(h)) for i,j,h in pts).most_common(8))
forms={'F(I)*s':(lambda i:F(F(i)*s), lambda j:F(F(3690+j)*s)),
       'split':(lambda i:F(F(i)*s), lambda j:F(F(F(j)*s)+F(F(3690)*s))),
       'dbl':(lambda i:F(i*D595/3568), lambda j:F((3690+j)*D595/3568)),
       'dbl Tp':(lambda i:F(i*float(Tp)/2), lambda j:F((3690+j)*float(Tp)/2))}
for nm,(fx,fz) in forms.items():
    ok=sum((ul(fx(i),F(F(i)*s)),ul(fz(j),F(F(3690+j)*s))) in h for i,j,h in pts)
    okz=sum(any(d[1]==ul(fz(j),F(F(3690+j)*s)) for d in h) for i,j,h in pts)
    print(nm, ok, 'z only', okz, len(pts))
