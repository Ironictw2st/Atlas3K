"""Which AMD call group (Frida dump) is which tile DDS, the mip rule, and how mip 0 relates to the blend/height TIFs.
usage: tile_dds_inspect.py <frida jsonl> <corpus project dir>"""
import glob, json, sys
import numpy as np, tifffile

rows = [json.loads(l) for l in open(sys.argv[1])]
proj = sys.argv[2]
src = [r for r in rows if r['kind'] == 'convert_src']
dst = [r for r in rows if r['kind'] == 'convert_dst']
groups = []
for i, r in enumerate(src):
    if i == 0 or r['src']['w'] > src[i - 1]['src']['w']: groups.append([])
    groups[-1].append(i)
for g in groups:
    blob = b''.join(open(dst[i]['file'], 'rb').read() for i in g)
    for f in ('blend0.dds', 'blend1.dds', 'normal.dds', 'lf_normal.dds'):
        try:
            d = open(f'{proj}/bob_run1/tile/{f}', 'rb').read()
            if d[128:] == blob: print('group', g[0], '->', f)
        except FileNotFoundError: pass
    # mip rule
    for k in range(1, len(g)):
        a = np.frombuffer(open(src[g[k - 1]]['file'], 'rb').read(), np.uint8).reshape(src[g[k - 1]]['src']['h'], src[g[k - 1]]['src']['w'], 4).astype(int)
        b = np.frombuffer(open(src[g[k]]['file'], 'rb').read(), np.uint8).reshape(src[g[k]]['src']['h'], src[g[k]]['src']['w'], 4).astype(int)
        h2, w2 = b.shape[:2]
        box = a[0:2 * h2:2, 0:2 * w2:2] + a[1:2 * h2:2, 0:2 * w2:2] + a[0:2 * h2:2, 1:2 * w2:2] + a[1:2 * h2:2, 1:2 * w2:2]
        bad = ((box + 2) // 4 != b).sum()
        if bad: print('  mip', k, a.shape[:2], '->', b.shape[:2], 'box mismatches', bad)
blend = tifffile.imread(glob.glob(proj + '/src/tile/*.blend.*.tif')[0])
for g in groups:
    m0 = np.frombuffer(open(src[g[0]]['file'], 'rb').read(), np.uint8).reshape(1280, 1280, 4)
    print('group', g[0], 'mip0 channel ranges', [(int(m0[..., c].min()), int(m0[..., c].max())) for c in range(4)])
    for c in range(4):
        for t in range(8):
            for flip in (False, True):
                bt = blend[::-1, :, t] if flip else blend[..., t]
                if (m0[..., c] == bt).all(): print('   ch', c, '== blend channel', t, 'flip' if flip else '')
