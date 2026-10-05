"""Vanilla trees.campaign_tree_list -> per-hex colour PNG -> regenerated list (BOB's CampaignTreeGenerator)."""
import pickle,sys,struct,numpy as np
sys.path.insert(0,'research/trees')
from rng import R,f32
from camap import ca_map_order
from PIL import Image
DB=r'Z:\Claude\VariantMeshError\game_Db\db'
def tsv(p): return [l.rstrip('\n').split('\t') for l in open(p,encoding='utf-8')][2:]
ids={r[0]:int(r[2],16) for r in tsv(DB+r'\campaign_tree_ids_tables\data__.tsv')}
seas={r[0]:int(r[4]) for r in tsv(DB+r'\seasons_tables\data__.tsv')}
bits={}
for r in tsv(DB+r'\campaign_tree_variants_tables\data__.tsv'):
    if r[2]=='' : continue
    bits[r[0]]=bits.get(r[0],0)|((1<<seas[r[1]]) if r[1] else 0x8000)
def season_list(b): return [i for i in range(15) if b>>i&1]+([0xFFFFFFFF] if b&0x8000 else [])
groups={}
for k in sorted(ids): groups.setdefault(ids[k],[]).append(k)

W,H,types=pickle.load(open('research/trees/vanilla.pkl','rb'))
n=892; s=(f32(0.6666666865348816)/(f32(n)-f32(1)))*f32(W); half=s*f32(0.8660253882408142); dz=half+half; dx=s*f32(1.5)
rows=int(np.floor(H/dz))+1
# --- reverse: list -> hex colour image (row 0 = south) + vanilla heights per hex
img=np.zeros((rows+1,n),np.uint32); yv={}
for name,inst in types:
    for (x,y,z,*_) in inst:
        col=int(round(x/dx)); row=int(round((z-(half if col&1 else 0))/dz))
        assert img[row,col]==0; img[row,col]=ids[name]|0xFF000000; yv[(row,col)]=y
print('hexes with trees',(img!=0).sum(), 'grid',img.shape)
rgb=np.stack([(img>>16)&255,(img>>8)&255,img&255],-1).astype(np.uint8)[::-1]
Image.fromarray(rgb).save('research/trees/vanilla_trees_hex.png')
# --- forward
seq=[];out={}
for row in range(img.shape[0]):
    for col in range(n):
        c=img[row,col]&0xFFFFFF
        if not img[row,col]: continue
        grp=groups[c]; r=R(col,row)
        name=grp[r.uint(0,len(grp)-1)]
        a=r.canon(); b=r.canon()
        z=((f32(0)+(f32(row)*dz+(half if col&1 else f32(0))))+a*f32(0.4))-f32(0.2)
        x=((b*f32(0.4)-f32(0.2))+f32(col)*dx)+f32(0)
        rot=r.uint(0,5)
        y=f32(yv[(row,col)])
        seq.append(name); out.setdefault(name,[]).append((x,y,z,rot))
order=ca_map_order(seq)
buf=bytearray(struct.pack('<IffffI',5,0,0,W,H,len(order)))
for name in order:
    buf+=struct.pack('<H',len(name))+name.encode()+struct.pack('<I',len(out[name]))
    sl=season_list(bits[name])
    for (x,y,z,rot) in out[name]:
        buf+=struct.pack('<fffBBI',x,y,z,1,rot,len(sl))+struct.pack('<%dI'%len(sl),*sl)
ref=open('Vanilla/Map/campaign_maps/3k_dlc07_main_map/display/trees/trees.campaign_tree_list','rb').read()
print(len(buf),len(ref),'IDENTICAL' if bytes(buf)==ref else 'DIFF at %d'%next(i for i,(p,q) in enumerate(zip(buf,ref)) if p!=q))
