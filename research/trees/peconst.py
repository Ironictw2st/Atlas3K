import pefile,struct,sys
pe=pefile.PE(r'Z:\Claude\Tools\qttoolutility.modder.x64.dll',fast_load=True)
base=pe.OPTIONAL_HEADER.ImageBase
def rd(a,n): return pe.get_data(a-base,n)
for s in sys.argv[1:]:
    a=int(s,16); b=rd(a,8)
    print(hex(a), struct.unpack('<f',b[:4])[0], b[:4].hex(), struct.unpack('<d',b)[0])
