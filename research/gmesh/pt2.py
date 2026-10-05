import sys, numpy as np
sys.argv=[sys.argv[0]]
sys.path.insert(0,'.')
import lf_probe as P, lf_fit as LF
F=np.float32
Tp=F(F(F(1)/F(2956))*P.maxX); f=F(F(0.0390625)*Tp)
for x,z in ((25.685368,12.842684),(25.686367,12.843684),(25.684368,12.841683)):
    x=F(x); z=F(z); l=LF.l_a(x,z); print(x,z,'lf',F(F(F(l*F(1100))*f)-F(f*F(240))), 'l',l)
