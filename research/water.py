"""How is water represented? Compare lf height, sea height and the region lookup (sea regions)."""
import numpy as np

T = r"Z:\Claude\TerryClone\Vanilla\Map\terrain\campaigns\3k_dlc07_main_map"
C = r"Z:\Claude\TerryClone\Vanilla\Map\campaign_maps\3k_dlc07_main_map"

h = np.fromfile(T + r"\lf_height_map.dds", np.uint16, offset=128).reshape(5620, 7136)
s = np.fromfile(T + r"\lf_sea_height_map.dds", np.uint16, offset=128).reshape(2810, 3568)
print("land h percentiles", np.percentile(h, [0, 1, 5, 10, 25, 50, 75, 95, 100]))
print("sea  s percentiles", np.percentile(s, [0, 1, 5, 10, 25, 50, 75, 95, 100]))
hd = h[::2, ::2]
for thr in (0, 1000, 5000, 10000, 14280, 20000):
    m = hd <= thr
    print(f"h<={thr}: frac {m.mean():.3f}  sea mean there {s[m].mean() if m.any() else 0:.0f}  sea mean elsewhere {s[~m].mean():.0f}")
# relation where both valid
print("corr h vs s", np.corrcoef(hd.ravel()[::97].astype(float), s.ravel()[::97].astype(float))[0, 1])
# world y=0 => h = 3.12/0.00021849
print("h at world y=0:", 3.12 / 0.00021849)
# lookup tga palette sea detection: palette count at byte 5..6, pixels u16 after palette
b = open(C + r"\3k_main_lookup.tga", "rb").read()
idlen = b[0]; cmap_first = b[3] | b[4] << 8; cmap_len = b[5] | b[6] << 8; cmap_bits = b[7]
w = b[12] | b[13] << 8; hh = b[14] | b[15] << 8
off = 18 + idlen + cmap_len * cmap_bits // 8
idx = np.frombuffer(b, np.uint16, w * hh, off).reshape(hh, w)
print("lookup", w, hh, "index range", idx.min(), idx.max(), "first", cmap_first, "len", cmap_len)
# sample lf height at lookup pixels (nearest) and show per-index median height -> sea regions low
ys = (np.arange(hh) * 5620 // hh); xs = (np.arange(w) * 7136 // w)
hl = h[ys][:, xs]
vals = [(i, np.median(hl[idx == i])) for i in np.unique(idx)[:400:1]]
vals.sort(key=lambda t: t[1])
print("lowest-median lookup indices:", [(int(i), int(m)) for i, m in vals[:10]])
print("highest-median lookup indices:", [(int(i), int(m)) for i, m in vals[-5:]])
lowidx = [i for i, m in vals if m < 14280]
print("count indices with median below y=0:", len(lowidx))
