import pickle,sys,math,numpy as np
sys.path.insert(0,'research'); sys.path.insert(0,'research/trees')
exec(open('research/trees/ytest3.py').read().split("pts=[")[0])
pts=[(x,y,z) for n,i in types for (x,y,z,*_) in i[::401]]
variants={
 'mul inv':lambda v:f32(f32(v)*INV),
 'div':lambda v:f32(f32(v)/f32(65535)),
 'double div':lambda v:f32(float(v)/65535.0),
}
for nm,fn in variants.items():
    S.vf=lambda c,r,fn=fn: fn(S.raw[r,c])
    print(nm, np.mean([lf(x,z)==f32(y) for x,y,z in pts]))
