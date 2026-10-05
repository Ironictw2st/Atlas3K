import sys, os, numpy as np, collections
sys.path.insert(0,'research/tiles'); sys.path.insert(0,'research/trees')
import placement as P
from tiles import read_tile_list
db=P.Db(P.ROOT+'/Vanilla/terrain/tiles/campaign/_tile_database')
by_loc={t['location'].lower().rstrip(chr(92)):t for t in db.tiles}
paths,clim,fl,ints,recs=read_tile_list(P.ROOT+'/Vanilla/Map/terrain/campaigns/3k_dlc07_main_map/tile_list.bin')
W,H=ints[1],ints[2]
def run(conv):
    cnt=np.zeros((H,W),np.int32); prev=None
    for r in recs:
        t=by_loc[paths[r['path']].lower().rstrip(chr(92))]
        if prev and (prev['x'],prev['y'])==(r['x'],r['y']) and t['tile_set'] in ('generic_sea','beach'):
            prev=r; continue
        prev=r
        w,h,rot=t['width'],t['height'],r['ori']&0xF0
        for j in range(h):
            for i in range(w):
                if not t['valid'][j][i]: continue
                dx,dy=conv(w,h,rot,i,j)
                x,y=r['x']+dx,r['y']+dy
                if 0<=x<W and 0<=y<H: cnt[y,x]+=1
    return (cnt==0).sum(),(cnt>1).sum()
print('h-1-j', run(lambda w,h,rot,i,j: P.rotate(w,h,rot,i,h-j-1)))
print('j    ', run(lambda w,h,rot,i,j: P.rotate(w,h,rot,i,j)))
own={}
over=collections.Counter(); prev=None
for r in recs:
    t=by_loc[paths[r['path']].lower().rstrip(chr(92))]
    if prev and (prev['x'],prev['y'])==(r['x'],r['y']) and t['tile_set'] in ('generic_sea','beach'):
        prev=r; continue
    prev=r
    w,h,rot=t['width'],t['height'],r['ori']&0xF0
    for j in range(h):
        for i in range(w):
            if not t['valid'][j][i]: continue
            dx,dy=P.rotate(w,h,rot,i,h-j-1); c=(r['x']+dx,r['y']+dy)
            if c in own: over[(own[c][0], t['key'])]+=1
            else: own[c]=(t['key'],r['x'],r['y'])
for k,v in over.most_common(15): print(v,k)
