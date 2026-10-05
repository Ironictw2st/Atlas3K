import sys, numpy as np
sys.path.insert(0,'research/tiles'); sys.path.insert(0,'research/trees')
import placement as P
from tiles import read_tile_list
db=P.Db(P.ROOT+'/Vanilla/terrain/tiles/campaign/_tile_database')
by_loc={t['location'].lower().rstrip(chr(92)):t for t in db.tiles}
paths,clim,fl,ints,recs=read_tile_list(P.ROOT+'/Vanilla/Map/terrain/campaigns/3k_dlc07_main_map/tile_list.bin')
W,H=ints[1],ints[2]
def first_cell(r,t):
    w,h,rot=t['width'],t['height'],r['ori']&0xF0
    for j in range(h):
        for i in range(w):
            if t['valid'][j][i]:
                dx,dy=P.rotate(w,h,rot,i,h-j-1); return (r['x']+dx,r['y']+dy)
keys=[]
for r in recs:
    t=by_loc[paths[r['path']].lower().rstrip(chr(92))]
    fx,fy=first_cell(r,t); keys.append((fy,fx))
bad=sum(1 for a,b in zip(keys,keys[1:]) if b<a)
print('order violations by first cell (y,x):',bad, 'equal-key neighbours:',sum(1 for a,b in zip(keys,keys[1:]) if a==b))
bad2=sum(1 for a,b in zip(recs,recs[1:]) if (b['y'],b['x'])<(a['y'],a['x']))
print('order violations by anchor:',bad2)
# first-use order of paths/climates
seenp=[];seenc=[]
for r in recs:
    if r['path'] not in seenp: seenp.append(r['path'])
    if r['climate'] not in seenc: seenc.append(r['climate'])
print('paths first-use ordered:',seenp==list(range(len(paths))),'climates:',seenc==list(range(len(clim))), len(paths), len(seenp))
print('header',fl,ints)
