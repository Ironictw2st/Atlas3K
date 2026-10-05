import json
objs = json.load(open('../bob_re/frida_out/cam_s4g_patches.json'))['objs']
R = (-1, -1, 595.18524, 541.20667)
out = [o for o in objs if not (o['aabb'][0] >= R[0] and o['aabb'][1] >= R[1] and o['aabb'][2] <= R[2] and o['aabb'][3] <= R[3])]
print(len(out))
for o in out: print([round(v, 3) for v in o['aabb']])
ins = [o for o in objs if o not in out]
print('kept extremes', min(o['aabb'][0] for o in ins), min(o['aabb'][1] for o in ins), max(o['aabb'][2] for o in ins), max(o['aabb'][3] for o in ins))
