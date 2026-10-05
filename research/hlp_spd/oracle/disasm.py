import pefile, capstone, sys
P=r"C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\assembly_kit\binaries\empirecampaign.modder.x64.dll"
pe=pefile.PE(P, fast_load=True); IB=pe.OPTIONAL_HEADER.ImageBase
a=int(sys.argv[1],16); n=int(sys.argv[2],16)
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64)
for i in md.disasm(pe.get_data(a-IB,n),a): print(hex(i.address),i.mnemonic,i.op_str)
