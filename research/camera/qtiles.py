import json, sys, collections
sys.path.insert(0, '../trees'); from tiles import read_tile_list
inst = json.load(open('../bob_re/frida_out/cam_s4h_tileinst.json'))['inst']
paths, clim, fl, ints, recs = read_tile_list('../../Vanilla/Map/terrain/campaigns/3k_dlc07_main_map/tile_list.bin')
_, _, _, _, gm = read_tile_list('../../Vanilla/Map/terrain/campaigns/3k_dlc07_main_map/global_map/tile_list.bin')
same = sum(1 for i, r in zip(inst, recs) if i[0] == r['x'] and i[1] == r['y'])
print('instances', len(inst), 'records', len(recs), 'same x,y in order', same)
print('flags', collections.Counter(i[2] >> 8 for i in inst).most_common(6))
print('flag 0x100 vs global_map flag bit0:', collections.Counter(((i[2] >> 8) & 1, g['flag'] & 1) for i, g in zip(inst, gm)))
nodes = json.load(open('../bob_re/frida_out/cam_s4h_qnodes.json'))['nodes']
where = {}
for n in nodes:
    for t in n['tiles']: where.setdefault(t, []).append((n['d'], n['b']))
print('tiles stored', len(where), 'multi', sum(1 for v in where.values() if len(v) > 1), 'depth hist', collections.Counter(v[0][0] for v in where.values()))
json.dump({str(k): v[0] for k, v in where.items()}, open('tile_nodes.json', 'w'))
print('root', nodes[0]['b'])
# map instances -> records by (x, y, orientation)
key = collections.defaultdict(list)
for i, r in enumerate(recs): key[(r['x'], r['y'], r['ori'] & 0xF0)].append(i)
amb = 0; inst2rec = {}
for t, (x, y, f) in enumerate(inst):
    c = key.get((x, y, f & 0xF0), [])
    if len(c) == 1: inst2rec[t] = c[0]
    else: amb += 1
print('mapped', len(inst2rec), 'ambiguous/unmapped', amb)
stored = set(int(k) for k in json.load(open('tile_nodes.json')))
st = collections.Counter((t in stored, gm[inst2rec[t]]['flag'] & 1, (inst[t][2] >> 8) & 1) for t in inst2rec)
print('(in tree, gm flag bit0, inst 0x100):', sorted(st.items()))
print('orient low bits', collections.Counter(f & 0xff for _, _, f in inst).most_common(8))
