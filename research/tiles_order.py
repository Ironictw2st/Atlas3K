import sys; sys.path.insert(0,'research/trees')
from tiles import read_tile_list
paths,clim,fl,ints,recs=read_tile_list('Vanilla/Map/terrain/campaigns/3k_dlc07_main_map/tile_list.bin')
short=lambda p: paths[p].split(chr(92)+'campaign'+chr(92))[-1]
runs=[]
for i,r in enumerate(recs):
    if not runs or runs[-1][0]!=r['path']: runs.append([r['path'],i,1,(r['x'],r['y'])])
    else: runs[-1][2]+=1
print(len(runs),'runs of',len(recs))
for p,i,n,xy in runs[:int(sys.argv[1]) if len(sys.argv)>1 else 40]:
    print(i,n,short(p),xy,(recs[i+n-1]['x'],recs[i+n-1]['y']))
