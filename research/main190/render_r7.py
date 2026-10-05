"""Round-7 preview: hex/map.hex regions with on-screen names (190E names, r7 renames, new towns).
yellow = new town, orange = moved existing town (thin line from its old site), white = unchanged."""
import sys, json, numpy as np
sys.path[:0] = ['.', '../guandu', '..']
from PIL import Image, ImageDraw, ImageFont
from regions_plan import load
BOX = dict(east=(770, 1070, 380, 700), hebei=(780, 960, 540, 720), north=(600, 1060, 620, 820))
f, names, w, h = load('hex/map.hex'); reg = f['region']
reg_names = json.load(open('research_r6/name_registry.json', encoding='utf-8'))['region_names']
onscreen = {}
for nm, keys in reg_names.items():
    for k in keys:
        if k.startswith('190E:'): onscreen[k[5:]] = nm
cand = json.load(open('research_r6/candidates.json', encoding='utf-8')); onscreen.update(cand.get('renames_r7', {}))
nj = json.load(open('regions_new.json', encoding='utf-8'))
new = {n: pv['names'][n] for pv in nj['provinces'].values() for n in pv['regions']}; onscreen.update(new)
moved = nj.get('moved_r7', {})
for tag, (c0, c1, r0, r1) in BOX.items():
    S = 3
    rng = np.random.default_rng(5); pal = rng.integers(110, 235, (len(names) + 2, 3)).astype(np.uint8)
    img = pal[np.clip(reg, 0, None)].copy()
    img[f['terr'] == 1] = (70, 105, 150); imp = f['imp'] == 1; img[imp] = (img[imp] * 0.62).astype(np.uint8)
    img[(f['river'] > 0) & (f['terr'] != 1)] = (90, 130, 190)
    e = np.zeros(reg.shape, bool); e[:, 1:] |= reg[:, 1:] != reg[:, :-1]; e[1:] |= reg[1:] != reg[:-1]; img[e & (f['terr'] != 1)] = (25, 25, 25)
    img[(f['road'] > 0) & (f['terr'] != 1)] = (150, 60, 40)
    sub = img[r0:r1, c0:c1][::-1]; im = Image.fromarray(sub).resize(((c1 - c0) * S, (r1 - r0) * S), Image.NEAREST); d = ImageDraw.Draw(im)
    font = ImageFont.truetype("arialbd.ttf", 13)
    P = lambda c, r: ((c - c0) * S, (r1 - 1 - r) * S)
    for k, m in moved.items():
        if m.get('old_site'): d.line([P(*m['old_site']), P(*m['site'])], fill=(255, 140, 0), width=2)
    for i, n in enumerate(names):
        m = (reg == i) & (f['slot'] == 0)
        if not m.any(): continue
        rr, cc = np.argwhere(m).mean(0)
        if not (c0 <= cc < c1 and r0 <= rr < r1): continue
        x, y = P(cc, rr)
        col = (255, 230, 0) if n in new else (255, 140, 0) if n in moved else (255, 255, 255)
        d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=col, outline=(0, 0, 0), width=2)
        t = onscreen.get(n, n.replace('3k_main_', ''))
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)): d.text((x + 7 + dx, y - 8 + dy), t, fill=(255, 255, 255), font=font)
        d.text((x + 7, y - 8), t, fill=(0, 0, 0), font=font)
    im.save(f'previews/r7_regions_{tag}.png'); print(tag, im.size)
