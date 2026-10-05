"""Which grid step reproduces BOB's grid-lambda query coordinates (frida_gheight3 dump)? For mismatched Land_10_0 points,
BOB's grid value is the call result at a coordinate 1 ulp off F(I)*cell."""
import numpy as np
exec(open('calls_at.py',encoding='utf-8').read().split("print(len(mis)")[0])
xs={}
for r in b: xs.setdefault((float(r['x']),float(r['z'])),float(r['res']))
allres={}
for r in b: allres.setdefault((float(r['x']),float(r['z'])),set()).add(float(r['res']))
def cands():
    c=cell
    yield 'cell',c
    for k in (1,2,-1,-2): yield f'cell{k:+d}ulp', F(np.nextafter(c, np.inf if k>0 else -np.inf)) if abs(k)==1 else F(np.nextafter(np.nextafter(c, np.inf if k>0 else -np.inf),np.inf if k>0 else -np.inf))
    yield 'double', None
for name,s in cands():
    ok=n=0
    for j,i in mis[:3000]:
        I=int(i); J=3690+int(j)
        if s is None: x=F(I*(float(W)*float(Tp))/(2*W)); z=F(J*(float(W)*float(Tp))/(2*W))
        else: x=F(F(I)*s); z=F(F(J)*s)
        v=allres.get((float(x),float(z)))
        if v is None: continue
        n+=1; ok+= F(bg[j,i]) in {F(t) for t in v}
    print(name, ok, n)
print('--- ext sweep')
ext0=F(F(W)*Tp)
for k in range(-4,5):
    e=ext0
    for _ in range(abs(k)): e=F(np.nextafter(e, np.inf if k>0 else -np.inf))
    s=F(e/F(2*W)); ok=n=miss=0
    for j,i in mis[:3000]:
        x=F(F(int(i))*s); z=F(F(3690+int(j))*s); v=allres.get((float(x),float(z)))
        if v is None: miss+=1; continue
        n+=1; ok+=F(bg[j,i]) in {F(t) for t in v}
    print(k, hex(int(s.view(np.uint32))), ok, n, 'missing', miss)
print('cell', hex(int(cell.view(np.uint32))))
print('--- formula sweep')
D595=float(F(595.1))
forms={'I*f595/3568 dbl': lambda I: F(I*D595/3568),
       'I*(f595/3568) dbl': lambda I: F(I*(D595/3568)),
       'I*Tp/2 dbl': lambda I: F(I*float(Tp)/2),
       'I*T/2 f': lambda I: F(F(I)*F(F(595.1)/F(3568))),
       'I*Tdbl/2': lambda I: F(I*float(F(595.1)/F(1784))/2),
       'I*cell dbl': lambda I: F(I*float(cell))}
for nm,f in forms.items():
    ok=n=miss=0
    for j,i in mis[:3000]:
        x=f(int(i)); z=f(3690+int(j)); v=allres.get((float(x),float(z)))
        if v is None: miss+=1; continue
        n+=1; ok+=F(bg[j,i]) in {F(t) for t in v}
    print(nm, ok, n, 'missing', miss)
print('--- empirical offsets')
import collections
byres=collections.defaultdict(list)
for r in b: byres[float(r['res'])].append((float(r['x']),float(r['z'])))
C=collections.Counter(); ex=[]
for j,i in mis[:3000]:
    I=int(i); J=3690+int(j); x=F(F(I)*cell); z=F(F(J)*cell); dx_=F(I*D595/3568); dz_=F(J*D595/3568)
    hits=[(int(F(a).view(np.int32)-x.view(np.int32)),int(F(c).view(np.int32)-z.view(np.int32))) for a,c in byres.get(float(bg[j,i]),[]) if abs(a-x)<1e-3 and abs(c-z)<1e-3]
    dd=(int(dx_.view(np.int32)-x.view(np.int32)),int(dz_.view(np.int32)-z.view(np.int32)))
    C[(tuple(sorted(set(hits)))[:2], dd)]+=1
for k,v in C.most_common(12): print(v,k)
print('--- z formulas')
pts=[]
for j,i in mis[:3000]:
    I=int(i); J=3690+int(j)
    hs=[(F(a),F(c)) for a,c in byres.get(float(bg[j,i]),[]) if abs(a-F(F(I)*cell))<1e-3 and abs(c-F(F(J)*cell))<1e-3]
    if hs: pts.append((int(i),int(j),hs))
s=cell; s2=F(np.nextafter(cell,np.inf))
zf={'F(J)*s':lambda j:F(F(3690+j)*s),
    'F(j)*s+F(3690)*s':lambda j:F(F(F(j)*s)+F(F(3690)*s)),
    'F(j*s + 3690*s) dbl':lambda j:F(float(F(F(j)*s))+float(F(F(3690)*s))),
    'z0 + j*s, z0=F(10*369*s)':lambda j:F(F(F(3690)*s)+F(F(j)*s)),
    'dbl':lambda j:F((3690+j)*D595/3568),
    'z0dbl+j*s':lambda j:F(F(3690*D595/3568)+F(F(j)*s)),
    'F(j)*s + z0dbl':lambda j:F(F(F(j)*s)+F(3690*D595/3568)),
    '(j+3690)*s2':lambda j:F(F(3690+j)*s2)}
xf={'F(I)*s':lambda i:F(F(i)*s),'dbl':lambda i:F(i*D595/3568),'F(i)*s2':lambda i:F(F(i)*s2)}
for nm,f in zf.items():
    print(nm, sum(any(c==f(j) for a,c in hs) for i,j,hs in pts), len(pts))
for nm,f in xf.items():
    print('x',nm, sum(any(a==f(i) for a,c in hs) for i,j,hs in pts), len(pts))
