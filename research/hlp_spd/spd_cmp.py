import sys; sys.path.insert(0,'.')
from spd_parse import parse
import numpy as np
a=parse(sys.argv[1]); b=parse(sys.argv[2])
ga=a["grid"].astype(np.int64); gb=b["grid"].astype(np.int64)
print("box",(a["x0"],a["y0"],a["x1"],a["y1"]),(b["x0"],b["y0"],b["x1"],b["y1"]),"landmarks same",a["landmarks"]==b["landmarks"])
print("cells equal",(ga==gb).all(axis=2).mean(),"values equal",(ga==gb).mean())
INF=0xffffffff
for s in range(16):
    m=ga[:,:,s]!=gb[:,:,s]
    print(s,int(m.sum()),"mineINF",int((m&(ga[:,:,s]==INF)).sum()),"refINF",int((m&(gb[:,:,s]==INF)).sum()))
d=np.argwhere(ga!=gb)
if len(d):
    y,x,s=d[0]; print("first divergence",(x+a["x0"],y+a["y0"]),"slot",s,ga[y,x,s],gb[y,x,s])
