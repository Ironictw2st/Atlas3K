"""Which lf raster did BOB sample? For BOB's valid hf-free get_height_worker calls (frida_gheight3 dump), compute the lf
from each candidate source (pack / working compressed maps, raw tif, pack .dds) and count exact matches."""
import glob, os, sys, numpy as np
sys.argv = [sys.argv[0]]
sys.path.insert(0, '.'); sys.path.insert(0, '..')
import compressed_map as C
F = np.float32
BIN = 'Z:/Claude/TerryClone/research/bob_re/frida_out/frida_gheight3_main190_bin/'
dt = np.dtype([('x', '<f4'), ('z', '<f4'), ('tx', '<i2'), ('ty', '<i2'), ('o', '<u2'), ('valid', 'u1'), ('flag', 'u1'),
               ('lf', '<f4'), ('res', '<f4'), ('hfo', '<f4'), ('n', '<u4')])
c = np.concatenate([np.fromfile(f, dt) for f in sorted(glob.glob(BIN + '*_calls.bin'))])
v = c[(c['valid'] == 1)]
rng = np.random.default_rng(5); s = v[rng.choice(len(v), 2000, replace=False)]
T = F(595.1) / F(1784); Tp = F(F(F(1) / F(2956)) * F(F(2956) * T)); maxX = F(F(2956) * Tp); maxZ = F(F(2267) * Tp)
f = F(F(0.0390625) * Tp); K = F(1) / F(65535)
srcs = {}
srcs['pack'] = np.load('Z:/Claude/TerryClone/output/mesh_parity/lf_pack.npy')
srcs['working'] = np.load('Z:/Claude/TerryClone/output/bob_runs/frida_gmesh_main190_bob_terrain/inputs/lf.npy')
from PIL import Image; Image.MAX_IMAGE_PIXELS = None
srcs['tif'] = np.array(Image.open(r'C:/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/assembly_kit_190E/raw_data/terrain/campaigns/3k_190e_expanded_map/lf_heights.tif'))
dds = r'C:/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/assembly_kit_190E/working_data/terrain/campaigns/3k_190e_expanded_map/lf_height_map.dds'
if os.path.exists(dds): srcs['working_dds'] = np.frombuffer(open(dds, 'rb').read(), '<u2', offset=128, count=11824 * 9068).reshape(9068, 11824)


def sample(L, u, v):
    H, W = L.shape
    def val(cc, r):
        cc = min(max(cc, F(0)), F(W - 1)); r = min(max(r, F(0)), F(H - 1))
        return F(F(L[int(r), int(cc)]) * K)
    fx = F(F(W) * u); fy = F(F(H) * v); fx0 = F(np.floor(fx)); fy0 = F(np.floor(fy)); xi = F(int(fx)); yi = F(int(fy))
    a = val(xi, F(yi - 1)); b = val(F(xi + 1), F(yi - 1)); top = F(F(F(b - a) * F(fx - fx0)) + a)
    cc = val(xi, yi); d = val(F(xi + 1), yi); bot = F(F(F(d - cc) * F(fx - fx0)) + cc)
    return F(F(F(bot - top) * F(fy - fy0)) + top)


for name, L in srcs.items():
    ok = 0
    for r in s:
        u = F(r['x'] / maxX); vv = F(F(1) - F(r['z'] / maxZ))
        ok += F(F(F(sample(L, u, vv) * F(1100)) * f) - F(f * F(240))) == r['res']
    print(name, ok, len(s))
