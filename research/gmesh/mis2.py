import sys, numpy as np, collections
args=sys.argv[1:]; sys.argv=[sys.argv[0]]
sys.path.insert(0,'.')
import lf_probe as P
F=np.float32
T=F(595.1)/F(1784); Tp=F(F(F(1)/F(2956))*F(F(2956)*T)); cell=F(F(F(2956)*Tp)/F(5912))
P.maxX=F(F(2956)*Tp); P.maxZ=F(F(2267)*Tp); f=F(F(0.0390625)*Tp); d=F(0.001)
def lf(x,z): return F(F(F(P.sample(F(x/P.maxX),F(F(1)-F(z/P.maxZ)))*F(1100))*f)-F(f*F(240)))
key=args[0]; row,col=map(int,key.split('_')[1:])
b=np.fromfile(f'Z:/Claude/TerryClone/output/mesh_parity/gmesh_bob_grids/{key}.bob.bin',np.float32).reshape(370,370)
a=np.fromfile(f'Z:/Claude/TerryClone/output/mesh_parity/gmesh_native_dump2/{key}.y.bin',np.float32).reshape(370,370)
mis=np.argwhere((a!=b)&(a!=-20)&(b!=-20))
cnt=collections.Counter()
for j,i in mis[:400]:
    x=F(F(col*369+i)*cell); z=F(F(row*369+j)*cell)
    c0=lf(x,z); pr=[lf(F(x+d),F(z+d)),lf(F(x-d),F(z+d)),lf(F(x+d),F(z-d)),lf(F(x-d),F(z-d))]
    cnt[('bob=center' if b[j,i]==c0 else 'bob=minprobe' if b[j,i]==min(pr) else 'bob=probe' if b[j,i] in pr else 'bob=other',
         'ours=center' if a[j,i]==c0 else 'ours=minprobe' if a[j,i]==min(pr) else 'ours=other')]+=1
print(key, len(mis), cnt.most_common())
