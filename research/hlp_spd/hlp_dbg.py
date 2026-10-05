import sys
from hlp_parse import R
from esf_flat import *
b=open(sys.argv[1],"rb").read()
h=header(b); toks,_=tokens(b,h["body"],h["end"])
r=R(toks); n=r.v()
prev=None
for j in range(n):
    st=r.i
    if toks[st][1]!=7 or toks[st][2]!=j:
        print("BAD at",j); print([(hex(t),v) for _,t,v in toks[prev:st+20]]); break
    prev=st
    id_=r.v(); k=r.v()
    if k==0: continue
    area=r.v(); c=(r.v(),r.v()); a=r.v(); bb=r.v(); m=r.v()
    for _ in range(m): [r.v() for _ in range(9)]
    [r.v() for _ in range(m*(m-1))]
else:
    print("ok", n, "consumed", r.i, "of", len(toks)); print([(hex(t),v) for _,t,v in toks[r.i:r.i+50]])
