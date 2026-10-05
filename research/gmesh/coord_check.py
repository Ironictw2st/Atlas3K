"""Grid coordinates BOB queries (get_height_worker dump) vs coordinate formulas: x = I·ext/total variants."""
import sys, numpy as np
sys.path.insert(0, '.')
import gheight_cmp as G, lf_probe as P
F = np.float32
c = G.calls
tw, th = P.W // 4, P.H // 4
total = 2 * max(tw, th)
T = F(595.1) / F(1784)
exts = {'tw*T': F(F(max(tw, th)) * T), 'dbl': F(max(tw, th) * 595.1 / 1784)}
xs = np.unique(c['x'])
print('distinct x', len(xs), xs[:8])
for en, ext in exts.items():
    forms = {
        'double I*ext/total': lambda I: F(I * float(ext) / total),
        'f32 I*(ext/total)': lambda I: F(F(I) * F(ext / F(total))),
        'f32 (I*ext)/total': lambda I: F(F(F(I) * ext) / F(total)),
        'f32 (I+0)*(ext/f(total))': lambda I: F(F(F(I) + F(0)) * F(ext / F(total))),
    }
    for fn, f in forms.items():
        grid = {f(I) for I in range(total + 1)}
        hit = sum(1 for x in xs[:20000] if F(x) in grid)
        print(en, fn, hit, min(len(xs), 20000))
