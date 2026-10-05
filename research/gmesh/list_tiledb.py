"""List the campaign _tile_database sub-folders in the game packs (tile sets: exclude_from_global_mesh, use_alt_lf)."""
import glob, os, sys, collections
sys.path.insert(0, r"Z:\Claude\TerryClone\tools\bob_mcp")
import packindex
D = r"C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\data"
c = collections.Counter(); ex = []
for pack in sorted(glob.glob(os.path.join(D, "*.pack"))):
    try: entries = packindex.index(pack)
    except Exception: continue
    for e in entries:
        k = e[0].lower().replace(chr(92), '/')
        if '_tile_database' in k and 'campaign' in k:
            sub = k.split('_tile_database/')[1].split('/')[0]; c[sub] += 1
            if sub != 'tiles' and len(ex) < 12: ex.append((os.path.basename(pack), k, e[2]))
print(c); print(*ex, sep='\n')
