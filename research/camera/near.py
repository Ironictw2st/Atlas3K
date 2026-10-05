import json, os, sys
objs = json.load(open('../bob_re/frida_out/cam_s4g_patches.json'))['objs']
pm = {int(k): os.path.basename(v) for k, v in json.load(open('../bob_re/frida_out/cam_s4d_patchmap.json')).items()}
name, x0, x1 = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
for o in objs:
    if name in pm[o['i']] and x0 <= o['m'][3] <= x1: print(o['i'], [round(v, 5) for v in o['m'][:12]])
