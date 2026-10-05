"""use_alt_lf (last byte) and barbarian (second last) of every campaign tile-database entry, tallied per tile set."""
import collections, struct, sys
sys.path.insert(0, '.')
from tile_bins import entries
c = collections.Counter(); per = {}
for k, b in entries():
    o = 10
    def s():
        global o
        n = struct.unpack_from('<H', b, o)[0]; v = b[o + 2:o + 2 + n].decode(errors='replace'); o += 2 + n; return v
    name = s(); tset = s()
    c[(tset, b[-2], b[-1])] += 1
    per[k.split('/')[-1]] = (tset, b[-1])
for key, v in sorted(c.items()): print(key, v)
