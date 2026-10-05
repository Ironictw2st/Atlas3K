import struct, numpy as np
F=np.float32
G='Z:/Claude/TerryClone/output/bob_runs/frida_gmesh_main190_bob_terrain/global_meshes/'
for name in ('land_mesh_0','land_mesh_100'):
    b=open(G+name+'.rigid_model_v2','rb').read()
    vo,vc=struct.unpack_from('<II',b,0xB0); V=np.frombuffer(b[0xA8+vo:0xA8+vo+vc*16],np.float32).reshape(-1,4)
    T=F(595.1)/F(1784); Tp=F(F(F(1)/F(2956))*F(F(2956)*T))
    for nm,cell in (('Tp',F(F(F(2956)*Tp)/F(5912))),('T',F(F(F(2956)*T)/F(5912)))):
        g={float(F(F(I)*cell)) for I in range(5913)}
        gx=np.mean([float(x) in g for x in V[:,0]]); gz=np.mean([float(z) in g for z in V[:,2]])
        print(name,nm,'x on grid',gx,'z on grid',gz, 'w', np.unique(V[:,3])[:3])
b=open(G+'land_mesh_0.rigid_model_v2','rb').read()
vo,vc=struct.unpack_from('<II',b,0xB0); V=np.frombuffer(b[0xA8+vo:0xA8+vo+vc*16],np.float32).reshape(-1,4)
cell=F(F(F(2956)*Tp)/F(5912)); g={float(F(F(I)*cell)):I for I in range(5913)}
off=[x for x in V[:,0] if float(x) not in g][:10]
for x in off:
    I=int(round(float(x)/float(cell))); gx=F(F(I)*cell)
    print(float(x), I, float(gx), int(np.array([x],F).view(np.int32)[0])-int(np.array([gx],F).view(np.int32)[0]))
print('vc',vc)
import collections
for name in ('land_mesh_0','land_mesh_100','land_mesh_50'):
    b=open(G+name+'.rigid_model_v2','rb').read()
    vo,vc=struct.unpack_from('<II',b,0xB0); V=np.frombuffer(b[0xA8+vo:0xA8+vo+vc*16],np.float32).reshape(-1,4)
    c=collections.Counter(); tot=collections.Counter()
    for x in V[:,0]:
        I=int(round(float(x)/float(cell))); tot[I%369==0]+=1
        if float(x) not in g: c[(I%369==0, int(np.array([x],F).view(np.int32)[0])-int(np.array([F(F(I)*cell)],F).view(np.int32)[0]))]+=1
    print(name, dict(c), dict(tot))
ext=F(F(2956)*Tp)
forms={'cell':lambda I:F(F(I)*cell),'muldiv':lambda I:F(F(F(I)*ext)/F(5912)),'dbl':lambda I:F(I*float(ext)/5912),'dbl2':lambda I:F(I*(float(ext)/5912))}
for name in ('land_mesh_0','land_mesh_100','land_mesh_50'):
    b=open(G+name+'.rigid_model_v2','rb').read()
    vo,vc=struct.unpack_from('<II',b,0xB0); V=np.frombuffer(b[0xA8+vo:0xA8+vo+vc*16],np.float32).reshape(-1,4)
    for fn,f in forms.items():
        ok=np.mean([F(x)==f(int(round(float(x)/float(cell)))) for x in V[:,0]])
        print(name, fn, ok)
