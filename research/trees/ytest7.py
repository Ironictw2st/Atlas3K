import pickle,sys,math,numpy as np
sys.path.insert(0,'research'); sys.path.insert(0,'research/trees')
exec(open('research/trees/ytest3.py').read().split("pts=[")[0])
pts=[(x,y,z) for n,i in types for (x,y,z,*_) in i[::401]]
def L(x,z):
    zz=f32(f32(z)/k); u=f32(f32(x)/mx); v=f32(f32(1)-f32(zz/mz)); return S.sample(u,v)
F={
 'base':lambda l:f32(f32(f32(l*f32(5500))*fct)-f32(fct*f32(1200))),
 '(l*5500-1200)*f':lambda l:f32(f32(f32(l*f32(5500))-f32(1200))*fct),
 'l*(5500f)-1200f':lambda l:f32(f32(l*f32(f32(5500)*fct))-f32(f32(1200)*fct)),
 'fma(l*5500,f,-1200f)':lambda l:f32(float(f32(l*f32(5500)))*float(fct)-float(f32(fct*f32(1200)))),
 'double all':lambda l:f32((float(l)*5500*float(fct))-float(fct)*1200),
 'split':lambda l:(lambda h:f32(f32(h-h)+h))(f32(f32(f32(l*f32(5500))*fct)-f32(fct*f32(1200)))),
}
for nm,fn in F.items(): print(nm, np.mean([fn(L(x,z))==f32(y) for x,y,z in pts]))
