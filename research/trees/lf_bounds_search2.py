"""Wider search over how the lf extents (maxX, maxZ) and the z' conversion may be represented. usage: lf_bounds_search2.py"""
import itertools
import numpy as np
from lf_exact import load_trees, load_lf, F, TILE
from lf_ulp_probe import height_from as _h  # noqa (reuses sampler; patched below)
import lf_ulp_probe as P

xs, ys, zs = load_trees()
T = TILE
Tq = F(T / F(4)); Tq2 = F(T * F(0.25))
cand_x = {"1784*T": F(F(1784) * T), "595.1": F(595.1), "7136*(T/4)": F(F(7136) * Tq), "7136*T*0.25": F(F(F(7136) * T) * F(0.25)),
          "1784*595.1/1784": F(F(F(1784) * F(595.1)) / F(1784))}
cand_z = {"1405*T": F(F(1405) * T), "5620*(T/4)": F(F(5620) * Tq), "5620*T*0.25": F(F(F(5620) * T) * F(0.25)),
          "1405*595.1/1784": F(F(F(1405) * F(595.1)) / F(1784)), "dbl": F(1405 * 595.1 / 1784)}
cand_zt = {"z/1.15476": lambda z: (z / F(1.15476)).astype(F), "z*(1/1.15476)": lambda z: (z * F(F(1) / F(1.15476))).astype(F),
           "z*0.8659808": lambda z: (z * F(0.8659808)).astype(F), "dbl": lambda z: (z.astype(np.float64) / 1.15476).astype(F)}
res = []
for (kx, mx), (kz, mz), (kt, zf) in itertools.product(cand_x.items(), cand_z.items(), cand_zt.items()):
    P.maxX, P.maxZ = mx, mz
    hgt = P.height_from(xs, zf(zs))
    res.append(((hgt.view(np.int32) == ys.view(np.int32)).mean(), kx, kz, kt))
for r in sorted(res, reverse=True)[:8]: print(f"{r[0]:.4%}", r[1:])
print("distinct float values: maxX", {k: float(v) for k, v in cand_x.items()}, "maxZ", {k: float(v) for k, v in cand_z.items()})
