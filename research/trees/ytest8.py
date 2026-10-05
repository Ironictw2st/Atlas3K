import pickle,sys,math,itertools,numpy as np
sys.path.insert(0,'research'); sys.path.insert(0,'research/trees')
exec(open('research/trees/ytest3.py').read().split("pts=[")[0])
pts=[(x,y,z) for n,i in types for (x,y,z,*_) in i[::401]]
def L1(a,b,t): return f32(f32(f32(b-a)*t)+a)
def L2(a,b,t): return f32(f32(a*f32(f32(1)-t))+f32(b*t))
def L3(a,b,t): return f32(float(a)+(float(b)-float(a))*float(t))
def corners(u,v,mode):
    s=S; fx=f32(f32(s.w)*u); fy=f32(f32(s.h)*v)
    if mode==0:   # 18039eea0: rows iy-1, iy
        ix=int(fx); iy=int(fy); r0,r1=iy-1,iy; tx=f32(fx-f32(math.floor(fx))); ty=f32(fy-f32(math.floor(fy)))
    else:         # 1803a1e30: row from (v-1/H)*H
        ix=int(fx); r0=int(f32(f32(v-f32(f32(1)/f32(s.h)))*f32(s.h))); r1=int(fy); tx=f32(fx-f32(math.floor(fx))); ty=f32(fy-f32(math.floor(fy)))
    c=lambda a,hi:0 if a<0 else min(a,hi)
    A=s.vf(c(ix,s.w-1),c(r0,s.h-1)); B=s.vf(c(ix+1,s.w-1),c(r0,s.h-1)); C=s.vf(c(ix,s.w-1),c(r1,s.h-1)); D=s.vf(c(ix+1,s.w-1),c(r1,s.h-1))
    return A,B,C,D,tx,ty
def H_(l): return f32(f32(f32(l*f32(5500))*fct)-f32(fct*f32(1200)))
for mode in (0,1):
  for nm,Lf in (('L1',L1),('L2',L2),('L3',L3)):
    for vfirst in (0,1):
        ok=0
        for x,y,z in pts:
            zz=f32(f32(z)/k); u=f32(f32(x)/mx); v=f32(f32(1)-f32(zz/mz))
            A,B,C,D,tx,ty=corners(u,v,mode)
            l = Lf(Lf(A,B,tx),Lf(C,D,tx),ty) if not vfirst else Lf(Lf(A,C,ty),Lf(B,D,ty),tx)
            ok+= H_(l)==f32(y)
        print(mode,nm,vfirst,ok/len(pts))
