"""Analyse a Frida height_split dump (frida_trees.js) against the shipped vanilla tree list: input coordinates BOB
used, how y relates to (hf, lf), and how our lf sampler compares with BOB's lf part.
usage: hs_dump_analyze.py <frida jsonl>"""
import json, sys
import numpy as np
from lf_exact import load_trees, load_lf, F, lf_height_bob

rows = []
for l in open(sys.argv[1], encoding="utf-8"):
    d = json.loads(l)
    if d["kind"] == "hs": rows += d["rows"]
R = np.array([r[:4] for r in rows], np.float64).astype(F)
hx, hz, hf, lf = R[:, 0], R[:, 1], R[:, 2], R[:, 3]
xs, ys, zs = load_trees()
print(f"dump rows {len(R):,}, trees {len(xs):,}, input encoding ptr={rows[0][4]}")
# pair by position: the dump's input (x, z') vs the tree (x, z)
order = {}
for i, (x, z) in enumerate(zip(xs.view(np.int32), zs.view(np.int32))): order[(int(x))] = order.get(int(x), []) + [i]
print("dump x == tree x (same order):", bool((hx.view(np.int32) == xs.view(np.int32)).all()) if len(hx) == len(xs) else "length differs")
ratio = (zs.astype(np.float64) / hz.astype(np.float64))
print("z_tree / z_input: pct", np.percentile(ratio, [0, 50, 100]))
s = (hf + lf).astype(F)
print("y == hf + lf (float32):", f"{(s.view(np.int32) == ys.view(np.int32)).mean():.4%}")
s2 = ((hf - lf + lf)).astype(F)
raster = load_lf()
ours = lf_height_bob(xs, zs, raster)
print("our lf == BOB lf part:", f"{(ours.view(np.int32) == lf.view(np.int32)).mean():.4%}",
      " hf == 0 share:", f"{(hf == 0).mean():.4%}")
np.save("hs_dump.npy", R)
