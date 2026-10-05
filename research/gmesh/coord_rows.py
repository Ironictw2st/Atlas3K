import collections, numpy as np, pickle, os
src=open('coord_fit.py',encoding='utf-8').read().split("forms=")[0]
exec(src)
pickle.dump(pts,open('Z:/Claude/TerryClone/output/mesh_parity2/coord_pts.pkl','wb'))
row=collections.defaultdict(collections.Counter)
for i,j,h in pts:
    zs={d[1] for d in h}; xs={d[0] for d in h}
    row[j]['z0' if 0 in zs else ('z+1' if 1 in zs else 'z-1')]+=1
    row[j]['x0' if 0 in xs else 'x+1']+=1
for j in range(0,370,1):
    c=row[j]
    if c['z+1'] or c['z-1'] or c['x+1']: print(j, 3690+j, dict(c))
