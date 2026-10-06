"""Extract the battle tile database settings (_settings.bin) from the game packs and print its conversion params.
usage: battle_settings.py"""
import glob, sys
sys.path.insert(0, r'Z:/Claude/UpdateMod/tools')
sys.path.insert(0, r'Z:/Claude/TerryClone/research/tiles')
from packidx import index
import tiledb

G = r'C:/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/data/'
OUT = r'Z:/Claude/TerryClone/research/battle_build/battle_settings.bin'
for p in sorted(glob.glob(G + '*.pack')):
    try:
        entries = index(p)
    except Exception:
        continue
    for n, sz, off, c in entries:
        if n.lower().replace(chr(92), '/').endswith('terrain/tiles/battle/_tile_database/_settings.bin'):
            with open(p, 'rb') as f:
                f.seek(off)
                data = f.read(sz)
            print(p, n, sz, 'compressed' if c else '')
            open(OUT, 'wb').write(data)
s = tiledb.load_settings(OUT)
print(s.keys() if isinstance(s, dict) else type(s))
print(s.get('conversion_params') if isinstance(s, dict) else s)
