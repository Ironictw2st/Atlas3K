"""disasm_iat_calls.py <dll> <function va hex> <iat slot va hex> [before]: like research/bob_re/disasm_calls.py but for
calls through an import slot (call qword ptr [rip + X] with rip+X == slot)."""
import sys

import capstone
import pefile

dll, fva, slot = sys.argv[1], int(sys.argv[2], 16), int(sys.argv[3], 16)
before = int(sys.argv[4]) if len(sys.argv) > 4 else 30
pe = pefile.PE(dll, fast_load=True)
base = pe.OPTIONAL_HEADER.ImageBase
code = pe.get_data(fva - base, 0x10000)
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
md.detail = True
insns = list(md.disasm(code, fva))
for k, ins in enumerate(insns):
    if ins.mnemonic == 'call' and 'rip' in ins.op_str:
        disp = ins.operands[0].mem.disp
        if ins.address + ins.size + disp == slot:
            print(f'--- call at {ins.address:#x}')
            for p in insns[max(0, k - before):k + 3]:
                print(f'  {p.address:#x}  {p.mnemonic:6s} {p.op_str}')
