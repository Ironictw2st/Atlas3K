"""Does the main190 pack carry its own lf maps / tile data, and do they differ from the kit working_data copies BOB was
assumed to read?"""
import sys, os, hashlib
sys.path.insert(0, r"Z:\Claude\TerryClone\tools\bob_mcp")
import packindex
D = r"C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\data"
W = r"C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\assembly_kit_190E\working_data"
pack = os.path.join(D, "!!190_expanded_region_test_main190.pack")
es = packindex.index(pack)
for e in es:
    k = e[0].lower().replace(chr(92), '/')
    if '3k_190e_expanded_map/' in k and ('lf_' in k or 'tile_list' in k):
        b = packindex.read(pack, e); loose = os.path.join(W, k.replace('/', os.sep))
        same = os.path.exists(loose) and open(loose, 'rb').read() == b
        print(k, len(b), 'same as working_data' if same else ('DIFFERS' if os.path.exists(loose) else 'no loose copy'))
print(sum(1 for e in es if 'terrain/tiles/' in e[0].lower().replace(chr(92), '/')), 'tile files in pack')
