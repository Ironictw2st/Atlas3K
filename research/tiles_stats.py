import sys, collections
sys.path.insert(0,'research/trees')
from tiles import read_tile_list
paths,clim,fl,ints,recs=read_tile_list('Vanilla/Map/terrain/campaigns/3k_dlc07_main_map/tile_list.bin')
short=lambda p: paths[p].split(chr(92)+'campaign'+chr(92))[-1]
pos=collections.Counter((r['x'],r['y']) for r in recs)
dups=[k for k,v in pos.items() if v>1]
print('records',len(recs),'distinct pos',len(pos),'dup positions',len(dups))
i=0
for r in recs:
    if pos[(r['x'],r['y'])]>1 and i<12:
        print(r['x'],r['y'],short(r['path']),hex(r['ori']),r['flag'],clim[r['climate']],r['lo'],r['hi']); i+=1
print('ori',collections.Counter(hex(r['ori']) for r in recs).most_common())
print('flag',collections.Counter(r['flag'] for r in recs).most_common())
print('ints',ints,'floats',fl)
