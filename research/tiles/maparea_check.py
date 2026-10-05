import sys, glob
sys.path.insert(0,'research/tiles'); sys.path.insert(0,'research/trees')
import tiledb
from tiles import read_tile_list
s,t=tiledb.load_all('Vanilla/terrain/tiles/campaign/_tile_database')
by_loc={v['variations'][0]['location'].lower().rstrip(chr(92)):v for v in t.values()}
for f in ['Vanilla/Map/terrain/campaigns/3k_dlc07_main_map/tile_list.bin','research/main190/combo_guandu/src/terrain/campaigns/3k_guandu_map/tile_list.bin','research/main190/stage_hx_terrain/tile_list.bin','research/main190/merge_src/terrain/campaigns/3k_dlc07_main_map/tile_list.bin']:
    paths,clim,fl,ints,recs=read_tile_list(f)
    x0=y0=10**9; x1=y1=-10**9; miss=0
    for r in recs:
        v=by_loc.get(paths[r['path']].lower().rstrip(chr(92)))
        if not v: miss+=1; continue
        sz=max(v['width'],v['height'])
        x0=min(x0,r['x']-sz); y0=min(y0,r['y']-sz); x1=max(x1,r['x']+sz); y1=max(y1,r['y']+sz)
    print(f[-60:], 'file',ints[7:11],'computed',(x0,y0,x1,y1),'missing tiles',miss)
