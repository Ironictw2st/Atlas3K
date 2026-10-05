"""Find code in empirecampaign.modder.x64.dll that loads a float constant (RIP-relative) - usage: findconst.py <float> [lo hi]"""
import pefile, capstone, struct, sys
P=r"C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\assembly_kit\binaries\empirecampaign.modder.x64.dll"
pe=pefile.PE(P, fast_load=True); IB=pe.OPTIONAL_HEADER.ImageBase
val=struct.pack('<f',float(sys.argv[1]))
addrs=[]
for s in pe.sections:
    d=s.get_data(); i=d.find(val)
    while i>=0:
        if i%4==0: addrs.append(IB+s.VirtualAddress+i)
        i=d.find(val,i+1)
print("const at",[hex(a) for a in addrs[:20]])
text=[s for s in pe.sections if s.Name.startswith(b'.text')][0]
code=text.get_data(); base=IB+text.VirtualAddress
lo=int(sys.argv[2],16) if len(sys.argv)>2 else base; hi=int(sys.argv[3],16) if len(sys.argv)>3 else base+len(code)
targets=set(addrs)
# scan for rip-relative disp32 references: instr at p, disp at p+k, target = p+len+disp; brute force: for every 4-byte window compute candidate
import numpy as np
arr=np.frombuffer(code,dtype=np.uint8)
hits=[]
for off in range(lo-base, min(hi-base,len(code)-4)):
    disp=int.from_bytes(code[off:off+4],'little',signed=True)
    for extra in (4,5):  # disp followed by 0 or 1 imm byte
        tgt=base+off+extra+disp
        if tgt in targets: hits.append((base+off,tgt))
print(len(hits)); print([hex(h[0]) for h in hits[:60]])
