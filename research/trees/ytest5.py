import pickle,sys,math,itertools,numpy as np
sys.path.insert(0,'research'); sys.path.insert(0,'research/trees')
exec(open('research/trees/ytest3.py').read().split("pts=[")[0])
pts=[(x,y,z) for n,i in types for (x,y,z,*_) in i[::401]]
def fma(a,b,c): return f32(float(a)*float(b)+float(c))
def lerp(a,b,t,F): return fma(f32(b-a),t,a) if F else f32(f32(f32(b-a)*t)+a)
def samp(u,v,F):
    s=S; fx=f32(f32(s.w)*u); fy=f32(f32(s.h)*v)
    flx=f32(math.floor(fx)); fly=f32(math.floor(fy)); ix=f32(int(fx)); iy=f32(int(fy))
    cl=lambda a,hi:f32(0) if a<0 else (hi if a>hi else a); wm=f32(s.w-1); hm=f32(s.h-1)
    A=s.vf(int(cl(ix,wm)),int(cl(iy-1,hm))); B=s.vf(int(cl(ix+1,wm)),int(cl(iy-1,hm)))
    C=s.vf(int(cl(ix,wm)),int(cl(iy,hm))); D=s.vf(int(cl(ix+1,wm)),int(cl(iy,hm)))
    tx=f32(fx-flx); ty=f32(fy-fly)
    top=lerp(A,B,tx,F[0]); bot=lerp(C,D,tx,F[0]); return lerp(top,bot,ty,F[1])
def lfp(x,z,F):
    zz=f32(f32(z)/k); u=f32(f32(x)/mx); v=f32(f32(1)-f32(zz/mz))
    l=samp(u,v,F)
    a=f32(l*f32(5500))
    if F[2]==0: return f32(f32(a*fct)-f32(fct*f32(1200)))
    if F[2]==1: return fma(a,fct,-f32(fct*f32(1200)))
    if F[2]==2: return fma(-fct,f32(1200),f32(a*fct))
for F in itertools.product([0,1],[0,1],[0,1,2]):
    print(F, np.mean([lfp(x,z,F)==f32(y) for x,y,z in pts]))
