"""hf_height_map.compressed_map (1025x1025) from the tile project's float height TIF (1280x1280): find the crop/sample
and normalisation that reproduce BOB. usage: hf_search.py [project id prefix]"""
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
print('tif', h.shape, lo, hi, 'bob', b.shape, b.min(), b.max())


def norm(w, lo, hi, mode):
    if mode == 'mulinv': return (((w - lo) * F(F(1) / (hi - lo))).astype(F) * F(65535)).astype(F).astype(np.int64)
    if mode == 'div': return (((w - lo) / (hi - lo)).astype(F) * F(65535)).astype(F).astype(np.int64)
    if mode == 'round': return np.floor(((w - lo) / (hi - lo)).astype(F) * F(65535) + F(0.5)).astype(np.int64)


best = []
for off in range(0, 256):
    for flip in (False, True):
        w = h[off:off + 1025, off:off + 1025]
        if w.shape != (1025, 1025): continue
        if flip: w = w[::-1]
        for mode in ('mulinv', 'div', 'round'):
            for wl in ('tif', 'win'):
                l, u = (lo, hi) if wl == 'tif' else (w.min(), w.max())
                if u <= l: continue
                v = norm(w, l, u, mode)
                best.append(((v != b).sum(), off, flip, mode, wl))
for x in sorted(best)[:8]: print(x)
