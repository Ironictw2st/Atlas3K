import pickle,sys,numpy as np
sys.path.insert(0,'research/derived_maps'); sys.path.insert(0,'research/trees')
from height_exact import LfSampler, f32
W,H,types=pickle.load(open('research/trees/vanilla.pkl','rb'))
raw=np.frombuffer(open(r'Z:\Claude\TerryClone\Vanilla\Map\terrain\campaigns\3k_dlc07_main_map\lf_height_map.dds','rb').read(),'<u2',offset=128,count=7136*5620).reshape(5620,7136)
pts=[(x,y,z) for n,i in types for (x,y,z,*_) in i[::97]]
k=f32(1.1547600030899048)
def ev(S,zf):
    d=np.array([float(S.height(f32(x),zf(z)))-y for x,y,z in pts]); return round(float(np.mean(d==0)),4)
ts=f32(f32(595.1)/f32(1784))
cands={'f32 1784*ts':(f32(1784)*ts,f32(1405)*ts),'double':(f32(1784*595.1/1784),f32(1405*595.1/1784)),
 'W,H/k':(f32(W),f32(f32(H)/k)),'W,Hd/k':(f32(W),f32(H/1.1547600030899048))}
for nm,(mx,mz) in cands.items():
    for tsn,tsv in [('ts',ts),('tsd',f32(595.1/1784))]:
        S=LfSampler(raw,mx,mz,tile=tsv)
        print(nm,tsn,ev(S,lambda z:f32(f32(z)/k)), ev(S,lambda z:f32(f32(z)*f32(f32(1)/k))))
