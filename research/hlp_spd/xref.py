"""xref.py <dll> <string regex> : find strings (ascii) and the functions (from .pdata) that reference them via RIP-relative lea/mov."""
import re, sys, struct, bisect
import pefile
dll, pat = sys.argv[1], re.compile(sys.argv[2].encode())
pe = pefile.PE(dll, fast_load=True)
pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXCEPTION"]])
base = pe.OPTIONAL_HEADER.ImageBase
img = pe.get_memory_mapped_image()
funcs = sorted((e.struct.BeginAddress, e.struct.EndAddress) for e in pe.DIRECTORY_ENTRY_EXCEPTION)
starts = [f[0] for f in funcs]
targets = {}
for m in re.finditer(rb"[\x20-\x7e]{4,}\x00", img):
    s = m.group()[:-1]
    if pat.search(s): targets[m.start()] = s.decode()
text = [s for s in pe.sections if s.Name.startswith(b".text")][0]
t0, t1 = text.VirtualAddress, text.VirtualAddress + text.Misc_VirtualSize
code = img[t0:t1]
hits = {}
for i in range(len(code) - 7):
    if code[i + 1] in (0x8D, 0x8B) and code[i] in (0x48, 0x4C) and (code[i + 2] & 0xC7) == 0x05:
        disp = struct.unpack_from("<i", code, i + 3)[0]
        tgt = t0 + i + 7 + disp
        if tgt in targets:
            rva = t0 + i
            k = bisect.bisect_right(starts, rva) - 1
            f = funcs[k][0] if k >= 0 and funcs[k][0] <= rva < funcs[k][1] else None
            hits.setdefault(targets[tgt], []).append((rva, f))
for s, h in sorted(hits.items()):
    print(repr(s))
    for rva, f in h:
        print(f"   ref {base + rva:#x} in func {base + f:#x}" if f else f"   ref {base + rva:#x}")
print("unreferenced:", [s for s in targets.values() if s not in hits][:50])
