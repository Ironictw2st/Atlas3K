"""Print hex types (* = bridge hex) and area ids around a point. usage: maparea.py <map dir> <grid dump prefix> x0 x1 y0 y1"""
import sys; sys.path.insert(0,'.')
import numpy as np
from ppd import Ppd, parse_rest
d,pre,x0,x1,y0,y1=sys.argv[1],sys.argv[2],*map(int,sys.argv[3:7])
p=Ppd(d+'/pathfinding.ppd'); parse_rest(p); t=p.hex_type()
am=np.fromfile(pre+'.areas',np.uint16).reshape(p.H,p.W)
br=set()
for a,b in p.bridges:
    for h in a+b: br.add(tuple(h))
print('     '+' '.join(f"{x:>7}" for x in range(x0,x1+1)))
for y in range(y0,y1+1):
    print(f"{y:4} "+' '.join(f"{int(t[y,x])}{'*' if (x,y) in br else ' '}{int(am[y,x]):5d}" for x in range(x0,x1+1)))
for a,b in p.bridges:
    if any(x0<=h[0]<=x1 and y0<=h[1]<=y1 for h in a+b): print("bridge",a,b)
