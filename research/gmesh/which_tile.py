"""Tile-list records at a tile position (x, y), with their folder contents in the kit's working_data."""
import sys, os
sys.path.insert(0, r"Z:\Claude\TerryClone\research\derived_maps")
import tiles_lib as TL
paths, cl, fl, ints, rec = TL.read_tile_list(r"Z:\Claude\TerryClone\output\bob_runs\frida_gmesh_main190_bob_terrain\inputs\tile_list.bin")
x, y = int(sys.argv[1]), int(sys.argv[2])
A = r"C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\assembly_kit_190E\working_data"
for i, r in enumerate(rec):
    if r['x'] == x and r['y'] == y:
        p = paths[r['path']]; d = os.path.join(A, p.rstrip(chr(92)))
        print(i, p, hex(r['orient']), hex(r['flag']), 'files:', sorted(os.listdir(d)) if os.path.isdir(d) else 'NO DIR')
