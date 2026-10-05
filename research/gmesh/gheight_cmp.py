"""BOB's get_height_worker calls (frida_gheight.js) vs the lf formulas: which sampler/formula gives BOB's lf part, and
what the hf output looks like. usage: gheight_cmp.py [max calls]"""
import glob, sys, numpy as np
sys.path.insert(0, '.')
import lf_probe as P
F = np.float32
BIN = 'Z:/Claude/TerryClone/research/bob_re/frida_out/frida_gheight_main190_bin/'
dt = np.dtype([('x', '<f4'), ('z', '<f4'), ('tx', '<i2'), ('ty', '<i2'), ('o', '<u2'), ('valid', 'u1'), ('had', 'u1'),
               ('lf', '<f4'), ('hf', '<f4'), ('var', '<u4'), ('n', '<u4')])
calls = np.concatenate([np.fromfile(f, dt) for f in sorted(glob.glob(BIN + '*_calls.bin'))])
lim = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
print(len(calls), 'calls; valid', calls['valid'].mean(), 'lf nan', np.isnan(calls['lf']).mean(), 'hf nan', np.isnan(calls['hf']).mean())
sub = calls[(~np.isnan(calls['lf']))][:lim]
W, H = P.W, P.H
f2 = F(F(0.0390625) * P.T)


def lf_c(x, z):   # FUN_1803a1e30 compressed sampler + (l·1100)·f' − f'·240
    u = F(x / P.maxX); v = F(F(1) - F(z / P.maxZ))
    fx = F(u * F(W)); fy = F(v * F(H)); x0 = F(np.floor(fx)); y0 = F(np.floor(fy))
    fyu = F(F(v - F(F(1) / F(H))) * F(H)); fxr = F(F(u + F(F(1) / F(W))) * F(W))
    def val(c, r):
        c = int(min(max(c, F(0)), F(W - 1))); r = int(min(max(r, F(0)), F(H - 1)))
        raw = F(F(P.L[r, c]) * P.K)
        return raw if (P.lo == 0 and P.hi == 1) else F(P.lo + F(raw * F(P.hi - P.lo)))
    a = val(fx, fyu); b = val(fxr, fyu); top = F(F(F(b - a) * F(fx - x0)) + a)
    c = val(fx, fy); d = val(fxr, fy); bot = F(F(F(d - c) * F(fx - x0)) + c)
    l = F(F(F(bot - top) * F(fy - y0)) + top)
    return F(F(F(l * F(1100)) * f2) - F(f2 * F(240)))


for name, fn in (('a: FUN_18039eea0 + 1100/240', P.lf_a), ('b: 5500/1200', P.lf_b), ('c: FUN_1803a1e30 + 1100/240', lf_c)):
    ok = sum(fn(F(r['x']), F(r['z'])) == F(r['lf']) for r in sub)
    print(name, f'{ok}/{len(sub)}')
print('lo/hi', P.lo, P.hi, 'W H', W, H, 'maxX maxZ', P.maxX, P.maxZ)
r = sub[0]; print('first', r, P.lf_a(F(r['x']), F(r['z'])), lf_c(F(r['x']), F(r['z'])))
