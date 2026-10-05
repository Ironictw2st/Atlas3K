"""Compare a startpos's settlement slot ZOE arrays with map_data slot blocks (from hlp-spd --dump-grid .regions.txt)."""
import sys; sys.path.insert(0,'Z:/Claude/TerryClone/research/hlp_spd')
import pickle
from esf_tree import find
root,s8,s16=pickle.load(open(sys.argv[1],'rb'))
md={}
for l in open(sys.argv[2]):
    f=l.rstrip('\n').split('\t')
    P=set(tuple(map(int,s.strip('()').split(','))) for s in (f[5].split(';') if f[5] else []))
    Q=set(tuple(map(int,s.strip('()').split(','))) for s in (f[6].split(';') if f[6] else []))
    md[f[1]]=(P,Q)
def vals(n): return [c[2] for g in n[3] for c in g if c[0]=='VAL']
def zoe(s):
    z=[c for g in s[3] for c in g if c[0]=='REC' and c[1]=='SLOT_ZOE_ARRAY']
    if not z: return set()
    v=[c[2] for g in z[0][3] for c in g if c[0]=='VAL']; return set(zip(v[0::2],v[1::2]))
diff=0; n=0
for e in find(root,'SETTLEMENT_EXPANSION_MAP_DATA'):
    ch=[c for g in e[3] for c in g]; key=s8.get(ch[0][2])
    sl=[c for c in ch if c[0]=='REC' and c[1]=='SLOT_MAP_DATA']
    P=zoe(sl[0]); Q=zoe(sl[1]) if len(sl)>1 else set()
    n+=1
    if key not in md: print("not in map_data",key); diff+=1; continue
    if P!=md[key][0] or Q!=md[key][1]:
        diff+=1; print(key,"primary eq",P==md[key][0],"port eq",Q==md[key][1],len(P),len(md[key][0]),len(Q),len(md[key][1]))
print("settlements",n,"differing",diff, "map_data regions with slots", sum(1 for v in md.values() if v[0] or v[1]))
