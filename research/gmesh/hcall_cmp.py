"""Native per-tile height calls (ATLAS3K_GMESH_HCALLS trace) vs BOB's (frida_gheight3 dump), keyed by (x, z, tile)."""
import glob, collections, numpy as np
BIN='Z:/Claude/TerryClone/research/bob_re/frida_out/frida_gheight3_main190_bin/'
dt=np.dtype([('x','<f4'),('z','<f4'),('tx','<i2'),('ty','<i2'),('o','<u2'),('valid','u1'),('flag','u1'),('lf','<f4'),('res','<f4'),('hfo','<f4'),('n','<u4')])
b=np.concatenate([np.fromfile(f,dt) for f in sorted(glob.glob(BIN+'*_calls.bin'))])
nd=np.dtype([('x','<f4'),('z','<f4'),('tx','<i2'),('ty','<i2'),('o','<u2'),('valid','u1'),('pad','u1'),('res','<f4')])
n=np.fromfile('Z:/Claude/TerryClone/output/mesh_parity2/hcalls_10_0.bin',nd)
key=lambda r:(r['x'].tobytes(),r['z'].tobytes(),int(r['tx']),int(r['ty']),int(r['o'])&0xF0)
B={}
for r in b: B[key(r)]=(int(r['valid']), r['res'])
N={}
for r in n: N[key(r)]=(int(r['valid']), r['res'])
both=B.keys()&N.keys()
print('bob calls',len(B),'native',len(N),'both',len(both),'only bob',len(B.keys()-N.keys()),'only native',len(N.keys()-B.keys()))
dv=[k for k in both if B[k][0]!=N[k][0]]; dr=[k for k in both if B[k][0] and N[k][0] and B[k][1]!=N[k][1]]
print('valid differs',len(dv),'value differs',len(dr))
for k in dr[:5]: print(np.frombuffer(k[0],np.float32)[0],np.frombuffer(k[1],np.float32)[0],k[2:],B[k],N[k])
for k in dv[:5]: print('V',np.frombuffer(k[0],np.float32)[0],np.frombuffer(k[1],np.float32)[0],k[2:],B[k],N[k])
ob=list(B.keys()-N.keys())[:5]
for k in ob: print('onlyB',np.frombuffer(k[0],np.float32)[0],np.frombuffer(k[1],np.float32)[0],k[2:],B[k])
