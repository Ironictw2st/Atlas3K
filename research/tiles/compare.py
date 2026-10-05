"""Compare a placement prototype pickle with vanilla tile_list.bin."""
import sys, pickle, collections
sys.path.insert(0, 'research/trees')
from tiles import read_tile_list

proto = pickle.load(open(sys.argv[1] if len(sys.argv) > 1 else 'output/tiles_proto.pkl', 'rb'))
paths, clim, fl, ints, recs = read_tile_list('Vanilla/Map/terrain/campaigns/3k_dlc07_main_map/tile_list.bin')
norm = lambda p: p.lower().replace('/', chr(92)).rstrip(chr(92))
short = lambda p: norm(p).split(chr(92) + 'campaign' + chr(92))[-1]

van = [(r['x'], r['y'], short(paths[r['path']]), r['ori'] & 0xF0, clim[r['climate']]) for r in recs]
tiles = proto['tiles']
cn = proto['climates']
mine = []
for (layer, x, y, ti, rot, c, first) in proto['instances']:
    mine.append((x, y, short(tiles[ti][2]), rot, cn[c]))

print('vanilla', len(van), 'proto', len(mine))
cv, cm = collections.Counter(van), collections.Counter(mine)
common = sum((cv & cm).values())
print('multiset overlap', common, f'({common / len(van):.4f} of vanilla)')
pos_v = {(a[0], a[1], a[2]) for a in van}
pos_m = {(a[0], a[1], a[2]) for a in mine}
print('same (x,y,tile) ignoring rot/climate:', len(pos_v & pos_m))
# first divergence in placement order is not observable; show spatial first difference in vanilla order
mset = set(mine)
miss = [a for a in van if a not in mset]
print('first vanilla records missing from proto:')
for a in miss[:15]:
    near = [b for b in mine if b[0] == a[0] and b[1] == a[1]]
    print('  ', a, '-> proto at same xy:', near[:3])
by_tile_v = collections.Counter(a[2] for a in van)
by_tile_m = collections.Counter(a[2] for a in mine)
diff = sorted(((by_tile_m[k] - by_tile_v[k]), k) for k in set(by_tile_v) | set(by_tile_m))
print('tile count diffs (proto - vanilla), worst:')
for d, k in diff[:10] + diff[-10:]:
    if d:
        print(f'  {d:+6d} {k} (vanilla {by_tile_v[k]})')
