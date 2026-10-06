"""Search BOB's lf normalisation rounding (battle lf_height_map, 224ad6d5): which float formula reproduces the DDS."""
import itertools
import numpy as np, tifffile
F = np.float32
C = r'Z:/Claude/BattleMaps/out/battle_parity/224ad6d5_3784_4c2d_93d4_87287c140efa'
s = tifffile.imread(C + '/src/map/lf_heights.tif').astype(np.int64)
d = open(C + '/existing/map/lf_height_map.dds', 'rb').read()
b = np.frombuffer(d, np.uint16, 512 * 512, 128).reshape(512, 512).astype(np.int64)
lo, hi = int(s.min()), int(s.max())
res = []
h = (s.astype(F) / F(65535)).astype(F)          # normalised source
hm = (s.astype(F) * F(F(1) / F(65535))).astype(F)
for hk, hv in (('div', h), ('mul', hm)):
    l, u = hv.min(), hv.max()
    for ok, t in (('a', ((hv - l) / (u - l)).astype(F)), ('b', ((hv - l) * (F(1) / (u - l))).astype(F))):
        for ek, e in (('trunc', (t * F(65535)).astype(F).astype(np.int64)), ('round', np.floor((t * F(65535)).astype(F) + F(0.5)).astype(np.int64)),
                      ('r2', np.rint((t * F(65535)).astype(F)).astype(np.int64))):
            res.append(((e != b).sum(), hk, ok, ek))
# double precision variants
hd = s / 65535.0
for ek, f in (('trunc', np.trunc), ('round', lambda x: np.floor(x + 0.5))):
    res.append(((f((hd - hd.min()) / (hd.max() - hd.min()) * 65535).astype(np.int64) != b).sum(), 'dbl', '-', ek))
for r in sorted(res)[:8]: print(r)
