import sys, numpy as np
sys.path.insert(0,'.')
ARGS=sys.argv[1:]; sys.argv=[sys.argv[0]]
import gheight_cmp as G
F=np.float32
cell=F(F(F(2956)*F(F(F(1)/F(2956))*F(F(2956)*(F(595.1)/F(1784)))))/F(5912))
col,row,i,j=[int(a) for a in ARGS[:4]]
x=F(F(col*369+i)*cell); z=F(F(row*369+j)*cell)
c=G.calls
m=(np.abs(c['x']-x)<0.0011)&(np.abs(c['z']-z)<0.0011)
print('cell',cell,'x',x,'z',z, m.sum())
for r in c[m][:int(ARGS[4]) if len(ARGS)>4 else 12]: print(float(r["x"]), float(r["z"]), r["tx"], r["ty"], hex(r["o"]), r["valid"], r["lf"], r["n"])
cc=c[m]
import struct
for r in cc[:12]: print(struct.pack('<f',r['x']).hex(), struct.pack('<f',r['z']).hex(), r['x'], r['z'], r['lf'])
print('ours', struct.pack('<f',x).hex(), struct.pack('<f',z).hex())
