"""Which lf formula / grid coordinate reproduces BOB's global-mesh heights? Takes one BOB grid (merge call index) and
tests variants on points where native and BOB differ. Needs the lf raster cached as .npy (decoded once).
usage: lf_probe.py <merge index> [mesh col] [mesh row]"""
import os, sys, struct, numpy as np
sys.path.insert(0, '.'); sys.path.insert(0, '..')
from grid_cmp import *
import compressed_map as C
F = np.float32
INP = ROOT + '/output/bob_runs/frida_gmesh_main190_bob_terrain/inputs/'
cache = INP + 'lf.npy'
if not os.path.exists(cache):
    r, hdr = C.decode(INP + 'lf_height_map.compressed_map'); np.save(cache, r); np.save(INP + 'lf_hdr.npy', np.array(hdr, np.float32))
L = np.load(cache); hdr = np.load(INP + 'lf_hdr.npy')
H, W = L.shape
tl = open(INP + 'tile_list.bin', 'rb').read()
T = F(595.1) / F(1784)
tilesW, tilesH = W // 4, H // 4
maxX, maxZ = F(tilesW * T), F(tilesH * T)
lo, hi = F(hdr[1]), F(hdr[4])
K = F(1) / F(65535)


def val(c, r):
    c = min(max(c, F(0)), F(W - 1)); r = min(max(r, F(0)), F(H - 1))
    return F(F(F(F(L[int(r), int(c)]) * K) * F(hi - lo)) + lo)


def sample(u, v):
    fx = F(F(W) * u); fy = F(F(H) * v); fx0 = F(np.floor(fx)); fy0 = F(np.floor(fy)); xi = F(int(fx)); yi = F(int(fy))
    a = val(xi, F(yi - 1)); b = val(F(xi + 1), F(yi - 1)); top = F(F(F(b - a) * F(fx - fx0)) + a)
    c = val(xi, yi); d = val(F(xi + 1), yi); bot = F(F(F(d - c) * F(fx - fx0)) + c)
    return F(F(F(bot - top) * F(fy - fy0)) + top)


def lf_a(x, z):     # TileHfHeight: (l·1100)·f' − f'·240
    u = F(x / maxX); v = F(F(1) - F(z / maxZ)); l = sample(u, v); f = F(F(0.0390625) * T)
    return F(F(F(l * F(1100)) * f) - F(f * F(240)))


def lf_b(x, z):     # (l·5500)·f − f·1200, f = T/128
    u = F(x / maxX); v = F(F(1) - F(z / maxZ)); l = sample(u, v); f = F(F(F(1) / F(128)) * T)
    return F(F(F(l * F(5500)) * f) - F(f * F(1200)))


if __name__ == "__main__":
    seq = bob_sequence(); h, mg = bob_dumps()
    mi = int(sys.argv[1]); kind, k, name = seq[mi]
    b = load_grid(h[mi]); n = h[mi]['n']; cells = n - 1
    col, row = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else (k % 16, k // 16)
    total = 2 * max(tilesW, tilesH); ext = float(F(max(tilesW, tilesH) * T))
    coords = {
        'double': lambda I: F(I * ext / total),
        'f32cell': lambda I: F(F(I) * F(F(ext) / F(total))),
        'f32div': lambda I: F(F(F(I) * F(ext)) / F(total)),
    }
    rng = np.random.default_rng(1); pts = [(rng.integers(0, n), rng.integers(0, n)) for _ in range(400)]
    for cn, cf in coords.items():
        for fn, lf in (('a', lf_a), ('b', lf_b)):
            ok = tot = 0
            for j, i in pts:
                if b[j, i] == -20: continue
                tot += 1; ok += lf(cf(col * cells + i), cf(row * cells + j)) == b[j, i]
            print(kind, name, 'coord', cn, 'lf', fn, f'{ok}/{tot}')
