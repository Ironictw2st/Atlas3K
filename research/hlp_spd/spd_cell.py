import sys; sys.path.insert(0,'.')
from spd_parse import parse
import numpy as np
a=parse(sys.argv[1]); b=parse(sys.argv[2])
ga=a["grid"].astype(np.int64); gb=b["grid"].astype(np.int64)
for s in range(16):
    m=ga[:,:,s]!=gb[:,:,s]
    ys,xs=np.nonzero(m)
    if len(xs)==0: continue
    print(s,len(xs),"x",xs.min()+a["x0"],xs.max()+a["x0"],"y",ys.min()+a["y0"],ys.max()+a["y0"], "mine<ref",int((ga[:,:,s][m]<gb[:,:,s][m]).sum()))
x,y=int(sys.argv[3]),int(sys.argv[4])
print("mine",[hex(v) for v in ga[y-a["y0"],x-a["x0"]]])
print("ref ",[hex(v) for v in gb[y-b["y0"],x-b["x0"]]])
