import pickle,sys,numpy as np
sys.path.insert(0,'research/derived_maps'); sys.path.insert(0,'research/trees')
from height_exact import LfSampler, f32
W,H,types=pickle.load(open('research/trees/vanilla.pkl','rb'))
p=r'Z:\Claude\TerryClone\Vanilla\Map\terrain\campaigns\3k_dlc07_main_map\lf_height_map.dds'
raw=np.frombuffer(open(p,'rb').read(),'<u2',offset=128,count=7136*5620).reshape(5620,7136)
pts=[(x,y,z) for n,i in types for (x,y,z,*_) in i[::97]]
def ev(S,tx=lambda x,z:(x,z)):
    d=np.array([float(S.height(*tx(x,z)))-y for x,y,z in pts])
    return round(np.mean(d==0),4), np.round(np.percentile(np.abs(d),[25,50,90]),4), round(float(np.median(d)),4)
print('base',ev(LfSampler(raw,f32(W),f32(H))))
print('z*k',ev(LfSampler(raw,f32(W),f32(H)),lambda x,z:(x,z*1.15476)))
print('z/k',ev(LfSampler(raw,f32(W),f32(H)),lambda x,z:(x,z/1.15476)))
print('maxz/k',ev(LfSampler(raw,f32(W),f32(H/1.15476)),lambda x,z:(x,z/1.15476)))
ts=f32(f32(595.1)/f32(1784))
S2=LfSampler(raw,f32(1784)*ts,f32(1405)*ts)
k=f32(1.1547600030899048)
print('tile space',ev(S2,lambda x,z:(f32(x),f32(f32(z)/k))))
d=np.array([float(S2.height(f32(x),f32(f32(z)/k)))-y for x,y,z in pts]); ys=np.array([p[1] for p in pts])
nz=d!=0
print('nonzero',nz.mean(), np.percentile(np.abs(d[nz]),[10,50,90,99]))
rel=np.abs(d[nz])/np.maximum(np.abs(ys[nz]),1e-6)
print('rel',np.percentile(rel,[10,50,90]))
