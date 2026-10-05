import numpy as np, compare_global_meshes as C, height_exact as HX, merger_proto as M
f32=np.float32
raw=np.frombuffer(open(M.V+r"\lf_height_map.dds",'rb').read(),'<u2',offset=128,count=7136*5620).reshape(5620,7136)
tile=f32(595.1)/f32(1784)
s=HX.LfSampler(raw,f32(595.1),f32(f32(1405)*tile),tile=tile)
for n in (0,20,40,60,80,100,120,140,160):
    res=[]
    for root in (C.VAN,C.OURS):
        v,idx,bb,surf=C.read(root+rf"\land_mesh_{n}.rigid_model_v2")
        cov,h=C.coverage(v,idx,surf,bb)
        js,is_=np.nonzero(cov)
        sel=np.arange(len(js))[::7]
        lf=np.array([s.height(f32(bb[0]+(is_[k]+0.5)*C.CELL),f32(bb[2]+(js[k]+0.5)*C.CELL)) for k in sel])
        d=np.abs(h[js[sel],is_[sel]]-lf)
        res.append((np.percentile(d,99),d.max()))
    print(f'mesh {n}: |surface - lf| p99/max  vanilla {res[0][0]:.3f}/{res[0][1]:.3f}   ours {res[1][0]:.3f}/{res[1][1]:.3f}')
