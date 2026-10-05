import json, sys, collections
import numpy as np
sys.path.insert(0, '../trees'); from tiles import read_tile_list
F = np.float32
inst = json.load(open('../bob_re/frida_out/cam_s4h_tileinst.json'))['inst']
nodes = json.load(open('../bob_re/frida_out/cam_s4h_qnodes.json'))['nodes']
where = {}
for n in nodes:
    for t in n['tiles']: where[t] = n['b']
print('stored flag hi-byte', collections.Counter(inst[t][2] >> 8 for t in where).most_common(10))
print('all flag 0x100 count', sum(1 for i in inst if i[2] & 0x100), 'stored with 0x100', sum(1 for t in where if inst[t][2] & 0x100))
paths, clim, fl, ints, gm = read_tile_list('../../Vanilla/Map/terrain/campaigns/3k_dlc07_main_map/global_map/tile_list.bin')
flagged = [r for r in gm if r['flag'] & 1]
fk = collections.Counter((r['x'], r['y'], r['ori'] & 0xF0) for r in flagged)
sk = collections.Counter((inst[t][0], inst[t][1], inst[t][2] & 0xF0) for t in where)
print('flagged records', len(flagged), 'key multiset equal to stored tiles:', fk == sk, 'diff', sum((fk - sk).values()), sum((sk - fk).values()))
allk = collections.Counter((i[0], i[1]) for i in inst); recs = read_tile_list('../../Vanilla/Map/terrain/campaigns/3k_dlc07_main_map/tile_list.bin')[4]
rk = collections.Counter((r['x'], r['y']) for r in recs)
print('all instances (x,y) multiset == records:', allk == rk, sum((allk - rk).values()))
print('inst x range', min(i[0] for i in inst), max(i[0] for i in inst), 'y', min(i[1] for i in inst), max(i[1] for i in inst))
st = [inst[t] for t in where][:10]; print('stored sample', st)
print('flagged sample', [(r['x'], r['y'], r['ori']) for r in flagged[:10]])
