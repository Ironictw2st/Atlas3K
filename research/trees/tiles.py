import struct
def read_tile_list(p):
    b=open(p,'rb').read(); o=12
    def strs(o):
        n,=struct.unpack_from('<I',b,o); o+=4; out=[]
        for _ in range(n):
            L,=struct.unpack_from('<H',b,o); o+=2; out.append(b[o:o+L].decode()); o+=L
        return out,o
    paths,o=strs(o); clim,o=strs(o)
    fl=struct.unpack_from('<6f',b,o); o+=24; ints=struct.unpack_from('<11i',b,o); o+=44; o+=1
    n,=struct.unpack_from('<I',b,o); o+=4
    recs=[]
    for i in range(n):
        ver,path,cl,x,y,ori,flag,lo,hi=struct.unpack_from('<HIBHHBBff',b,o); o+=21
        recs.append(dict(path=path,climate=cl,x=x,y=y,ori=ori,flag=flag,lo=lo,hi=hi))
    return paths,clim,fl,ints,recs
