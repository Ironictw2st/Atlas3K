def m2(data,seed=0):
    m=0x5bd1e995; h=(seed^len(data))&0xffffffff; i=0; n=len(data)
    while n-i>=4:
        k=int.from_bytes(data[i:i+4],'little'); k=(k*m)&0xffffffff; k^=k>>24; k=(k*m)&0xffffffff
        h=(h*m)&0xffffffff; h^=k; i+=4
    r=n-i
    if r==3: h^=data[i+2]<<16
    if r>=2: h^=data[i+1]<<8
    if r>=1: h^=data[i]; h=(h*m)&0xffffffff
    h^=h>>13; h=(h*m)&0xffffffff; h^=h>>15
    return h
def m3(data,seed=0):
    c1,c2=0xcc9e2d51,0x1b873593; h=seed; n=len(data); i=0
    rotl=lambda x,r:((x<<r)|(x>>(32-r)))&0xffffffff
    while n-i>=4:
        k=int.from_bytes(data[i:i+4],'little'); k=(k*c1)&0xffffffff; k=rotl(k,15); k=(k*c2)&0xffffffff
        h^=k; h=rotl(h,13); h=(h*5+0xe6546b64)&0xffffffff; i+=4
    k=0; r=n-i
    if r==3: k^=data[i+2]<<16
    if r>=2: k^=data[i+1]<<8
    if r>=1:
        k^=data[i]; k=(k*c1)&0xffffffff; k=rotl(k,15); k=(k*c2)&0xffffffff; h^=k
    h^=n; h^=h>>16; h=(h*0x85ebca6b)&0xffffffff; h^=h>>13; h=(h*0xc2b2ae35)&0xffffffff; h^=h>>16
    return h
