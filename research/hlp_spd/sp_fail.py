import sys; sys.path.insert(0,'Z:/Claude/TerryClone/research/hlp_spd')
import esf_tree
from esf_tree import read
b,names,s8,s16=read(sys.argv[1])
stack=[]
_node=esf_tree.node
def wrap(b_,p,names_,root=False):
    stack.append(p)
    r=_node(b_,p,names_,root)
    stack.pop()
    return r
esf_tree.node=wrap
try: wrap(b,16,names,True); print("ok")
except Exception as ex:
    print(repr(ex), "stack", stack[-6:])
    p=stack[-1]; print(b[p-60:p+30].hex())
    for q in stack[-6:]:
        t=b[q]
        if t&0x80:
            ni=((t&1)<<8)|b[q+1] if not (t&0x20) else int.from_bytes(b[q+1:q+3],'little')
            print(q,hex(t),names[ni] if ni<len(names) else ni)
