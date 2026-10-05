import sys, numpy as np, struct
args=sys.argv[1:]; sys.argv=[sys.argv[0]]
sys.path.insert(0,'.')
import lf_probe as P
F=np.float32
T=F(595.1)/F(1784); Tp=F(F(F(1)/F(2956))*F(F(2956)*T)); cell=F(F(F(2956)*Tp)/F(5912))
P.maxX=F(F(2956)*Tp); P.maxZ=F(F(2267)*Tp); f=F(F(0.0390625)*Tp)
i,j=int(args[0]),int(args[1])
x=F(F(i)*cell); z=F(F(j)*cell)
for dx,dz in ((0,0),(1,1),(-1,1),(1,-1),(-1,-1)):
    xx=F(x+F(dx*0.001)) if dx>0 else (F(x-F(0.001)) if dx<0 else x)
    zz=F(z+F(dz*0.001)) if dz>0 else (F(z-F(0.001)) if dz<0 else z)
    u=F(xx/P.maxX); v=F(F(1)-F(zz/P.maxZ))
    l=P.sample(u,v); print(dx,dz,float(F(F(F(l*F(1100))*f)-F(f*F(240)))), 'fx', float(F(F(P.W)*u)), 'fy', float(F(F(P.H)*v)))
