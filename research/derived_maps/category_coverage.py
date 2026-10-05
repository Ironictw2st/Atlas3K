"""Which tile categories does vanilla put in the land mesh, the sea mesh, or neither (hole)?
For every tile_list record, test the tile-map pixel centres it covers against land/sea vertex validity."""
import collections
import glob
import re

import numpy as np

import merger_proto as M
import tiles_lib as T

TOTAL = M.TOTAL


def validity(kind):
    valid = np.zeros((TOTAL + 1, TOTAL + 1), bool)
    for f in glob.glob(M.V + rf"\global_meshes\{kind}_mesh_*.rigid_model_v2"):
        b = open(f, 'rb').read()
        import struct
        vc, = struct.unpack_from('<I', b, 0xB4)
        io, ic = struct.unpack_from('<II', b, 0xB8)
        v = np.frombuffer(b, '<f4', count=vc * 4, offset=0x150).reshape(-1, 4)[:, :3]
        idx = np.frombuffer(b, '<u2', count=ic, offset=0xA8 + io).reshape(-1, 3)
        gi = np.round(v[:, 0] / M.CELL).astype(int); gj = np.round(v[:, 2] / M.CELL).astype(int)
        p = v[idx].astype(np.float64)
        area = (p[:, 1, 0] - p[:, 0, 0]) * (p[:, 2, 2] - p[:, 0, 2]) - (p[:, 2, 0] - p[:, 0, 0]) * (p[:, 1, 2] - p[:, 0, 2])
        for t in idx[np.abs(area) > 1e-9]:
            valid[gj[t].min():gj[t].max() + 1, gi[t].min():gi[t].max() + 1] = True
    return valid


land, sea = validity('land'), validity('sea')
db = T.read_db()
paths, climates, floats, ints, rec = T.read_tile_list(M.V + r"\tile_list.bin")
stats = collections.defaultdict(lambda: collections.Counter())
for r in rec:
    p = paths[r['path']].lower()
    cat = p.split('\\')[3]
    d = db[p]
    w, h = (d['h'], d['w']) if r['orient'] & 0xF0 in (0x20, 0x80) else (d['w'], d['h'])
    # tile px (x, y) with y = 0 south; one tile px = 2 mesh cells
    for ty in range(h):
        for tx in range(w):
            I, J = 2 * (r['x'] + tx) + 1, 2 * (r['y'] + ty) + 1
            if I > TOTAL or J > TOTAL:
                continue
            stats[cat][('L' if land[J, I] else '-') + ('S' if sea[J, I] else '-')] += 1
for cat, c in sorted(stats.items()):
    tot = sum(c.values())
    print(f'{cat:28s} ' + '  '.join(f'{k}:{v / tot:.2f}' for k, v in sorted(c.items())) + f'   (n={tot})')
