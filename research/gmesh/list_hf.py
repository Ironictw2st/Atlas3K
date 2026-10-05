"""Count the campaign tile hf map kinds in the game packs (hf_height_map, _mesh_delta, hf_water_map)."""
import glob, os, sys, collections
sys.path.insert(0, r"Z:\Claude\TerryClone\tools\bob_mcp")
import packindex
D = r"C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\data"
c = collections.Counter(); where = collections.Counter()
for pack in sorted(glob.glob(os.path.join(D, "*.pack"))):
    try: es = packindex.index(pack)
    except Exception: continue
    for e in es:
        k = e[0].lower().replace(chr(92), '/')
        if k.startswith('terrain/tiles/campaign/') and 'hf_' in k:
            c[k.split('/')[-1]] += 1; where[(os.path.basename(pack), k.split('/')[-1])] += 1
print(c); print(where)
