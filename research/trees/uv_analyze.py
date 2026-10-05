"""From frida_trees2.js rows: per tree, the sampler calls (map, u, v). Check (1) our sampler on BOB's (u, v) == BOB's lf,
(2) BOB's (u, v) vs our u = x/maxX, v = 1 - (z/1.15476)/maxZ, and search the exact u/v formula.
usage: uv_analyze.py <jsonl>"""
import json, sys, collections
import numpy as np
from lf_exact import load_lf, F, TILE

trees, samples = [], []
cur = []
for l in open(sys.argv[1], encoding="utf-8"):
    d = json.loads(l)
    if d["kind"] != "rows": continue
    for r in d["rows"]:
        if r[0] == "S": cur.append((r[1], r[2], r[3]))
        else: trees.append(r[1:]); samples.append(cur); cur = []
T = np.array(trees, np.float64).astype(F)
x, z, hf, lf = T.T
print("samples per tree:", collections.Counter(len(s) for s in samples).most_common(5))
maps = collections.Counter(s[0] for ss in samples for s in ss); print("maps sampled:", maps.most_common(4))
first_map = maps.most_common(1)[0][0]
uv = np.array([[s[1], s[2]] for ss in samples for s in ss if s[0] == first_map][:len(T)], np.float64).astype(F)
# take, per tree, the first sample on the most common map
U, V = [], []
for ss in samples:
    s = next((s for s in ss if s[0] == first_map), (None, np.nan, np.nan)); U.append(s[1]); V.append(s[2])
U = np.array(U, np.float64).astype(F); V = np.array(V, np.float64).astype(F)
raster = load_lf(); h, w = raster.shape
K = F(1 / 65535)


def sample(u, v):
    fx = (F(w) * u).astype(F); fy = (F(h) * v).astype(F)
    x0 = fx.astype(np.int64).astype(F); y0 = fy.astype(np.int64).astype(F)
    x1 = (x0 + F(1)).astype(F); ym = (y0 - F(1)).astype(F)
    cl = lambda a, m: np.clip(a, F(0), F(m)).astype(np.int64)
    val = lambda c, r: (raster[r, c].astype(F) * K).astype(F)
    a = val(cl(x0, w - 1), cl(ym, h - 1)); b = val(cl(x1, w - 1), cl(ym, h - 1))
    c = val(cl(x0, w - 1), cl(y0, h - 1)); d = val(cl(x1, w - 1), cl(y0, h - 1))
    tx = (fx - x0).astype(F); ty = (fy - y0).astype(F)
    top = ((b - a).astype(F) * tx + a).astype(F); bot = ((d - c).astype(F) * tx + c).astype(F)
    return ((bot - top).astype(F) * ty + top).astype(F)


f = F(F(F(1) / F(128)) * TILE)
lf_from_uv = (((sample(U, V) * F(5500)).astype(F) * f) - (f * F(1200)).astype(F)).astype(F)
ok = np.isfinite(U)
print("our sampler on BOB's (u,v) == BOB lf:", f"{(lf_from_uv[ok].view(np.int32) == lf[ok].view(np.int32)).mean():.4%}")
maxX = F(F(1784) * TILE); maxZ = F(F(1405) * TILE)
ou = (x / maxX).astype(F); ov = (F(1) - ((z / F(1.15476)).astype(F) / maxZ).astype(F)).astype(F)
print("u equal:", f"{(ou[ok].view(np.int32) == U[ok].view(np.int32)).mean():.4%}", " v equal:", f"{(ov[ok].view(np.int32) == V[ok].view(np.int32)).mean():.4%}")
np.save("uv_dump.npy", np.c_[x, z, hf, lf, U, V])
# fit: u = a*x + b ? v = c*z + d ? (float64 least squares as a hint)
A = np.c_[x.astype(np.float64), np.ones(len(x))]
print("u ~ a*x+b:", np.linalg.lstsq(A[ok], U[ok].astype(np.float64), rcond=None)[0])
B = np.c_[z.astype(np.float64), np.ones(len(z))]
print("v ~ c*z+d:", np.linalg.lstsq(B[ok], V[ok].astype(np.float64), rcond=None)[0])
