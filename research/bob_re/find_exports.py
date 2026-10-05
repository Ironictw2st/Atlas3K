"""Search every DLL in the kit's binaries folder for exports containing all of the given substrings.
usage: find_exports.py <substring> [substring ...]"""
import glob, os, sys
import pefile
B = r"C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\assembly_kit\binaries"
keys = sys.argv[1:]
for dll in sorted(glob.glob(os.path.join(B, "*.dll"))):
    try:
        pe = pefile.PE(dll, fast_load=True)
        pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXPORT"]])
    except Exception:
        continue
    for e in getattr(getattr(pe, "DIRECTORY_ENTRY_EXPORT", None), "symbols", []) or []:
        n = (e.name or b"").decode("latin1")
        if all(k in n for k in keys):
            print(os.path.basename(dll), hex(e.address), n[:200])
