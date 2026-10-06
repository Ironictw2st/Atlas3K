"""hf: separate x/y offsets near 129 and where the remaining mismatches are."""
import glob, sys
import numpy as np, tifffile
sys.path.insert(0, r'Z:/Claude/TerryClone/research')
import compressed_map as cm
F = np.float32
pre = sys.argv[1] if len(sys.argv) > 1 else 'dfe064a6'
C = glob.glob(rf'Z:/Claude/BattleMaps/out/battle_parity/{pre}*')[0]
h = tifffile.imread(glob.glob(C + '/src/tile/*.height.*.tif')[0]).astype(F)
r = cm.decode(open(C + '/bob_run1/tile/hf_height_map.compressed_map', 'rb').read())
b = np.asarray(r[0] if isinstance(r, tuple) else r).astype(np.int64)
lo, hi = h.min(), h.max()
for oy in range(126, 132):
    for ox in range(126, 132):
        w = h[oy:oy + 1025, ox:ox + 1025]
        v = (((w - lo) * F(F(1) / (hi - lo))).astype(F) * F(65535)).astype(F).astype(np.int64)
        n = (v != b).sum()
        if n < 2000: print(oy, ox, n)
w = h[129:1154, 129:1154]; v = (((w - lo) * F(F(1) / (hi - lo))).astype(F) * F(65535)).astype(F).astype(np.int64)
m = np.argwhere(v != b); print('mismatch rows', np.unique(m[:, 0])[:20], 'cols', np.unique(m[:, 1])[:20], 'diffs', np.unique((v - b)[v != b])[:10])
print([(y, x, w[y, x], v[y, x], b[y, x]) for y, x in m[:8]])
