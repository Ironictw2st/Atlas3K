"""Full tree height model: y = hf * f + lf, hf from the FIRST tile instance (tile_list order) whose bounds contain the
point (get_height_worker loop; masks ignored here), sampled in local (u, v) with BOB's bilinear sampler (no v flip),
f = (1/128) * tile size. usage: hf_model.py"""
import collections, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from lf_exact import load_trees, load_lf, lf_height_bob, F, TILE
from tree_tiles import read_tile_list, tile_info, TL
from hf_fit import sample
import camap_read
HERE = Path(__file__).parent


def build_cover(recs, info, W=1784, H=1405):
    cover = collections.defaultdict(list)
    for i, (k, x, y, rot, lo, hi) in enumerate(recs):
        ti = info.get(k)
        if ti is None or ti["w"] is None: continue
        w, h = (ti["h"], ti["w"]) if rot in (0x20, 0x80) else (ti["w"], ti["h"])
        for yy in range(y, y + h + 1):
            for xx in range(x, x + w + 1): cover[(xx, yy)].append(i)
    return cover


if __name__ == "__main__":
    xs, ys, zs = load_trees(); lfr = load_lf()
    lf = lf_height_bob(xs, zs, lfr)
    recs = read_tile_list(TL); info = tile_info(); cover = build_cover(recs, info)
    T = TILE; invT = F(F(1) / T); f = F(F(F(1) / F(128)) * T)
    tx = (xs * invT).astype(F); ty = ((zs / F(1.15476)).astype(F) * invT).astype(F)
    maps = {}
    out = lf.copy(); used = collections.Counter()
    for i in range(len(xs)):
        cands = sorted(cover.get((int(tx[i]), int(ty[i])), []))
        for j in cands:
            k, X0, Y0, rot, lo, hi = recs[j]; ti = info[k]
            w, h = (ti["h"], ti["w"]) if rot in (0x20, 0x80) else (ti["w"], ti["h"])
            if not (F(X0) <= tx[i] <= F(X0 + w) and F(Y0) <= ty[i] <= F(Y0 + h)): continue
            used[k.split("/")[0] + ("" if ti["nz"] else "(0)")] += 1
            if ti["nz"] and ti["kind"] == "map":
                if k not in maps:
                    try: maps[k] = camap_read.read(HERE / "tile_hf/terrain/tiles/campaign" / k / "hf_height_map.compressed_map")
                    except Exception: maps[k] = None
                if maps[k] is not None:
                    r, hd = maps[k]
                    a = F((tx[i] - F(X0)) / F(F(X0 + w) - F(X0))); b = F((ty[i] - F(Y0)) / F(F(Y0 + h) - F(Y0)))
                    u, v = {0x10: (a, b), 0x00: (a, b), 0x20: (F(1) - b, a), 0x40: (F(1) - a, F(1) - b), 0x80: (b, F(1) - a)}[rot]
                    hv = F(F(sample(r, u, v, False) * F(hd[4] - hd[1])) + F(hd[1]))
                    tot = F(F(hv * f) + lf[i]); out[i] = F(F(tot - lf[i]) + lf[i])
            break
    ex = out.view(np.int32) == ys.view(np.int32)
    print(f"lf only: exact {(lf.view(np.int32) == ys.view(np.int32)).mean():.4%};  lf + hf: exact {ex.mean():.4%}, "
          f"within 1e-5 {(np.abs(out - ys) <= 1e-5).mean():.4%}, >1e-3 {(np.abs(out - ys) > 1e-3).mean():.4%}")
    print("first covering tile by set:", used.most_common(12))
