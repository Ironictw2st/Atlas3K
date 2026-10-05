import numpy as np
f32=np.float32
M=0x7fffffff
class R:
    def __init__(s,col,row):
        v=((row<<16)|col)%M
        s.v=v if v else 1
    def nxt(s):
        s.v=(s.v*48271)%M; return s.v
    def uint(s,lo,hi):
        rng=hi-lo
        if rng==0:
            return lo
        n=rng+1
        while True:
            ret=0; mask=0
            while mask<rng:
                while True:
                    v=s.nxt()-1
                    if v<=0x3fffffff: break
                ret=((ret<<30)|v)&0xffffffff; mask=((mask<<30)|0x3fffffff)&0xffffffff
            if not (mask//n<=ret//n and mask%n!=rng): break
        return ret%n+lo
    def canon(s):
        return (f32(s.nxt())-f32(1))/f32(2147483648.0)
