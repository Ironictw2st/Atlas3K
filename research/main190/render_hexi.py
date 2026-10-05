"""Hexi close-up of hex/map.hex: regions, borders, roads, towns labelled with their hex count."""
import sys, numpy as np
sys.path[:0] = ['.', '../guandu', '..']
from PIL import Image, ImageDraw, ImageFont
from regions_plan import load
f, names, w, h = load('hex/map.hex'); reg = f['region']; c0, c1, r0, r1 = 0, 430, 560, 840; S = 3
rng = np.random.default_rng(5); pal = rng.integers(110, 235, (len(names) + 2, 3)).astype(np.uint8)
img = pal[np.clip(reg, 0, None)].copy()
img[f['terr'] == 1] = (70, 105, 150); imp = f['imp'] == 1; img[imp] = (img[imp] * 0.62).astype(np.uint8)
img[(f['river'] > 0) & (f['terr'] != 1)] = (90, 130, 190)
e = np.zeros(reg.shape, bool); e[:, 1:] |= reg[:, 1:] != reg[:, :-1]; e[1:] |= reg[1:] != reg[:-1]; img[e & (f['terr'] != 1)] = (25, 25, 25)
img[(f['road'] > 0) & (f['terr'] != 1)] = (150, 60, 40)
sub = img[r0:r1, c0:c1][::-1]; im = Image.fromarray(sub).resize(((c1 - c0) * S, (r1 - r0) * S), Image.NEAREST); d = ImageDraw.Draw(im)
font = ImageFont.truetype("arialbd.ttf", 15)
lab = {'ironic_hexi_yuanquan': 'Yuanquan', 'ironic_hexi_yumen': 'Yumen', 'ironic_hexi_jianshui': 'Jianshui', 'ironic_hexi_huishui': 'Huishui', 'ironic_region_wuwei_resource_3': 'Rile', 'ironic_region_hanyang_capital': 'Dunhuang', 'ironic_region_hanyang_resource_1': 'Jiuquan', 'ironic_region_xi_resource_1': 'Juyan', 'ironic_region_xi_capital': 'Zhangye'}
for i, n in enumerate(names):
    m = (reg == i) & (f['slot'] == 0)
    if not m.any(): continue
    rr, cc = np.argwhere(m).mean(0)
    if not (c0 <= cc < c1 and r0 <= rr < r1): continue
    x, y = (cc - c0) * S, (r1 - 1 - rr) * S
    d.ellipse([x - 6, y - 6, x + 6, y + 6], fill=(255, 230, 0), outline=(0, 0, 0), width=2)
    t = lab.get(n, n.replace('3k_main_', '').replace('ironic_region_', '').replace('_capital', '').replace('_resource_1', ' res'))
    d.text((x + 8, y - 9), t, fill=(0, 0, 0), font=font); d.text((x + 8, y + 7), f"{int((reg == i).sum())} hexes", fill=(40, 40, 40), font=font)
im.save('previews/r6_regions_hexi.png')
