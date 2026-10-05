import pickle, numpy as np, sys
from hlp2 import Grid
from ppd import DIRS
p=pickle.load(open("/tmp/ppd07.pkl","rb")); mz=pickle.load(open("/tmp/model07c.pkl","rb")); mp=pickle.load(open("/tmp/model07.pkl","rb"))
prim,port=pickle.load(open("/tmp/slots07.pkl","rb")); hl=np.load("/tmp/hlci07.npy")
t=p.hex_type()
G=Grid(p,mz,mp,prim|port,hl)
_g=G.gated
def gated(settle,cc,ce):
    e=_g(settle,cc,ce)
    for y,x in zip(*np.nonzero(t==2)):
        for k,(dq,dr) in enumerate(DIRS[x&1]):
            e[y,x,k]&=0x7F
            nx,ny=x+dq,y+dr
            if 0<=nx<p.W and 0<=ny<p.H: e[ny,nx,(k+3)%6]&=0x7F
    return e
G.gated=gated
def trace(a,b,settle="blocked"):
    c,path=G.path(a,b,settle)
    e=G.gated(settle,int(hl[a[1],a[0]]),int(hl[b[1],b[0]]))
    steps=[]
    for u,v in zip(path,path[1:]):
        k=[i for i,(dq,dr) in enumerate(DIRS[u[0]&1]) if (u[0]+dq,u[1]+dr)==v]
        steps.append((v,int(t[v[1],v[0]]),int(G.costs[e[u[1],u[0],k[0]]&0x7f]) if k else 500, v in prim, v in port))
    print(a,b,c,"hlci",hl[a[1],a[0]],hl[b[1],b[0]],steps)
if __name__=="__main__":
    for s in sys.argv[1:]:
        a,b=s.split(":"); trace(tuple(map(int,a.split(","))),tuple(map(int,b.split(","))))

beach=np.zeros((p.H,p.W,6),bool)
for a_,l_,ent,lev in p.beaches:
    for (x,y,m) in ent+lev:
        for k in range(6):
            if m>>k&1: beach[y,x,k]=True
_nb=G.neighbours
def nbh(e,x,y,reverse=False):
    for v,c in _nb(e,x,y,reverse):
        if abs(v[0]-x)<=1 and abs(v[1]-y)<=1 and hl[v[1],v[0]]!=hl[y,x]:
            k=[i for i,(dq,dr) in enumerate(DIRS[x&1]) if (x+dq,y+dr)==v]
            if k and not beach[y,x,k[0]]: continue
        yield v,c
G.neighbours=nbh
for s in ["628,631:628,633","418,325:418,323","213,551:214,550","371,190:370,189"]:
    a,b=s.split(":"); trace(tuple(map(int,a.split(","))),tuple(map(int,b.split(","))))
