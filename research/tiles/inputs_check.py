import sys, numpy as np, collections
sys.path.insert(0,'research/tiles'); sys.path.insert(0,'research/trees'); sys.path.insert(0,'research')
import tiledb, compressed_map as CM
from PIL import Image
from tiles import read_tile_list
AK='C:/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/assembly_kit/raw_data/terrain/campaigns/3k_dlc07_main_map/'
s,t=tiledb.load_all('Vanilla/terrain/tiles/campaign/_tile_database')
setcol={ts['rgb']:ts['name'] for ts in s['tile_sets']}
tilecol={}
for k,v in t.items():
    if v['rgb']!=(0,0,0): tilecol.setdefault(v['rgb'],[]).append(k)
img=np.array(Image.open(AK+'tile_map.png').convert('RGB'))
cols,counts=np.unique(img.reshape(-1,3),axis=0,return_counts=True)
unk=0
for c,n in zip(cols,counts):
    c=tuple(int(x) for x in c)
    nm=setcol.get(c) or (('tile:'+','.join(tilecol[c])) if c in tilecol else None)
    if nm is None: unk+=n
print(len(cols),'colours; pixels with no group:',unk, 'of', img.shape[0]*img.shape[1])
print('tile-colour tiles:',sum(len(v) for v in tilecol.values()))
for c,n in sorted(zip(map(tuple,cols),counts),key=lambda z:-z[1])[:25]:
    c=tuple(int(x) for x in c); print(c,n,setcol.get(c) or tilecol.get(c))
# climate
paths,clim,fl,ints,recs=read_tile_list('Vanilla/Map/terrain/campaigns/3k_dlc07_main_map/tile_list.bin')
cm,_=CM.decode('Vanilla/Map/terrain/campaigns/3k_dlc07_main_map/climate_map.cm')
print('climate_map.cm',cm.shape,np.unique(cm))
H=cm.shape[0]
cn=[c['name'] for c in s['climates']]
agree=sum(cn[cm[H-1-r['y'],r['x']]]==clim[r['climate']] for r in recs[::10]); print('cm agree (flip)',agree/len(recs[::10]))
agree=sum(cn[cm[r['y'],r['x']]]==clim[r['climate']] for r in recs[::10]); print('cm agree (noflip)',agree/len(recs[::10]))
