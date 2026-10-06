"""ground_types.dds (1024x1024 L8, EMPIREUTILITY::GROUND_TYPE per pixel) from the tile's blend TIF (1280x1280x8) and the
.terry texture channels mapped through db ground_type_to_texture_groups. Searches crop offset and per-pixel rule.
usage: ground_types_fit.py <corpus project dir>"""
import glob, re, sys
import numpy as np, tifffile

ENUM = ['forest', 'grass', 'mud', 'sand', 'scrub', 'rock', 'deep_water', 'shallow_water', 'road', 'wooden_floor', 'snow',
        'sharp_stones', 'burnt', 'wet_mud', 'long_grass', 'light_forest', 'caltrops', 'oil']
proj = sys.argv[1]
tex2gt = {}
for line in open(r'Z:/Claude/BattleMaps/db/ground_type_to_texture_groups_tables/data__.tsv', encoding='utf-8').read().splitlines()[2:]:
    a = line.split('\t'); tex2gt[a[0]] = ENUM.index(a[1])
terry = open(glob.glob(proj + '/src/tile/*.terry')[0], encoding='utf-8').read()
chans = [re.search(f'texture_channel_{i}="([^"]*)"', terry).group(1) for i in range(8)]
gt = np.array([tex2gt.get(c, 1) for c in chans]); print(chans, gt)
blend = tifffile.imread(glob.glob(proj + '/src/tile/*.blend.*.tif')[0]).astype(np.int64)
b = np.frombuffer(open(proj + '/bob_run1/tile/ground_types.dds', 'rb').read(), np.uint8, 1024 * 1024, 128).reshape(1024, 1024)
for off in (127, 128, 129):
    w = blend[off:off + 1024, off:off + 1024]
    for flip in (False, True):
        ww = w[::-1] if flip else w
        rules = {'argmax_first': gt[np.argmax(ww, axis=2)],
                 'argmax_last': gt[7 - np.argmax(ww[..., ::-1], axis=2)],
                 'last_nonzero': gt[np.where(ww > 0, np.arange(8), 0).max(axis=2)]}
        for k, v in rules.items(): print(off, flip, k, int((v != b).sum()))
