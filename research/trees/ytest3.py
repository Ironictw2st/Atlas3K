import pickle,sys,math,numpy as np
sys.path.insert(0,'research'); sys.path.insert(0,'research/trees')
import compressed_map as CM
f32=np.float32
W,H,types=pickle.load(open('research/trees/vanilla.pkl','rb'))
raw,fl=CM.decode(r'Z:\Claude\TerryClone\Vanilla\Map\terrain\campaigns\3k_dlc07_main_map\lf_height_map.compressed_map')
print(raw.shape, fl)
INV=f32(1.0/65535)
class CMS:
    def __init__(s,raw,fl): s.raw=raw; s.h,s.w=raw.shape; s.lo=f32(fl[1]); s.hi=f32(fl[4])
    def vf(s,c,r): return f32(f32(f32(f32(s.raw[r,c])*INV)*f32(s.hi-s.lo))+s.lo)
    def sample(s,u,v):
        fx=f32(f32(s.w)*u); fy=f32(f32(s.h)*v)
        flx=f32(math.floor(fx)); fly=f32(math.floor(fy))
        ix=f32(int(fx)); iy=f32(int(fy))
        cl=lambda a,hi:f32(0) if a<0 else (hi if a>hi else a)
        wm=f32(s.w-1); hm=f32(s.h-1)
        A=s.vf(int(cl(ix,wm)),int(cl(iy-1,hm))); B=s.vf(int(cl(ix+1,wm)),int(cl(iy-1,hm)))
        top=f32(f32(f32(B-A)*f32(fx-flx))+A)
        C=s.vf(int(cl(ix,wm)),int(cl(iy,hm))); D=s.vf(int(cl(ix+1,wm)),int(cl(iy,hm)))
        bot=f32(f32(f32(D-C)*f32(fx-flx))+C)
        return f32(f32(f32(bot-top)*f32(fy-fly))+top)
S=CMS(raw,fl)
ts=f32(f32(595.1)/f32(1784)); mx=f32(1784)*ts; mz=f32(1405)*ts; k=f32(1.1547600030899048)
fct=f32(f32(f32(1)/f32(128))*ts)
def lf(x,z):
    zz=f32(f32(z)/k)
    u=f32(f32(x)/mx); v=f32(f32(1)-f32(zz/mz))
    l=S.sample(u,v)
    return f32(f32(f32(l*f32(5500))*fct)-f32(fct*f32(1200)))
pts=[(x,y,z) for n,i in types for (x,y,z,*_) in i[::97]]
d=np.array([float(lf(x,z))-y for x,y,z in pts])
print('exact',np.mean(d==0), np.percentile(np.abs(d),[50,90,99,99.9]))
