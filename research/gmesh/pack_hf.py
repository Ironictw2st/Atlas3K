"""Header lo/hi of the campaign tile hf maps in the game packs (are any generic tiles non-zero?)."""
import glob, os, sys, collections
sys.path.insert(0, r"Z:\Claude\TerryClone\tools\bob_mcp"); sys.path.insert(0, r"Z:\Claude\TerryClone\research")
import packindex, compressed_map as C
D = r"C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\data"
c = collections.Counter()
for pack in sorted(glob.glob(os.path.join(D, "*.pack"))):
    try: es = packindex.index(pack)
    except Exception: continue
    for e in es:
        k = e[0].lower().replace(chr(92), '/')
        if k.startswith('terrain/tiles/campaign/') and k.endswith('hf_height_map.compressed_map'):
            h = C.read_header(packindex.read(pack, e))[5]
            c[(k.split('/')[3], h[1] != 0 or h[4] != 0)] += 1
print(sorted(c.items()))
