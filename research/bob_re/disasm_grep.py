"""disasm_grep.py <dll> <function va hex> <size hex> <regex>: disassemble a function range and print matching instructions
with resolved RIP-relative float constants."""
import re
import struct
import sys

import capstone
import pefile

dll, fva, size, pat = sys.argv[1], int(sys.argv[2], 16), int(sys.argv[3], 16), re.compile(sys.argv[4])
pe = pefile.PE(dll)
base = pe.OPTIONAL_HEADER.ImageBase
code = pe.get_data(fva - base, size)
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
for ins in md.disasm(code, fva):
    text = f'{ins.mnemonic} {ins.op_str}'
    if pat.search(text):
        extra = ''
        m = re.search(r'\[rip \+ (0x[0-9a-f]+)\]', ins.op_str)
        if m:
            target = ins.address + ins.size + int(m.group(1), 16)
            try:
                raw = pe.get_data(target - base, 4)
                extra = f'   ; [{target:#x}] = {struct.unpack("<f", raw)[0]!r} ({raw.hex()})'
            except Exception:
                pass
        print(f'{ins.address:#x}  {text}{extra}')
