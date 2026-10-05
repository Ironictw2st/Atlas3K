"""Which data packs carry a map's terrain inputs (lf maps, tile lists), and do they match the kit's working_data copies?
BOB reads these through the game file system, so a pack copy overrides the kit's (vanilla: CA's shipped files).
usage: find_pack_inputs.py <map> [extract root [pack file name]]"""
import glob, os, sys
sys.path.insert(0, r"Z:\Claude\TerryClone\tools\bob_mcp")
import packindex

GAME = r"C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS"
MAP = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else None
ONLY = sys.argv[3].lower() if len(sys.argv) > 3 else None
W = os.path.join(GAME, "assembly_kit", "working_data", "terrain", "campaigns", MAP)
WANT = ["lf_height_map.compressed_map", "lf_sea_height_map.compressed_map", "tile_list.bin", "global_map/tile_list.bin"]
for p in sorted(glob.glob(os.path.join(GAME, "data", "*.pack"))):
    try:
        idx = packindex.index(p)
    except Exception as ex:
        print("skip", os.path.basename(p), ex)
        continue
    for e in idx:
        k = e[0].lower().replace(chr(92), "/")
        for w in WANT:
            if k != f"terrain/campaigns/{MAP}/{w}":
                continue
            b = packindex.read(p, e)
            kit = os.path.join(W, w)
            kb = open(kit, "rb").read() if os.path.exists(kit) else None
            print(os.path.basename(p), w, len(b), "same as kit" if b == kb else f"DIFFERS from kit ({None if kb is None else len(kb)})")
            if OUT and (ONLY is None or os.path.basename(p).lower() == ONLY):
                dst = os.path.join(OUT, "terrain", "campaigns", MAP, *w.split("/"))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                open(dst, "wb").write(b)
