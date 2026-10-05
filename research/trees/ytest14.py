import pickle,sys,math,itertools,numpy as np
sys.path.insert(0,'research'); sys.path.insert(0,'research/trees')
exec(open('research/trees/ytest3.py').read().split("pts=[")[0])
pts=[(x,y,z) for n,i in types for (x,y,z,*_) in i[::401]]
Ls=[]
for x,y,z in pts:
    zz=f32(f32(z)/k); u=f32(f32(x)/mx); v=f32(f32(1)-f32(zz/mz)); Ls.append((S.sample(u,v),f32(y)))
def nud(a,n):
    a=f32(a)
    for _ in range(abs(n)): a=np.nextafter(a,f32(np.inf) if n>0 else f32(-np.inf))
    return f32(a)
res=[]
for da in range(-8,9):
  A=nud(5500,da)
  for db in range(-8,9):
    B=nud(1200,db)
    for df in range(-2,3):
      F=nud(fct,df)
      ok=sum(f32(f32(f32(l*A)*F)-f32(F*B))==y for l,y in Ls)
      res.append((ok/len(Ls),da,db,df))
res.sort(reverse=True); print(res[:8])
