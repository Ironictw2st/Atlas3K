import pickle, numpy as np, sys
from gamepf import search
from ppd import DIRS
p=pickle.load(open("/tmp/ppd07.pkl","rb")); model=pickle.load(open("/tmp/"+(sys.argv[4] if len(sys.argv)>4 else "model07")+".pkl","rb"))
d=pickle.load(open("/tmp/spd07.pkl","rb"))
g=d["grid"].astype(np.int64); x0,y0,x1,y1=d["x0"],d["y0"],d["x1"],d["y1"]
lm=int(sys.argv[1]); rev=int(sys.argv[2])
dist=search(p,model,d["landmarks"][lm],bool(rev)); np.save(f"/tmp/gd_{lm}_{rev}.npy",dist)
sub=dist[y0:y1+1,x0:x1+1]; ref=g[:,:,2*lm+rev]
print("eq",(sub==ref).mean())
diff=np.argwhere(ref!=sub)
vals=[min(ref[y,x],sub[y,x]) for y,x in diff]
o=np.argsort(vals,kind="stable")
e,types,costs,links=model
for i in o[:int(sys.argv[3]) if len(sys.argv)>3 else 3]:
    y,x=diff[i]; X,Y=x+x0,y+y0
    print((X,Y),"ref",ref[y,x],"mine",sub[y,x],"type",types[Y,X],"edges",[(hex(v),costs[v&0x7f]) for v in e[Y,X]], "link",(X,Y) in links)
    for k,(dq,dr) in enumerate(DIRS[X&1]):
        nx,ny=X+dq,Y+dr
        print("   nb",k,(nx,ny),"t",types[ny,nx],"ref",ref[ny-y0,nx-x0],"mine",sub[ny-y0,nx-x0],"nb->me",costs[e[ny,nx,(k+3)%6]&0x7f],"me->nb",costs[e[Y,X,k]&0x7f])
