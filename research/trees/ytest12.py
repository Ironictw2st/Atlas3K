import pickle,sys,math,itertools,numpy as np
sys.path.insert(0,'research'); sys.path.insert(0,'research/trees')
exec(open('research/trees/ytest3.py').read().split("pts=[")[0])
pts=[(x,y,z) for n,i in types for (x,y,z,*_) in i[::401]]
rk=f32(f32(1)/k); rmx=f32(f32(1)/mx); rmz=f32(f32(1)/mz)
def H_(l): return f32(f32(f32(l*f32(5500))*fct)-f32(fct*f32(1200)))
for a,b,c in itertools.product([0,1],[0,1],[0,1]):
    r=[]
    for x,y,z in pts:
        zz=f32(f32(z)*rk) if a else f32(f32(z)/k)
        u=f32(f32(x)*rmx) if b else f32(f32(x)/mx)
        v=f32(f32(1)-(f32(zz*rmz) if c else f32(zz/mz)))
        r.append(H_(S.sample(u,v))==f32(y))
    print(a,b,c,np.mean(r))
