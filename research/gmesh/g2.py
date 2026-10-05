"""Race-free get_height_worker dump (frida_gheight2 in frida_gmesh_combo.js): lf check and hf = result - lf stats."""
import glob, sys, numpy as np
sys.argv=[sys.argv[0]]
sys.path.insert(0,'.')
import lf_probe as P
F=np.float32
BIN='Z:/Claude/TerryClone/research/bob_re/frida_out/frida_gcombo_main190_bin/'
dt=np.dtype([('x','<f4'),('z','<f4'),('tx','<i2'),('ty','<i2'),('o','<u2'),('valid','u1'),('flag','u1'),('lf','<f4'),('res','<f4'),('hfo','<f4'),('n','<u4')])
c=np.concatenate([np.fromfile(f,dt) for f in sorted(glob.glob(BIN+'*_calls.bin'))])
print(len(c),'calls; valid',c['valid'].mean(), 'flag values', np.unique(c['flag']))
v=c[c['valid']==1]
hf=(v['res']-v['lf']); print('valid with hf==0', np.mean(hf==0), 'nonzero hf', np.mean(hf!=0))
T=F(595.1)/F(1784); Tp=F(F(F(1)/F(2956))*F(F(2956)*T)); P.maxX=F(F(2956)*Tp); P.maxZ=F(F(2267)*Tp); f=F(F(0.0390625)*Tp)
rng=np.random.default_rng(3); s=v[rng.choice(len(v),3000,replace=False)]
ok=sum(F(F(F(P.sample(F(r['x']/P.maxX),F(F(1)-F(r['z']/P.maxZ)))*F(1100))*f)-F(f*F(240)))==r['lf'] for r in s)
print('lf exact', ok, len(s))
np.save('Z:/Claude/TerryClone/output/mesh_parity/gcalls.npy', c)
