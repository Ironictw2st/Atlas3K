"""Check CA's spd values against my edge model: for hexes away from the 1024 alias strips, an outward value must be
min over neighbours of value(nb) + cost(nb -> h)."""
import sys; sys.path.insert(0,'.')
import numpy as np
from spd_parse import parse
from ppd import DIRS
M='Z:/Claude/TerryClone/output/hlp_spd/'
W,H=1478,1133
fwd=np.fromfile(M+'g190.fwd',np.uint32).reshape(H,W,6)
b=parse(sys.argv[1] if len(sys.argv)>1 else M+'main190/campaign_maps/3k_190e_expanded_map/spd_data.esf')
g=b["grid"].astype(np.int64); x0,y0=b["x0"],b["y0"]
INF=0xffffffff
bad=[]
for slot in (0,):
    for y in range(y0+1,950):
        for x in range(x0+1,950):
            v=g[y-y0,x-x0,slot]
            best=INF
            for d,(dx,dy) in enumerate(DIRS[x&1]):
                nx,ny=x+dx,y+dy
                c=fwd[ny,nx,(d+3)%6]
                if c==INF: continue
                nv=g[ny-y0,nx-x0,slot]
                if nv==INF: continue
                best=min(best,nv+int(c))
            if v!=INF and v!=0 and best!=v: bad.append((x,y,v,best))
import pickle; pickle.dump(bad,open(sys.argv[2],"wb")) if len(sys.argv)>2 else None; print(len(bad))
