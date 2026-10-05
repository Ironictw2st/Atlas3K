"""Write BOB's per-mesh height grids (and merged index lists) as <Kind>_<row>_<col>.bob.bin / .merged.bin for the native
builder's research overrides (ATLAS3K_GMESH_BOB_GRIDS). (row, col) of each BOB mesh: the native grid it agrees with
best (|d| < 1e-3), so it doesn't depend on BOB's loop numbering. Needs a native dump in output/mesh_parity/gmesh_native_dump.
usage: export_bob_grids.py <out dir>"""
import os, sys, glob, json, numpy as np
sys.path.insert(0, '.')
from grid_cmp import *
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
seq = bob_sequence(); h, mg = bob_dumps()
nat = {os.path.basename(f)[:-6]: np.fromfile(f, np.float32) for f in glob.glob(NAT + '*.y.bin')}
mapping = []
for (kind, k, name), d, m in zip(seq, h, mg):
    b = np.fromfile(BIN + d['file'], np.float32)
    cands = [n for n in nat if n.startswith(kind)]
    best = max(cands, key=lambda n: ((np.abs(nat[n] - b) < 1e-3) & (b != -20)).sum() + ((nat[n] == -20) & (b == -20)).sum())
    score = ((np.abs(nat[best] - b) < 1e-3)).mean()
    b.tofile(os.path.join(out, best + '.bob.bin'))
    (np.fromfile(BIN + m['file'], np.uint32) if 'file' in m else np.zeros(0, np.uint32)).tofile(os.path.join(out, best + '.merged.bin'))
    mapping.append(dict(kind=kind, k=k, file=name, grid=best, agree=float(score)))
json.dump(mapping, open(os.path.join(out, 'mapping.json'), 'w'), indent=1)
low = [x for x in mapping if x['agree'] < 0.9]
print(len(mapping), 'grids;', len(low), 'below 90% agreement', low[:5])
