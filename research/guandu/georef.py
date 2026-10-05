"""Fit a lon/lat -> world (x, z) transform for the vanilla 3K map from region-capital settlement positions.

Settlement world positions = median position of non-vegetation props in each <region>_capital props layer.
Real positions = Han-era commandery seats (approximate modern coords).
"""
import re, glob, statistics as st, numpy as np, json, sys, os

AK = r"Z:/Claude/TerryClone/Vanilla/3k_dlc07_main_map"
WORLD_W, WORLD_H = 595.0999755859375, 541.7861938476562   # trees.campaign_tree_list header
RASTER_W, RASTER_H = 7136, 5620

# region -> (seat, lat, lon)
SEATS = {
    "luoyang": ("Luoyang", 34.72, 112.62), "changan": ("Chang'an", 34.31, 108.88),
    "weijun": ("Ye", 36.33, 114.37), "yingchuan": ("Xuchang", 34.04, 113.83),
    "taiyuan": ("Jinyang", 37.72, 112.47), "youzhou": ("Ji (Beijing)", 39.90, 116.40),
    "henei": ("Huai", 35.03, 113.20), "dongjun": ("Puyang", 35.66, 114.95),
    "chenjun": ("Chen", 33.73, 114.88), "pingyuan": ("Pingyuan", 37.17, 116.43),
    "bohai": ("Nanpi", 38.03, 116.70), "zhongshan": ("Lunu", 38.52, 115.00),
    "taishan": ("Fenggao", 36.20, 117.10), "shangdang": ("Zhangzi", 36.12, 113.00),
    "nanyang": ("Wan", 33.00, 112.53), "runan": ("Pingyu", 32.96, 114.62),
    "anping": ("Xindu", 37.57, 115.55), "langye": ("Kaiyang", 35.10, 118.35),
    "donghai": ("Tan", 34.60, 118.35), "xiapi": ("Xiapi", 34.31, 117.96),
    "penchang": ("Pengcheng", 34.26, 117.19), "guangling": ("Guangling", 32.40, 119.43),
    "yanmen": ("Yinguan", 39.33, 112.43), "daijun": ("Dai", 39.83, 114.57),
    "donglai": ("Huang", 37.65, 120.40), "beihai": ("Ju", 36.70, 118.80),
    "xiangyang": ("Xiangyang", 32.01, 112.12), "jianye": ("Jianye", 32.05, 118.78),
    "hanzhong": ("Nanzheng", 33.07, 107.03), "chengdu": ("Chengdu", 30.66, 104.07),
    "changsha": ("Linxiang", 28.20, 112.97), "kuaiji": ("Shanyin", 30.00, 120.58),
    "nanhai": ("Panyu", 23.13, 113.26), "wuwei": ("Guzang", 37.93, 102.64),
}

def settlements():
    t = open(f"{AK}/3k_dlc07_main_map.terry", encoding="utf-8").read()
    out = {}
    for lid, name in re.findall(r'<entity id="([0-9a-f]+)" name="3k_(?:main|dlc06)_([a-z_]+)_capital">', t):
        f = f"{AK}/3k_dlc07_main_map.{lid}.layer"
        if not os.path.exists(f): continue
        pts = []
        for e in re.findall(r"<entity id.*?</entity>", open(f, encoding="utf-8").read(), re.S):
            m = re.search(r'model_path="([^"]*)"', e); p = re.search(r'position="([^"]+)"', e)
            if m and p and "vegetation" not in m.group(1).lower():
                x, _, z = map(float, p.group(1).split()); pts.append((x, z))
        if len(pts) >= 20:
            out[name] = (st.median(a for a, _ in pts), st.median(b for _, b in pts))
    return out

def fit(keys, S):
    A = np.array([[SEATS[k][2], SEATS[k][1], 1] for k in keys])
    B = np.array([S[k] for k in keys])
    M, *_ = np.linalg.lstsq(A, B, rcond=None)
    return M, A @ M - B

if __name__ == "__main__":
    S = settlements()
    north = [k for k in SEATS if k in S and SEATS[k][1] >= 31.5 and 105 < SEATS[k][2] < 122]
    everything = [k for k in SEATS if k in S]
    for label, keys in (("all China", everything), ("north", north)):
        M, r = fit(keys, S)
        err = np.hypot(r[:, 0], r[:, 1])
        print(f"== {label}: {len(keys)} seats, rms {np.sqrt((err**2).mean()):.1f} units, max {err.max():.1f}")
        print(f"   x = {M[0,0]:.3f}*lon + {M[1,0]:.3f}*lat + {M[2,0]:.1f}   z = {M[0,1]:.3f}*lon + {M[1,1]:.3f}*lat + {M[2,1]:.1f}")
        if label == "north":
            for k, e, rr in sorted(zip(keys, err, r), key=lambda t: -t[1]):
                print(f"   {k:10s} {SEATS[k][0]:12s} off {e:5.1f}  (dx {rr[0]:+5.1f}, dz {rr[1]:+5.1f})")
            json.dump({"M": M.tolist(), "settlements": S}, open(os.path.join(os.path.dirname(__file__), "georef.json"), "w"), indent=1)
