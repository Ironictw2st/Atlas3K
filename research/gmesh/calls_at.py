"""BOB's raw height-query calls (frida_gheight3 dump) around mismatched Land_10_0 grid points: every call at the point and
its ±0.001 probes, in call order, vs BOB's grid value and the native one."""
import glob, numpy as np
F=np.float32
BIN='Z:/Claude/TerryClone/research/bob_re/frida_out/frida_gheight3_main190_bin/'
dt=np.dtype([('x','<f4'),('z','<f4'),('tx','<i2'),('ty','<i2'),('o','<u2'),('valid','u1'),('flag','u1'),('lf','<f4'),('res','<f4'),('hfo','<f4'),('n','<u4')])
b=np.concatenate([np.fromfile(f,dt) for f in sorted(glob.glob(BIN+'*_calls.bin'))]); b=b[np.argsort(b['n'],kind='stable')]
bg=np.fromfile('Z:/Claude/TerryClone/output/mesh_parity/gmesh_bob_grids/Land_10_0.bob.bin',F).reshape(370,370)
ng=np.fromfile('Z:/Claude/TerryClone/output/mesh_parity2/dump_trace/Land_10_0.y.bin',F).reshape(370,370)
T=F(595.1)/F(1784); W=2956; Tp=F(F(F(1)/F(W))*F(F(W)*T)); cell=F(F(F(W)*Tp)/F(2*W))
mis=np.argwhere((bg!=ng)&(bg!=-20)&(ng!=-20))
print(len(mis),'mismatched')
for j,i in mis[::max(1,len(mis)//5)][:5]:
    x=F(F(int(i))*cell); z=F(F(3690+int(j))*cell)
    m=(np.abs(b['x']-x)<0.0015)&(np.abs(b['z']-z)<0.0015)
    print(f'point ({x},{z}) bob {bg[j,i]:.9f} native {ng[j,i]:.9f}')
    for r in b[m][:24]: print('  ',f"{r['x']-x:+.4f} {r['z']-z:+.4f}",r['tx'],r['ty'],hex(r['o']),r['valid'],r['flag'],f"lf {r['lf']:.9f} res {r['res']:.9f} hfo {r['hfo']:.9f} n {r['n']}")
print('--- exact coords')
for j,i in mis[::max(1,len(mis)//5)][:5]:
    x=F(F(int(i))*cell); z=F(F(3690+int(j))*cell)
    m=(b['x']==x)|(np.abs(b['x']-x)<1e-4); m&=(np.abs(b['z']-z)<1e-4)
    u=sorted({(float(r['x']),float(r['z']),float(r['res'])) for r in b[m]})
    print('grid',i,3690+j,repr(float(x)),repr(float(z)),'bob',bg[j,i]); [print('   ',t, 'dx ulps',int(np.float32(t[0]).view(np.int32)-x.view(np.int32)),'dz ulps',int(np.float32(t[1]).view(np.int32)-z.view(np.int32))) for t in u]
