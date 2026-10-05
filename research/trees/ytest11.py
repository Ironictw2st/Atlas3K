import pickle,sys,math,numpy as np
sys.path.insert(0,'research'); sys.path.insert(0,'research/trees')
exec(open('research/trees/ytest3.py').read().split("pts=[")[0])
pts=[(x,y,z) for n,i in types for (x,y,z,*_) in i[::401]]
def samp20(u,v,rowoff):
    s=S; fx=f32(f32(s.w)*u); fy=f32(f32(s.h)*v)
    ix=int(fx); iy=int(fy)
    c=lambda a,hi:0 if a<0 else min(a,hi)
    r0=c(iy+rowoff,s.h-1); r1=c(iy+1+rowoff,s.h-1)
    v00=s.vf(c(ix,s.w-1),r0); v01=s.vf(c(ix+1,s.w-1),r0); v10=s.vf(c(ix,s.w-1),r1); v11=s.vf(c(ix+1,s.w-1),r1)
    tx=f32(fx-f32(math.floor(fx))); ty=f32(fy-f32(math.floor(fy)))
    top=f32(f32(f32(v01-v00)*tx)+v00); bot=f32(f32(f32(v11-v10)*tx)+v10)
    return f32(f32(ty*f32(bot-top))+top)
def H_(l): return f32(f32(f32(l*f32(5500))*fct)-f32(fct*f32(1200)))
for off in (0,-1):
    r=[]
    for x,y,z in pts:
        zz=f32(f32(z)/k); u=f32(f32(x)/mx); v=f32(f32(1)-f32(zz/mz))
        r.append(H_(samp20(u,v,off))==f32(y))
    print(off,np.mean(r))
