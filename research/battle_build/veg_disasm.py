"""Disassemble a range of a kit DLL (capstone). usage: veg_disasm.py <dll name> <start va hex> <end va hex>"""
import sys
import capstone
import pefile
from veg_dllconst import KIT

dll, a, b = sys.argv[1], int(sys.argv[2], 16), int(sys.argv[3], 16)
pe = pefile.PE(KIT + dll, fast_load=True)
base = pe.OPTIONAL_HEADER.ImageBase
code = pe.get_data(a - base, b - a)
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
for ins in md.disasm(code, a):
    print(f"{ins.address:x}  {ins.mnemonic:8s} {ins.op_str}")
