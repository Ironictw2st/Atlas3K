import sys, numpy as np, collections, os
args=sys.argv[1:]; sys.argv=[sys.argv[0]]
sys.path.insert(0,'.'); sys.path.insert(0, r"Z:\Claude\TerryClone\research\derived_maps")
import tiles_lib as TL
F=np.float32
paths, cl, fl, ints, rec = TL.read_tile_list(r"Z:\Claude\TerryClone\output\mesh_parity\gmesh_pack\terrain\campaigns\3k_190e_expanded_map\tile_list.bin")
T=F(595.1)/F(1784); Tp=F(F(F(1)/F(2956))*F(F(2956)*T)); cell=F(F(F(2956)*Tp)/F(5912))
key=args[0]; row,col=map(int,key.split('_')[1:])
b=np.fromfile(f'Z:/Claude/TerryClone/output/mesh_parity/gmesh_bob_grids/{key}.bob.bin',np.float32).reshape(370,370)
a=np.fromfile(f'Z:/Claude/TerryClone/output/mesh_parity/gmesh_native_dump2/{key}.y.bin',np.float32).reshape(370,370)
mis=np.argwhere((a!=b)&(a!=-20)&(b!=-20))
cnt=collections.Counter()
A=r"C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\assembly_kit_190E\working_data"
for j,i in mis[::max(1,len(mis)//300)]:
    tx=float((col*369+i)*cell/Tp); ty=float((row*369+j)*cell/Tp)
    ps=[]
    for r in rec:
        if r['x']<=tx<=r['x']+16 and r['y']<=ty<=r['y']+16:
            p=paths[r['path']]
            if True:
                d=os.path.join(A,p.rstrip(chr(92))); fs=os.listdir(d) if os.path.isdir(d) else []
                ps.append((p.split(chr(92))[-2], 'data' if 'hf_height_map.data' in fs else 'cm' if 'hf_height_map.compressed_map' in fs else 'none'))
    cnt[tuple(ps[:2])]+=1
print(key, cnt.most_common(8))
