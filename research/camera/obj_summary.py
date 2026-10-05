import json, collections, os
objs = json.load(open('../bob_re/frida_out/cam_s4g_patches.json'))['objs']
pm = {int(k): os.path.basename(v) for k, v in json.load(open('../bob_re/frida_out/cam_s4d_patchmap.json')).items()}
print(len(objs))
c = collections.Counter(pm[o['i']] for o in objs)
print(len(c)); print(c.most_common(80))
riv = [o for o in objs if 'river_' in pm[o['i']]]
print(len(riv)); o = riv[0]; print(o['m'], o['inv'], o['aabb'], o['en'], o['addlf'])
o = [o for o in objs if 'river_' not in pm[o['i']]][0]; print(pm[o['i']], {k: v for k, v in o.items() if k != 'cm'})
print(collections.Counter((o['en'], o['addlf']) for o in objs))
print([ (o['i'], pm[o['i']][:30]) for o in objs[:5]], [(o['i'], pm[o['i']][:30]) for o in objs[-5:]])
