"""Re-derive BOB's per-point selection from its own call dump on mismatched Land_10_0 points."""
import sys, collections, numpy as np
exec(open('order_mismatch.py',encoding='utf-8').read().split("mis=np.argwhere")[0])
import glob
BIN='Z:/Claude/TerryClone/research/bob_re/frida_out/frida_gheight3_main190_bin/'
dt=np.dtype([('x','<f4'),('z','<f4'),('tx','<i2'),('ty','<i2'),('o','<u2'),('valid','u1'),('flag','u1'),('lf','<f4'),('res','<f4'),('hfo','<f4'),('n','<u4')])
b=np.concatenate([np.fromfile(f,dt) for f in sorted(glob.glob(BIN+'*_calls.bin'))])
V={}
for r in b: V[(float(r['x']),float(r['z']),int(r['tx']),int(r['ty']),int(r['o'])&0xF0)]=(int(r['valid']),float(r['res']))
p=F(0.001)
def tilekey(r): return (int(rec[r]['x']),int(rec[r]['y']),int(rec[r]['orient'])&0xF0)
mis=np.argwhere((bg!=ng)&(bg!=-20)&(ng!=-20))
cnt=collections.Counter(); ex=[]
for j,i in mis[:4000]:
    x=F(F(int(i))*cell); z=F(F(3690+int(j))*cell); s=seqs.get((float(x),float(z)))
    if not s or -1 in s: cnt['skip']+=1; continue
    res=None
    for r in s:
        tk=tilekey(r)
        c=V.get((float(x),float(z))+tk)
        pr=[V.get((float(F(x+dx)),float(F(z+dz)))+tk) for dx,dz in ((p,p),(-p,p),(p,-p),(-p,-p))]
        if c and c[0]: res=('centre',c[1],r); break
        vals=[q[1] for q in pr if q and q[0]]
        if vals: res=('probe',min(vals),r); break
    if res is None: cnt['none']+=1; continue
    bob=float(bg[j,i]); nat=float(ng[j,i])
    cnt[(res[0], 'sim==bob' if F(res[1])==F(bob) else ('sim==native' if F(res[1])==F(nat) else 'neither'))]+=1
    if len(ex)<6 and F(res[1])!=F(bob): ex.append((float(x),float(z),res,bob,nat))
print(cnt); print(*ex,sep='\n')
