"""calls.py <dll> <func va>: list direct calls in a function (bounds from .pdata) with export names when known."""
import sys, bisect, capstone, pefile
dll, fva = sys.argv[1], int(sys.argv[2], 16)
pe = pefile.PE(dll, fast_load=True)
pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXCEPTION"], pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXPORT"]])
base = pe.OPTIONAL_HEADER.ImageBase
names = {base + e.address: (e.name or b"").decode("latin1") for e in getattr(pe, "DIRECTORY_ENTRY_EXPORT").symbols}
funcs = sorted((e.struct.BeginAddress, e.struct.EndAddress) for e in pe.DIRECTORY_ENTRY_EXCEPTION)
rva = fva - base
end = max(f[1] for f in funcs if f[0] == rva)
code = pe.get_memory_mapped_image()[rva:end]
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
for ins in md.disasm(code, fva):
    if ins.mnemonic == "call":
        t = ins.op_str
        try:
            tv = int(t, 16); print(f"{ins.address:#x} call {tv:#x} {names.get(tv, '')[:150]}")
        except ValueError:
            print(f"{ins.address:#x} call {t}")
