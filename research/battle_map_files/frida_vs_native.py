"""First divergence between BOB's place_tile sequence (Frida, frida_battle_tiles.js) and the native placement trace
(ATLAS3K_BATTLE_TILE_TRACE). place_tile y is the anchor passed to place_tile (south-origin), as the trace's Y.
usage: frida_vs_native.py <frida.jsonl> <trace.tsv>"""
import json, sys

BS = chr(92)
norm = lambda s: s.lower().replace('/', BS).rstrip(BS)
bob = [json.loads(l) for l in open(sys.argv[1]) if '"place"' in l]
mine = [l.rstrip('\n').split('\t') for l in open(sys.argv[2])]
mine = [m for m in mine if m[4] == '1']          # layer-2 also-place tiles go through TILE_MAP::place_tile only
print('bob places', len(bob), 'native layer-1 placements', len(mine))
for i, (b, m) in enumerate(zip(bob, mine)):
    if norm(b['loc']) != norm(m[0]) or b['x'] != int(m[1]) or b['y'] != int(m[2]) or b['rot'] != int(m[3]):
        print('first diff at', i)
        for j in range(max(0, i - 3), min(len(bob), len(mine), i + 5)):
            print(f"  {j} bob pass {bob[j]['pass']} {norm(bob[j]['loc'])[-45:]} {bob[j]['x']},{bob[j]['y']} {bob[j]['rot']:#x}"
                  f" | native {norm(mine[j][0])[-45:]} {mine[j][1]},{mine[j][2]} {int(mine[j][3]):#x}")
        break
else:
    print('no divergence in the common prefix')
