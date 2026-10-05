import sys, pickle; sys.path.insert(0,'Z:/Claude/TerryClone/research/hlp_spd')
from esf_tree import find
root,s8,s16=pickle.load(open(sys.argv[1],'rb'))
inv={v:k for k,v in s8.items()}
def strs(n,acc):
    if n[0]=='REC':
        for g in n[3]:
            for c in g: strs(c,acc)
    elif n[0]=='VAL' and n[1]==0x0f: acc.add(s8.get(n[2]))
    return acc
def summ(n,depth=0,maxd=2,ind=''):
    out=[]
    if n[0]=='REC':
        out.append(f"{ind}<{n[1]}>")
        if depth<maxd:
            for g in n[3]:
                for c in g: out+=summ(c,depth+1,maxd,ind+'  ')
    elif n[0]=='VAL':
        v=n[2]
        if n[1]==0x0f: v=s8.get(v)
        elif n[1]==0x0e: v=s16.get(v)
        out.append(f"{ind}{n[1]:#x} {v}")
    else: out.append(f"{ind}ARR {n[1]:#x} len={len(n[2])}")
    return out
