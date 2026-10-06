"""lf normalisation search over every corpus map folder: which float32 formula reproduces BOB's lf_height_map.dds on all."""
import glob, itertools, os
import numpy as np, tifffile

F = np.float32
D = np.float64
cases = []
for c in glob.glob(r'Z:/Claude/BattleMaps/out/battle_parity/*'):
    if os.path.exists(c + '/src/map/lf_heights.tif') and os.path.exists(c + '/bob_run1/map/lf_height_map.dds'):
        s = tifffile.imread(c + '/src/map/lf_heights.tif')
        h0, w0 = s.shape
        b = np.frombuffer(open(c + '/bob_run1/map/lf_height_map.dds', 'rb').read(), np.uint16, h0 * w0, 128).reshape(h0, w0).astype(np.int64)
        cases.append((os.path.basename(c)[:8], s, b))

hs = {'div': lambda s: (s.astype(F) / F(65535)).astype(F), 'mul': lambda s: (s.astype(F) * F(F(1) / F(65535))).astype(F),
      'mulx': lambda s: (s.astype(D) * D(F(1) / F(65535))).astype(F)}
def ts(h, lo, hi):
    inv = F(F(1) / (hi - lo))
    return {'mulinv': ((h - lo) * inv).astype(F), 'div': ((h - lo) / (hi - lo)).astype(F),
            'mulinv_dbl': ((h - lo).astype(D) * D(inv)).astype(F),
            'fma_inv': ((h.astype(D) - D(lo)) * D(inv)).astype(F),
            'sub_dbl_div': ((h.astype(D) - D(lo)) / D(hi - lo)).astype(F)}
outs = {'trunc': lambda t: (t * F(65535)).astype(F).astype(np.int64), 'trunc_dbl': lambda t: (t.astype(D) * 65535).astype(np.int64),
        'fma': lambda t: np.trunc(t.astype(D) * D(65535)).astype(np.int64)}
res = {}
for name, s, b in cases:
    for hk, hf in hs.items():
        h = hf(s); lo, hi = h.min(), h.max()
        for tk, t in ts(h, lo, hi).items():
            for ok, of in outs.items():
                res.setdefault((hk, tk, ok), []).append(int((of(t) != b).sum()))
for k, v in sorted(res.items(), key=lambda kv: sum(kv[1])): print(sum(v), v, k)
