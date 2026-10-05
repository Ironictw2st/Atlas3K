import pickle, numpy as np, sys
from dijk2 import dijkstra, road_masks
from ppd import DIRS
p=pickle.load(open("/tmp/ppd07.pkl","rb"))
d=pickle.load(open("/tmp/spd07.pkl","rb"))
g=d["grid"].astype(np.int64); x0,y0=d["x0"],d["y0"]
road=road_masks(p)
lm=int(sys.argv[1]); slot=int(sys.argv[2]); rev=sys.argv[3]=="1"
dist=dijkstra(p,d["landmarks"][lm],road,reverse=rev)
np.save(f"/tmp/dist_{lm}_{int(rev)}.npy",dist)
sub=dist[y0:d["y1"]+1, x0:d["x1"]+1]
ref=g[:,:,slot]
print("eq", (sub==ref).mean(), "neq", (sub!=ref).sum())
diff=np.argwhere(ref!=sub)
vals=[min(ref[y,x],sub[y,x]) for y,x in diff]
o=np.argsort(vals)
for i in o[:6]:
    y,x=diff[i]; X,Y=x+x0,y+y0
    print((X,Y),"ref",ref[y,x],"mine",sub[y,x], "type",p.hex_type()[Y,X], "road",bin(road[Y,X]), "edges",[hex(e) for e in p.cells[Y,X,:6]])
    for k,(dq,dr) in enumerate(DIRS[X&1]):
        nx,ny=X+dq,Y+dr
        print("   nb",k,(nx,ny),"t",p.hex_type()[ny,nx],"road",bin(road[ny,nx]),"ref",ref[ny-y0,nx-x0],"mine",sub[ny-y0,nx-x0],"edge nb->me",hex(p.cells[ny,nx,(k+3)%6]), p.costs[p.cells[ny,nx,(k+3)%6]&0x7f], "me->nb", hex(p.cells[Y,X,k]))
