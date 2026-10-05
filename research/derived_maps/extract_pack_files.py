"""extract_pack_files.py <out root> <internal path> [...]: copy files out of the vanilla game packs, keeping their paths."""
import glob
import os
import sys

sys.path.insert(0, r"Z:\Claude\TerryClone\tools\bob_mcp")
import packindex

D = r"C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\data"
out_root = sys.argv[1]
want = {p.lower().replace('/', os.sep) for p in sys.argv[2:]}
for pack in sorted(glob.glob(os.path.join(D, "*.pack"))):
    try:
        entries = packindex.index(pack)
    except Exception:
        continue
    for e in entries:
        key = e[0].lower().replace('/', os.sep)
        if key in want:
            dst = os.path.join(out_root, key)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, 'wb') as f:
                f.write(packindex.read(pack, e))
            print('ok', os.path.basename(pack), key, e[2])
            want.discard(key)
for k in want:
    print('missing', k)
