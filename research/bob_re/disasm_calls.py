"""disasm_calls.py <dll> <function va hex> <callee va hex> [before]: disassemble the instructions leading up to each call
of <callee> inside the function starting at <function va> (scans 64 KB)."""
import sys

import capstone
import pefile

dll, fva, callee = sys.argv[1], int(sys.argv[2], 16), int(sys.argv[3], 16)
before = int(sys.argv[4]) if len(sys.argv) > 4 else 25
pe = pefile.PE(dll)
base = pe.OPTIONAL_HEADER.ImageBase
code = pe.get_data(fva - base, 0x10000)
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
insns = list(md.disasm(code, fva))
for k, ins in enumerate(insns):
    if ins.mnemonic == 'call' and ins.op_str.startswith('0x') and int(ins.op_str, 16) == callee:
        print(f'--- call at {ins.address:#x}')
        for p in insns[max(0, k - before):k + 3]:
            print(f'  {p.address:#x}  {p.mnemonic:6s} {p.op_str}')
    if ins.mnemonic == 'int3' and k > 50 and insns[k - 1].mnemonic in ('ret', 'jmp', 'int3') and ins.address > fva + 0x4000:
        break
