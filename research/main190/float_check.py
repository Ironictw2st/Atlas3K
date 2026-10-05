import re, sys, glob, numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
sys.path[:0] = ['.', '../guandu', '..']
from hexgrid import HX, HZ
U2W = 0.000218712; W0 = 3.12725
def run(d, tif, label):
    hgt = np.array(Image.open(tif)); H8, W8 = hgt.shape
    terry = open(glob.glob(d + '/*.terry')[0], encoding='utf-8', errors='replace').read()
    used = set(re.findall(r'id="([0-9a-f]+)"', terry))
    rows = []
    for p in glob.glob(d + '/*.layer'):
        lid = p.split('.')[-2]
        if lid not in used: continue
        t = open(p, encoding='utf-8', errors='replace').read()
        for m in re.finditer(r'<entity id="([0-9a-f]+)">(.*?)</entity>', t, re.S):
            e = m.group(2)
            mp = re.search(r'model_path="([^"]*)"', e)
            if not mp: continue
            mpl = mp.group(1).lower()
            if '/mountains/' not in mpl and 'rocks/' not in mpl: continue
            pm = re.search(r'position="([^ ]+) ([^ ]+) ([^"]+)"', e)
            x, y, z = map(float, pm.groups())
            # min ground under a small footprint (3x3 hexes) and centre ground
            px = int(round(x / HX * 8 + 4)); py = int(round(H8 - 1 - (z / HZ * 8 + 4)))
            py = min(max(py, 0), H8 - 1); px = min(max(px, 0), W8 - 1)
            g = float(hgt[py, px]) * U2W - W0
            win = hgt[max(0, py - 12):py + 13, max(0, px - 12):px + 13]
            gmin = float(win.min()) * U2W - W0
            rows.append((y - g, y - gmin, x, z, mpl.split('/')[-1], lid, m.group(1)))
    dy = np.array([r[0] for r in rows]); dmin = np.array([r[1] for r in rows])
    print(label, len(rows), 'y-ground pct', np.percentile(dy, [1, 5, 50, 95, 99]).round(2), ' >0.3 above ground:', int((dy > 0.3).sum()), ' >0.3 above min-ground (whole base floating):', int((dmin > 0.3).sum()))
    return rows
o = run('Z:/Claude/TerryClone/output/backups/main190_originals_20260929_130639/ak190E_terrain_3k_dlc07_main_map',
        'Z:/Claude/TerryClone/output/backups/main190_originals_20260929_130639/ak190E_terrain_3k_dlc07_main_map/3k_dlc07_main_map.height.191fd803c1a801d.tif', 'ORIGINAL')
n = run('ak/3k_dlc07_main_map', 'terrain/3k_dlc07_main_map.height.191fd803c1a801d.tif', 'CURRENT')
import pickle; pickle.dump(n, open('/tmp/float_rows.pkl', 'wb'))
bad = sorted([r for r in n if r[1] > 0.3], key=lambda r: -r[1])
import collections
print('floating by model', collections.Counter(r[4] for r in bad).most_common(12))
print('by id prefix (0e = north_dress)', collections.Counter(r[6][:2] for r in bad).most_common(5))
for r in bad[:15]: print([round(v, 2) if isinstance(v, float) else v for v in r])

om = {r[6]: r for r in o}
pairs = [(r, om[r[6]]) for r in n if r[6] in om]
d = np.array([r[0] - q[0] for r, q in pairs])        # change in (y - ground): + = now higher above ground than in 190E
print('matched', len(pairs), 'change pct', np.percentile(d, [1, 5, 50, 95, 99]).round(2), ' raised >0.3:', int((d > 0.3).sum()), ' >0.6:', int((d > 0.6).sum()), ' sunk < -0.3:', int((d < -0.3).sum()))
fl = sorted([(dd, r) for dd, (r, q) in zip(d, pairs) if dd > 0.3], key=lambda t: -t[0])
print(collections.Counter(r[4] for _, r in fl).most_common(10))
for dd, r in fl[:20]: print(round(dd, 2), round(r[2], 1), round(r[3], 1), r[4], r[5])
newp = [r for r in n if r[6] not in om]
dn = np.array([r[0] for r in newp]); print('new (north_dress) props', len(newp), 'y-ground pct', np.percentile(dn, [1, 50, 99]).round(2) if len(dn) else None)
pickle.dump(fl, open('/tmp/float_fl.pkl', 'wb'))
