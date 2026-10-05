"""scan_imm.py <dll> <regex>: disassemble the whole .text (linear, per .pdata function) and print matching instructions with function start."""
import sys, re, capstone, pefile
dll, pat = sys.argv[1], re.compile(sys.argv[2])
pe = pefile.PE(dll, fast_load=True)
pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXCEPTION"]])
base = pe.OPTIONAL_HEADER.ImageBase
img = pe.get_memory_mapped_image()
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
lo = int(sys.argv[3], 16) - base if len(sys.argv) > 3 else 0
hi = int(sys.argv[4], 16) - base if len(sys.argv) > 4 else 1 << 40
seen = set()
for e in pe.DIRECTORY_ENTRY_EXCEPTION:
    b, en = e.struct.BeginAddress, e.struct.EndAddress
    if b in seen or not (lo <= b < hi): continue
    seen.add(b)
    for ins in md.disasm(img[b:en], base + b):
        t = f"{ins.mnemonic} {ins.op_str}"
        if pat.search(t): print(f"{base+b:#x} {ins.address:#x} {t}")
