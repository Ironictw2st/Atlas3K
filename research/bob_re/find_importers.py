"""Which kit binaries (dll/exe, recursive) import a symbol containing all given substrings.
usage: find_importers.py <substring> [substring ...]"""
import glob, os, sys
import pefile
B = r"C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\assembly_kit"
keys = [k.encode() for k in sys.argv[1:]]
for f in sorted(glob.glob(os.path.join(B, "**", "*.dll"), recursive=True) + glob.glob(os.path.join(B, "**", "*.exe"), recursive=True)):
    try:
        pe = pefile.PE(f, fast_load=True)
        pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]])
    except Exception:
        continue
    for d in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
        for i in d.imports:
            if i.name and all(k in i.name for k in keys):
                print(os.path.relpath(f, B), "<-", d.dll.decode(), i.name.decode()[:120])
