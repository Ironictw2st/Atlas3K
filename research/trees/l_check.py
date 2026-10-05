"""Run-3 dump (frida_trees3.js): BOB's sampled l per tree. Check our sampler l == BOB l, then the final scaling with the
TERRAIN_RENDER_SETUP constants read from memory (+0x8c = 1100, +0x84 = 240, +0x324 = tile 0.3335762).
usage: l_check.py <jsonl>"""
import json, sys, collections
import numpy as np
from lf_exact import load_lf, F

T, S = [], []
cur = []
for l in open(sys.argv[1], encoding="utf-8"):
    d = json.loads(l)
    if d["kind"] != "rows": continue
    for r in d["rows"]:
        if r[0] == "S": cur.append(r[1:])
        else: T.append(r[1:]); S.append(cur); cur = []
T = np.array(T, np.float64).astype(F); x, z, hf, lf = T.T
lfmap = collections.Counter(s[0] for ss in S for s in ss).most_common(1)[0][0]
rowsS = [next((s for s in ss if s[0] == lfmap), None) for ss in S]
ok = np.array([r is not None for r in rowsS])
U = np.array([r[1] if r else np.nan for r in rowsS], np.float64).astype(F)
V = np.array([r[2] if r else np.nan for r in rowsS], np.float64).astype(F)
Lb = np.array([r[3] if r else np.nan for r in rowsS], np.float64).astype(F)
raster = load_lf(); h, w = raster.shape; K = F(1 / 65535)
U2, V2 = U[ok], V[ok]
fx = (F(w) * U2).astype(F); fy = (F(h) * V2).astype(F)
x0 = fx.astype(np.int64).astype(F); y0 = fy.astype(np.int64).astype(F)
x1 = (x0 + F(1)).astype(F); ym = (y0 - F(1)).astype(F)
cl = lambda a, m: np.clip(a, F(0), F(m)).astype(np.int64)
val = lambda c, r: (raster[r, c].astype(F) * K).astype(F)
a = val(cl(x0, w - 1), cl(ym, h - 1)); b = val(cl(x1, w - 1), cl(ym, h - 1))
c = val(cl(x0, w - 1), cl(y0, h - 1)); d = val(cl(x1, w - 1), cl(y0, h - 1))
tx = (fx - x0).astype(F); ty = (fy - y0).astype(F)
top = ((b - a).astype(F) * tx + a).astype(F); bot = ((d - c).astype(F) * tx + c).astype(F)
L = ((bot - top).astype(F) * ty + top).astype(F)
print(f"trees {len(T):,}; with an lf sample {ok.mean():.4%}")
print(f"our sampler l == BOB l: {(L.view(np.int32) == Lb[ok].view(np.int32)).mean():.4%}")
tile = F(0.3335762321949005)
cands = {"(1/25.6)*tile": F(F(F(1) / F(25.6)) * tile), "0.0390625*tile": F(F(0.0390625) * tile),
         "5*f0": F(F(5) * F(0.0026060643140226603)), "tile/25.6": F(tile / F(25.6))}
for name, f2 in cands.items():
    hgt = ((Lb[ok] * F(1100)).astype(F) * f2 - (f2 * F(240)).astype(F)).astype(F)
    print(f"  f2 = {name:16s} {float(f2)!r}: lf == BOB lf {(hgt.view(np.int32) == lf[ok].view(np.int32)).mean():.4%}")
