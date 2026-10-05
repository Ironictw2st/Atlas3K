import sys, numpy as np
sys.path.insert(0,'research/tiles'); sys.path.insert(0,'research/trees')
import placement as P
from tiles import read_tile_list
f32=np.float32
db=P.Db(P.ROOT+'/Vanilla/terrain/tiles/campaign/_tile_database')
by_loc={t['location'].lower().rstrip(chr(92)):t for t in db.tiles}
paths,clim,fl,ints,recs=read_tile_list(P.ROOT+'/Vanilla/Map/terrain/campaigns/3k_dlc07_main_map/tile_list.bin')
TW,TH=ints[1],ints[2]
def dds(p,w,h): return np.frombuffer(open(p,'rb').read(),'<u2',offset=128,count=w*h).reshape(h,w)
V=P.ROOT+'/Vanilla/Map/terrain/campaigns/3k_dlc07_main_map/'
fields={False:(dds(V+'lf_height_map.dds',7136,5620).astype(np.float32)/f32(65535)).astype(np.float32),
        True:(dds(V+'lf_sea_height_map.dds',3568,2810).astype(np.float32)/f32(65535)).astype(np.float32)}
one=f32(1); two=f32(2)
def lohi(r,t):
    F=fields[bool(t['use_alt_lf'])]; fh,fw=F.shape
    s=max(t['width'],t['height']); x,y=r['x'],r['y']
    sx=one/f32(TW); sy=one/f32(TH)
    u0=f32(f32(x-2)*sx); v0=f32(f32(y-2)*sy)
    u1=f32(f32(f32(f32(x)+f32(s))+two)*sx); v1=f32(f32(f32(f32(y)+f32(s))+two)*sy)
    cl=lambda a: f32(0) if a<0 else (one if a>one else a)
    u0,v0,u1,v1=cl(u0),cl(v0),cl(u1),cl(v1)
    c0=int(f32(u0*f32(fw))); r0=int(f32(v0*f32(fh)))
    c1=f32(u1*f32(fw)); r1=f32(v1*f32(fh))
    lo,hi=f32(3.4028235e38),f32(-3.4028235e38)
    row=r0
    while f32(row)<r1:
        col=c0
        seg=[]
        while f32(col)<c1: col+=1
        a=F[fh-row-1, c0:col]
        if a.size: lo=min(lo,a.min()); hi=max(hi,a.max())
        row+=1
    return lo,hi
ok=0;n=0;bad=[]
for r in recs[::50]:
    t=by_loc[paths[r['path']].lower().rstrip(chr(92))]
    lo,hi=lohi(r,t); n+=1
    if f32(lo)==f32(r['lo']) and f32(hi)==f32(r['hi']): ok+=1
    elif len(bad)<8: bad.append((r['x'],r['y'],t['key'],r['lo'],float(lo),r['hi'],float(hi)))
print(ok,n); [print(b) for b in bad]
land=fields[False]
for name,F in [('full',land),('half',land[::2,::2]),('quarter',land[::4,::4]),('half-mean',land.reshape(2810,2,3568,2).mean((1,3)).astype(np.float32))]:
    fields[False]=F
    ok=n=0
    for r in recs[::200]:
        t=by_loc[paths[r['path']].lower().rstrip(chr(92))]
        if t['use_alt_lf']: continue
        lo,hi=lohi(r,t); n+=1
        ok+= f32(lo)==f32(r['lo']) and f32(hi)==f32(r['hi'])
    print(name,ok,n)
fields[False]=land
import itertools
def lohi2(r,t,a,b):
    F=fields[False]; fh,fw=F.shape
    s=max(t['width'],t['height']); x,y=r['x'],r['y']
    c0=max(0,int((x-a)/TW*fw)); r0=max(0,int((y-a)/TH*fh)); c1=min(fw,(x+s+b)/TW*fw); r1=min(fh,(y+s+b)/TH*fh)
    import math
    blk=F[fh-int(math.ceil(r1)):fh-r0, c0:int(math.ceil(c1))]
    return blk.min(),blk.max()
sample=[r for r in recs[::200] if not by_loc[paths[r['path']].lower().rstrip(chr(92))]['use_alt_lf']]
for a,b in itertools.product([0,1,2,3],[0,1,2,3]):
    ok=sum(1 for r in sample if (lambda lh:(f32(lh[0])==f32(r['lo']), f32(lh[1])==f32(r['hi'])))(lohi2(r,by_loc[paths[r['path']].lower().rstrip(chr(92))],a,b))==(True,True))
    print(a,b,ok,len(sample))
def lohi3(r,t,mode):
    F=fields[False]; fh,fw=F.shape
    s=max(t['width'],t['height']); x,y=r['x'],r['y']
    if mode=='div':   U=lambda v,N: f32(f32(v)/f32(N))
    elif mode=='mulrcp': U=lambda v,N: f32(f32(v)*f32(f32(1)/f32(N)))
    else: U=lambda v,N: v/N
    cl=lambda a: 0 if a<0 else (1 if a>1 else a)
    u0,v0=cl(U(x-2,TW)),cl(U(y-2,TH)); u1,v1=cl(U(x+s+2,TW)),cl(U(y+s+2,TH))
    m=(lambda a,b: f32(f32(a)*f32(b))) if mode!='exact' else (lambda a,b:a*b)
    c0=int(m(u0,fw)); r0=int(m(v0,fh)); c1=m(u1,fw); r1=m(v1,fh)
    import math
    cc=c0
    while cc<c1: cc+=1
    rr=r0
    while rr<r1: rr+=1
    blk=F[fh-rr:fh-r0, c0:cc]
    return blk.min(),blk.max()
for mode in ('exact','div','mulrcp'):
    ok=sum(1 for r in sample if (lambda lh:(f32(lh[0])==f32(r['lo']) and f32(lh[1])==f32(r['hi'])))(lohi3(r,by_loc[paths[r['path']].lower().rstrip(chr(92))],mode)))
    print(mode,ok,len(sample))
seadds=dds(V+'lf_sea_height_map.dds',3568,2810).astype(np.float64)
for nm,src in [('round',np.round(seadds*44217/65535)),('floor',np.floor(seadds*44217/65535)),('ceil',np.ceil(seadds*44217/65535))]:
    fields[True]=(src.astype(np.float32)/f32(65535)).astype(np.float32)
    ss=[r for r in recs[::20] if by_loc[paths[r['path']].lower().rstrip(chr(92))]['use_alt_lf']]
    ok=0
    for r in ss:
        t=by_loc[paths[r['path']].lower().rstrip(chr(92))]
        F=fields[True]; fh,fw=F.shape; s=max(t['width'],t['height']); x,y=r['x'],r['y']
        U=lambda v,N: f32(f32(v)/f32(N)); cl=lambda a: f32(0) if a<0 else (f32(1) if a>1 else a)
        u0,v0,u1,v1=cl(U(x-2,TW)),cl(U(y-2,TH)),cl(U(x+s+2,TW)),cl(U(y+s+2,TH))
        c0=int(f32(u0*f32(fw))); r0=int(f32(v0*f32(fh))); c1=f32(u1*f32(fw)); r1=f32(v1*f32(fh))
        cc=c0
        while cc<c1: cc+=1
        rr=r0
        while rr<r1: rr+=1
        blk=F[fh-rr:fh-r0,c0:cc]
        ok+= f32(blk.min())==f32(r['lo']) and f32(blk.max())==f32(r['hi'])
    print(nm,ok,len(ss))
