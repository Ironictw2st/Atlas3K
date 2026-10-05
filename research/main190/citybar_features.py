#!/usr/bin/env python3
"""Per-town features (stock 190E vs a given map.hex) to find what separates towns with a missing city bar."""
import sys, json, numpy as np
from pathlib import Path
HERE = Path(__file__).parent; sys.path[:0] = [str(HERE), str(HERE.parent), str(HERE.parent / "guandu")]
import town_fix as T
BAD = {"3k_main_taiyuan_resource_1", "3k_main_shangyong_capital", "3k_main_shangyong_resource_1", "3k_main_baxi_capital",
       "3k_main_baxi_resource_2", "3k_main_chengdu_resource_3", "3k_main_chengdu_resource_2", "3k_dlc06_kui_pass",
       "3k_main_badong_capital", "3k_main_jingzhou_capital", "3k_main_zhongshan_resource_1", "3k_main_changsha_resource_3",
       "3k_main_changsha_capital", "3k_main_anding_capital", "3k_main_luoyang_capital", "3k_main_kuaiji_resource_2",
       "3k_main_yulin_capital", "3k_main_wuling_capital", "3k_main_zangke_capital", "3k_main_lingling_resource_2",
       "3k_main_poyang_resource_3", "3k_main_dongjun_resource_1", "3k_main_donglai_capital"}


def hazard(f, w, h, edges=True, sea=True):
    hz = (f["imp"] > 0) | (f["river"] > 0) | np.isin(f["terr"], (2, 3) if not sea else (1, 2, 3))
    if edges:
        for r, c in zip(*np.nonzero(f["river"] > 0)):
            for d, nc, nr in T.nbrs(int(c), int(r), w, h):
                if (f["river"][r, c] >> d) & 1: hz[nr, nc] = True
    return hz


def feats(path):
    _, _, w, h, _, f, names = T.load(path)
    hz = hazard(f, w, h)
    out = {}
    for k in sorted({int(k) for k in np.unique(f["region"][f["slot"] == 0])}):
        F = T.footprint(f, k); R1 = T.ring(F, w, h); R2 = T.ring(F | R1, w, h); R3 = T.ring(F | R1 | R2, w, h)
        n = lambda S, m: sum(1 for c, r in S if m[r, c])
        out[names[k]] = dict(F=len(F), r1=n(R1, hz), r2=n(R2, hz), r3=n(R3, hz), r1imp=n(R1, f["imp"] > 0), r1riv=n(R1, f["river"] > 0),
                             r1sea=n(R1, f["terr"] == 1), inF_haz=n(F, hz), inF_imp=n(F, f["imp"] > 0), inF_riv=n(F, f["river"] > 0),
                             slot0=int(((f["slot"] == 0) & (f["region"] == k)).sum()), slots=int(((f["slot"] >= 0) & (f["region"] == k)).sum()))
    return out


if __name__ == "__main__":
    s = feats(T.STOCK); n = feats(sys.argv[1] if len(sys.argv) > 1 else str(T.HEX0))
    keys = list(next(iter(n.values())).keys())
    print("feature            bad(mean / frac>0)        good(mean / frac>0)      | stock: bad / good")
    for key in keys:
        b = np.array([n[t][key] for t in n if t in BAD]); g = np.array([n[t][key] for t in n if t not in BAD])
        sb = np.array([s[t][key] for t in n if t in BAD and t in s]); sg = np.array([s[t][key] for t in n if t not in BAD and t in s])
        print(f"{key:8s} {b.mean():7.2f} {np.mean(b > 0):5.2f}     {g.mean():7.2f} {np.mean(g > 0):5.2f}    | {sb.mean():6.2f} / {sg.mean():6.2f}")
    # deltas vs stock
    for key in ("r1", "r2", "inF_haz", "inF_riv", "inF_imp"):
        db = np.array([n[t][key] - s[t][key] for t in n if t in BAD]); dg = np.array([n[t][key] - s[t][key] for t in n if t not in BAD and t in s])
        print(f"delta {key:8s} bad mean {db.mean():6.2f} (<0: {np.mean(db < 0):.2f}, >0: {np.mean(db > 0):.2f})   good mean {dg.mean():6.2f} (<0: {np.mean(dg < 0):.2f}, >0: {np.mean(dg > 0):.2f})")
    json.dump({"stock": s, "new": n}, open(HERE / "citybar_features.json", "w"))
