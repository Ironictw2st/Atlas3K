"""export_bob_grids by BOB's output file bounding box: (col, row) = bbox min / (cells · cell)."""
import os, sys, json, struct, numpy as np
sys.path.insert(0,'.')
from grid_cmp import *
out=sys.argv[1]; os.makedirs(out, exist_ok=True)
for f in os.listdir(out): os.remove(os.path.join(out,f))
seq=bob_sequence(); h,mg=bob_dumps()
G=os.environ.get('GMESH_BOBFILES','Z:/Claude/TerryClone/output/bob_runs/frida_gmesh_main190_bob_terrain/global_meshes/')
F=np.float32; T=F(595.1)/F(1784); Tp=F(F(F(1)/F(2956))*F(F(2956)*T)); cell=F(F(F(2956)*Tp)/F(5912))
maps=[]; seen={}
for (kind,k,name),d,m in zip(seq,h,mg):
    n=d['n']; cells=n-1
    if name is None: maps.append((kind,k,None,None)); continue
    b=open(G+name+'.rigid_model_v2','rb').read(); bb=struct.unpack_from('<6f',b,0xC0)
    col=int(round(bb[0]/(cells*float(cell)))); row=int(round(bb[2]/(cells*float(cell))))
    key=f'{kind}_{row}_{col}'
    if key in seen: print('dup', key, name, seen[key])
    seen[key]=name
    np.fromfile(BIN+d['file'],np.float32).tofile(os.path.join(out,key+'.bob.bin'))
    (np.fromfile(BIN+m['file'],np.uint32) if 'file' in m else np.zeros(0,np.uint32)).tofile(os.path.join(out,key+'.merged.bin'))
    maps.append((kind,k,name,key))
json.dump(maps, open(os.path.join(out,'mapping.json'),'w'))
print(len(seen),'meshes; no-file merges', sum(1 for x in maps if x[2] is None))
print([x for x in maps[:20]])
