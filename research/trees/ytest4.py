import pickle,sys,math,numpy as np
sys.path.insert(0,'research'); sys.path.insert(0,'research/trees')
exec(open('research/trees/ytest3.py').read().split("pts=[")[0])
pts=[(x,y,z) for n,i in types for (x,y,z,*_) in i[::401]]
def lfp(x,z,mx,mz,fct):
    zz=f32(f32(z)/k); u=f32(f32(x)/mx); v=f32(f32(1)-f32(zz/mz))
    l=S.sample(u,v); return f32(f32(f32(l*f32(5500))*fct)-f32(fct*f32(1200)))
def score(mx,mz,fct): return np.mean([lfp(x,z,mx,mz,fct)==f32(y) for x,y,z in pts])
base=(mx,mz,fct); print('base',score(*base), mx, mz, fct)
best=[]
for dxu in range(-6,7):
    m1=np.nextafter(mx,np.float32(1e9) if dxu>0 else np.float32(0)) if dxu else mx
    a=mx
    for _ in range(abs(dxu)): a=np.nextafter(a,f32(1e9) if dxu>0 else f32(0))
    for dzu in range(-6,7):
        b=mz
        for _ in range(abs(dzu)): b=np.nextafter(b,f32(1e9) if dzu>0 else f32(0))
        best.append((score(a,b,fct),dxu,dzu))
best.sort(reverse=True); print(best[:5])
