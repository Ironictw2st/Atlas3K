"""Global mesh: BOB's per-mesh height grids (Frida dump of FUN_180147860's input, frida_gmesh.js) vs the native
builder's (ATLAS3K_GMESH_DUMP). BOB merge order -> (kind, mesh k) from bob.log ("Building mesh k" + TRIANGLE_MERGER).
usage: grid_cmp.py [k-limit]"""
import json, re, sys, glob, os, numpy as np
ROOT = 'Z:/Claude/TerryClone'
LOG = os.environ.get('GMESH_BOBLOG', ROOT + '/output/bob_runs/20261005_025700_frida_gmesh_main190/bob.log')
RUN = os.environ.get('GMESH_RUN', 'frida_gmesh_main190')
JL = ROOT + f'/research/bob_re/frida_out/{RUN}.jsonl'
BIN = ROOT + f'/research/bob_re/frida_out/{RUN}_bin/'
NAT = os.environ.get('GMESH_NAT', ROOT + '/output/mesh_parity/gmesh_native_dump/')


def bob_sequence():
    """[(kind, k, file name or None)] per TRIANGLE_MERGER call, in order."""
    seq = []; kind = None; k = None
    for line in open(LOG, encoding='utf-8', errors='replace'):
        if line.startswith('Building the campaign global meshes'): kind = 'Land' if kind is None else 'Sea'
        m = re.match(r'Building mesh (\d+) of', line)
        if m: k = int(m.group(1))
        if line.startswith('TRIANGLE_MERGER starting'): seq.append([kind, k, None])
        m = re.search(r'global_meshes\\(\w+)\.rigid_model_v2', line)
        if m and seq: seq[-1][2] = m.group(1)
    return seq


def bob_dumps():
    h, mg = [], []
    for l in open(JL, encoding='utf-8'):
        d = json.loads(l)
        if d['kind'] == 'heights': h.append(d)
        elif d['kind'] == 'merged': mg.append(d)
    return h, mg


def load_grid(d):
    n = d['n']; return np.fromfile(BIN + d['file'], np.float32).reshape(n, n)


if __name__ == "__main__":
    seq = bob_sequence(); h, mg = bob_dumps()
    print(len(seq), len(h), len(mg))
    nat = sorted(glob.glob(NAT + '*.y.bin'))
    per = max(int(os.path.basename(f).split('_')[2].split('.')[0]) for f in nat) + 1
    print('native meshes per axis', per)
    tot = eq = 0; holes_eq = 0; stats = []
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else len(seq)
    for (kind, k, name), d in list(zip(seq, h))[:lim]:
        b = load_grid(d); n = d['n']
        row, col = divmod(k, per)
        p = NAT + f'{kind}_{row}_{col}.y.bin'
        if not os.path.exists(p): print('no native', kind, k, name); continue
        a = np.fromfile(p, np.float32).reshape(n, n)
        e = (a == b); hb = b == -20; ha = a == -20
        tot += a.size; eq += e.sum(); holes_eq += (hb == ha).sum()
        both = ~hb & ~ha
        d_ulp = np.abs(a[both].view(np.int32).astype(np.int64) - b[both].view(np.int32).astype(np.int64)) if both.any() else np.array([0])
        stats.append((kind, k, name, e.mean(), (hb == ha).mean(), int(hb.sum()), int(ha.sum()), np.median(d_ulp), np.abs(a[both] - b[both]).max() if both.any() else 0))
    for s in stats[:12]: print(s)
    worst = sorted(stats, key=lambda s: s[4])[:5]
    print('worst holes', worst)
    print(f'grid values equal {eq}/{tot} = {eq/tot:.2%}; hole pattern equal {holes_eq/tot:.2%}')
