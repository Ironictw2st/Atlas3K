"""Fit the new-path tile hf term (get_high_frequency_height_new, hf map bilinear via FUN_18039eea0, x this+800) on the
trees whose lf-only height misses by > 1e-4: for each such tree, sample the hf map of every covering tile record in
local tile (u, v) (get_height_worker 0x371030 rotation mapping) and compare with the residual y - lf.
usage: hf_fit.py"""
import collections, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from lf_exact import load_trees, load_lf, lf_height_bob, F
from tree_tiles import read_tile_list, tile_info, TL
import camap_read
HERE = Path(__file__).parent
K = F(1 / 65535)


def sample(raster, u, v, flipv):
    h, w = raster.shape
    if flipv: v = F(1) - v
    fx = F(w) * u; fy = F(h) * v
    x0 = F(int(fx)); y0 = F(int(fy)); x1 = x0 + F(1); ym = y0 - F(1)
    cl = lambda a, m: int(min(max(a, F(0)), F(m)))
    val = lambda c, r: F(raster[r, c]) * K
    a = val(cl(x0, w - 1), cl(ym, h - 1)); b = val(cl(x1, w - 1), cl(ym, h - 1))
    c = val(cl(x0, w - 1), cl(y0, h - 1)); d = val(cl(x1, w - 1), cl(y0, h - 1))
    tx = F(fx - x0); ty = F(fy - y0)
    top = F((b - a) * tx + a); bot = F((d - c) * tx + c)
    return F((bot - top) * ty + top)


if __name__ == "__main__":
    xs, ys, zs = load_trees(); lfr = load_lf()
    lf = lf_height_bob(xs, zs, lfr); res = (ys.astype(np.float64) - lf.astype(np.float64))
    big = np.flatnonzero(np.abs(res) > 1e-4)
    print(f"trees with |y - lf| > 1e-4: {len(big)} ({len(big) / len(xs):.2%})")
    recs = read_tile_list(TL); info = tile_info()
    T = F(F(595.1) / F(1784)); invT = F(F(1) / T)
    tx = (xs * invT).astype(F); ty = ((zs / F(1.15476)).astype(F) * invT).astype(F)
    # index records by covered cell
    cover = collections.defaultdict(list)
    for i, (k, x, y, rot, lo, hi) in enumerate(recs):
        ti = info.get(k)
        if ti is None or ti["w"] is None or not ti["nz"]: continue
        w, h = (ti["h"], ti["w"]) if rot in (0x20, 0x80) else (ti["w"], ti["h"])
        for yy in range(y, y + h + 1):
            for xx in range(x, x + w + 1): cover[(xx, yy)].append(i)
    maps = {}
    stats = collections.Counter(); ratios = {True: [], False: []}
    for i in big:
        cands = cover.get((int(tx[i]), int(ty[i])), [])
        if not cands: stats["no hf tile"] += 1; continue
        stats["hf tile"] += 1
        for j in cands:
            k, X0, Y0, rot, lo, hi = recs[j]; ti = info[k]
            w, h = (ti["h"], ti["w"]) if rot in (0x20, 0x80) else (ti["w"], ti["h"])
            a = F((tx[i] - F(X0)) / F(w)); bq = F((ty[i] - F(Y0)) / F(h))
            u, v = {0x10: (a, bq), 0x00: (a, bq), 0x20: (F(1) - bq, a), 0x40: (F(1) - a, F(1) - bq), 0x80: (bq, F(1) - a)}[rot]
            if k not in maps:
                try: maps[k] = camap_read.read(HERE / "tile_hf/terrain/tiles/campaign" / k / "hf_height_map.compressed_map")
                except Exception: maps[k] = None
            if maps[k] is None: stats["v2 map skipped"] += 1; continue
            r, hd = maps[k]
            for flip in (False, True):
                s = sample(r, u, v, flip); val = F(s * F(hd[4] - hd[1]) + F(hd[1]))
                if val != 0: ratios[flip].append(res[i] / float(val))
    print(dict(stats))
    for flip in (False, True):
        rr = np.array(ratios[flip])
        if len(rr): print(f"flipv={flip}: n {len(rr)}  residual/hf ratio pct", np.percentile(rr, [5, 25, 50, 75, 95]).round(4))
