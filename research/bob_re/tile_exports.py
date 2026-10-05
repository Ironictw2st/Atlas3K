"""List warscape.modder.x64.dll exports relevant to tile matching (RVA, name) and check the image base, so a Frida hook
can resolve them by name (or by RVA from the Ghidra addresses, base 0x180000000)."""
import pefile, sys
DLL = r"C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\assembly_kit_190E\binaries\warscape.modder.x64.dll"
pe = pefile.PE(DLL, fast_load=True)
pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXPORT"]])
print("image base", hex(pe.OPTIONAL_HEADER.ImageBase))
keys = sys.argv[1:] or ["TILE_DATABASE_TILE@", "scan_for_tiles", "select_tiles_for_pass", "build_tile_map", "sort@TILE_DATABASE", "tile_count@TILE_DATABASE", "tile@TILE_DATABASE"]
for e in pe.DIRECTORY_ENTRY_EXPORT.symbols:
    n = (e.name or b"").decode("latin1")
    if any(k in n for k in keys) and ("name@" in n or "scan_for" in n or "select_tiles" in n or "build_tile_map" in n or "sort@" in n
                                      or "tile_count" in n or "?tile@TILE_DATABASE" in n or "file@" in n or "path@" in n):
        print(hex(e.address), n)
