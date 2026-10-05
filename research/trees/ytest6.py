import pickle,sys,math,numpy as np
sys.path.insert(0,'research'); sys.path.insert(0,'research/trees')
exec(open('research/trees/ytest3.py').read().split("pts=[")[0])
pts=[(x,y,z) for n,i in types for (x,y,z,*_) in i[::401]]
def parts(x,z):
    zz=f32(f32(z)/k); u=f32(f32(x)/mx); v=f32(f32(1)-f32(zz/mz)); l=S.sample(u,v)
    return u,v,l
ul=lambda a,b: int(np.int32(np.float32(a).view(np.int32))-np.int32(np.float32(b).view(np.int32)))
c=0
for x,y,z in pts:
    u,v,l=parts(x,z); h=lf(x,z)
    if h!=f32(y):
        lt=(f32(y)+f32(fct*f32(1200)))/fct/f32(5500)
        print(f"x={x:.4f} z={z:.4f} y={y:.7g} ours={float(h):.7g} ulps={ul(h,y)} l={float(l):.9g} l_true~{float(lt):.9g} fx={float(f32(7136)*u):.4f} fy={float(f32(5620)*v):.4f}")
        c+=1
        if c>25: break
