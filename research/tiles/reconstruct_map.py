"""Reconstruct the tile-map PNG BOB must have used, from vanilla tile_list.bin: each layer-1 tile's footprint
(rotation + mask) painted in its tile set's colour. Uncovered cells stay black (no group).
Usage: python reconstruct_map.py out.png"""
import sys, os
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'trees'))
import placement as P
from tiles import read_tile_list

db = P.Db(P.ROOT + '/Vanilla/terrain/tiles/campaign/_tile_database')
by_loc = {}
for t in db.tiles:
    by_loc.setdefault(t['location'].lower().rstrip(chr(92)), t)
paths, clim, fl, ints, recs = read_tile_list(P.ROOT + '/Vanilla/Map/terrain/campaigns/3k_dlc07_main_map/tile_list.bin')
W, H = ints[1], ints[2]
img = np.zeros((H, W, 3), np.uint8)
cover = np.zeros((H, W), np.int32)      # 1 = layer-1 footprint of an also_place tile
def cells(r, t):
    w, h, rot = t['width'], t['height'], r['ori'] & 0xF0
    for j in range(h):
        for i in range(w):
            if t['valid'][j][i]:
                dx, dy = P.rotate(w, h, rot, i, h - j - 1)
                x, y = r['x'] + dx, r['y'] + dy
                if 0 <= x < W and 0 <= y < H:
                    yield x, y
targets = {db.sets[s]['also_place_tile_set'] for s in range(db.n_sets) if db.sets[s]['also_place_tile_set']}
ts_of = lambda r: by_loc[paths[r['path']].lower().rstrip(chr(92))]
for r in recs:
    t = ts_of(r)
    if t['also_place']:
        for x, y in cells(r, t):
            cover[y, x] = 1
layer2 = 0
for r in recs:
    t = ts_of(r)
    cs = list(cells(r, t))
    if t['tile_set'] in targets and cs and all(cover[y, x] for x, y in cs):
        layer2 += 1
        continue
    for x, y in cs:
        img[y, x] = db.sets[t['set']]['rgb']
print('layer-2 records', layer2, 'uncovered cells', int((img.sum(2) == 0).sum()))
Image.fromarray(img[::-1]).save(sys.argv[1] if len(sys.argv) > 1 else P.ROOT + '/output/tile_map_reconstructed.png')
