"""Extract the main190 pack's terrain inputs (lf maps, tile_list, its tile files) into a native build's --out folder:
with the pack at type 4 (movie) BOB reads these instead of the kit's working_data copies.
usage: extract_pack_inputs.py <out root>"""
import sys, os
sys.path.insert(0, r"Z:\Claude\TerryClone\tools\bob_mcp")
import packindex
D = r"C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\data"
pack = os.path.join(D, "!!190_expanded_region_test_main190.pack")
out = sys.argv[1]
n = 0
for e in packindex.index(pack):
    k = e[0].lower().replace(chr(92), '/')
    if (k.startswith('terrain/campaigns/3k_190e_expanded_map/') and ('lf_' in k and k.endswith('.compressed_map') or k.endswith('tile_list.bin'))) \
            or k.startswith('terrain/tiles/'):
        dst = os.path.join(out, k.replace('/', os.sep)); os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst, 'wb').write(packindex.read(pack, e)); n += 1
print(n, 'files')
