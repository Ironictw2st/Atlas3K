import sys, numpy as np
sys.path.insert(0,'.')
import gheight_cmp as G, lf_probe as P, lf_fit as LF
F=np.float32
Tp=F(F(F(1)/F(P.W//4))*P.maxX)
f=F(F(0.0390625)*Tp)
import numpy.random as R; ok_idx=np.where(~np.isnan(G.calls["lf"]))[0]; sub=G.calls[R.default_rng(2).choice(ok_idx,4000,replace=False)]
for nm,lfun in (('a',LF.l_a),('c',LF.l_c)):
    ok=0
    for r in sub:
        l=lfun(F(r['x']),F(r['z'])); ok+= F(F(F(l*F(1100))*f)-F(f*F(240)))==F(r['lf'])
    print(nm, ok, len(sub))
import compressed_map as C, os
cache=P.INP+'lfsea.npy'
if not os.path.exists(cache):
    r,hdr=C.decode(P.INP+'lf_sea_height_map.compressed_map'); np.save(cache,r); np.save(P.INP+'lfsea_hdr.npy',np.array(hdr,np.float32))
S=np.load(cache); sh=np.load(P.INP+'lfsea_hdr.npy'); print('sea map', S.shape, sh)
bad=[r for r in sub if F(F(F(LF.l_a(F(r['x']),F(r['z']))*F(1100))*f)-F(f*F(240)))!=F(r['lf'])]
L0=P.L; P.L=S; P.lo,P.hi=F(sh[1]),F(sh[4]); P.H,P.W=S.shape
ok=sum(F(F(F(LF.l_a(F(r['x']),F(r['z']))*F(1100))*f)-F(f*F(240)))==F(r['lf']) for r in bad)
print('mismatches', len(bad), 'match with sea lf', ok)
print(bad[:3])
for r in bad[:6]:
    x,z=F(r['x']),F(r['z'])
    P.L=S; P.lo,P.hi=F(sh[1]),F(sh[4]); P.H,P.W=S.shape; ls=LF.l_a(x,z)
    P.L=L0; P.lo,P.hi=F(0),F(1); P.H,P.W=L0.shape; ll=LF.l_a(x,z)
    print(float(x),float(z),'bob',float(r['lf']),'land',float(F(F(F(ll*F(1100))*f)-F(f*F(240)))),'sea',float(F(F(F(ls*F(1100))*f)-F(f*F(240)))), 'o', hex(r['o']))
