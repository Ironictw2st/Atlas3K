import sys, collections
sys.path.insert(0,'research/trees')
from tiles import read_tile_list
A=read_tile_list(sys.argv[1]); B=read_tile_list(sys.argv[2])
pa,ca,fa,ia,ra=A; pb,cb,fb,ib,rb=B
key=lambda p,c,r,ext: (r['x'],r['y'],p[r['path']].lower(),r['ori'] if ext else r['ori']&0xF0, c[r['climate']]) 
print('records',len(ra),len(rb),'header ints',ia,ib)
for ext in (False,True):
    ka=collections.Counter(key(pa,ca,r,ext) for r in ra); kb=collections.Counter(key(pb,cb,r,ext) for r in rb)
    print('with flow bit' if ext else 'pos+tile+rot+climate', 'overlap', sum((ka&kb).values()), f'{sum((ka&kb).values())/len(ra):.4f}')
pos=lambda p,r:(r['x'],r['y'],p[r['path']].lower())
sa={pos(pa,r) for r in ra}; sb={pos(pb,r) for r in rb}
print('same position+tile', len(sa&sb), f'{len(sa&sb)/len(sa):.4f}')
hl=sum(1 for x,y in zip(ra,rb) if (x['lo'],x['hi'])==(y['lo'],y['hi']) and pos(pa,x)==pos(pb,y)); print('same index & same lo/hi', hl)
same=sum(1 for x,y in zip(ra,rb) if pos(pa,x)==pos(pb,y) and x['ori']==y['ori'] and ca[x['climate']]==cb[y['climate']] and (x['lo'],x['hi'])==(y['lo'],y['hi'])); print('records identical in place', same, f'{same/len(ra):.4f}')
da={(r['x'],r['y'],pa[r['path']].lower()):(r['lo'],r['hi']) for r in ra}
m=t=0
for r in rb:
    k=(r['x'],r['y'],pb[r['path']].lower())
    if k in da:
        t+=1; m+= da[k]==(r['lo'],r['hi'])
print('lo/hi equal on matching tiles', m, t, f'{m/t:.4f}')
