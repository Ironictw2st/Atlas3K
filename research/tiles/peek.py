import sys, numpy as np
sys.path.insert(0,'research/trees'); sys.path.insert(0,'research/tiles')
from tiles import read_tile_list
from PIL import Image
import placement as P
paths,clim,fl,ints,recs=read_tile_list('Vanilla/Map/terrain/campaigns/3k_dlc07_main_map/tile_list.bin')
short=lambda p: p.split(chr(92)+'campaign'+chr(92))[-1]
img=np.array(Image.open(P.AK+'tile_map.png').convert('RGB'))[::-1]
db=P.Db(P.ROOT+'/Vanilla/terrain/tiles/campaign/_tile_database'); g=P.Groups(db)
name={v:k for k,v in g.by_rgb.items()}
setname=lambda rgb: next((ts['name'] for ts in db.sets if tuple(ts['rgb'])==rgb), str(rgb))
want=sys.argv[1]; n=0
for r in recs:
    if short(paths[r['path']]).rstrip(chr(92))==want:
        x,y=r['x'],r['y']; print('rec',x,y,hex(r['ori']))
        for yy in range(y+4,y-3,-1):
            print(' '.join(setname(tuple(int(v) for v in img[yy,xx]))[:6].ljust(6) for xx in range(x-2,x+6)))
        near=[(rr['x'],rr['y'],short(paths[rr['path']]),hex(rr['ori'])) for rr in recs if abs(rr['x']-x)<=4 and abs(rr['y']-y)<=4]
        print(near); n+=1
        if n>=2: break
