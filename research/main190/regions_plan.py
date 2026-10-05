"""New-region seats for main190: lon/lat -> 190E world (georef) -> new hex (warp), locally corrected with the
residuals of known capitals (IDW over the nearest anchors). Read-only; prints the plan."""
import sys, json, numpy as np
from pathlib import Path
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
import crop_scale_map_hex as C, hexmap
from rebuild_hex import unpack
from hexgrid import nearest_hex, centre
from warp import Warp, WarpMapping, current
from georef import SEATS

NEW = {  # key: (group, seat name, lat, lon)
    "chenliu": ("central", "Chenliu", 34.80, 114.35), "liang": ("central", "Suiyang", 34.43, 115.63),
    "pei": ("central", "Xiang", 33.93, 116.77), "jiyin": ("central", "Dingtao", 35.07, 115.57),
    "shanyang": ("central", "Changyi", 35.10, 116.28), "lu": ("central", "Lu (Qufu)", 35.60, 116.99),
    "dongping": ("central", "Wuyan", 35.93, 116.47), "hongnong": ("central", "Hongnong", 34.52, 110.87),
    "zhangye": ("hexi", "Lude", 38.93, 100.45), "jiuquan": ("hexi", "Lufu", 39.73, 98.50),
    "dunhuang": ("hexi", "Dunhuang", 40.14, 94.66),
    "yunzhong": ("nomad", "Yunzhong", 40.28, 111.20), "dingxiang": ("nomad", "Shanwu", 40.20, 112.50),
    "shanggu": ("nomad", "Juyong", 40.43, 115.97), "liaoxi": ("nomad", "Yangle", 41.52, 121.25),
    "danhan": ("nomad", "Danhan (Xianbei court)", 41.55, 113.50),
}
M = np.array(json.load(open(HERE.parent / "guandu" / "georef.json"))["M"])
MAP = WarpMapping(current())


def load(path=None):
    p = Path(path) if path else HERE / "hex" / "map.hex"; src = p.read_bytes(); P, w, h = C.locate_dims(src)
    f = unpack(np.frombuffer(src, np.uint8, 16 * w * h, P + 8).reshape(h, w, 16))
    L = hexmap.load(str(p))["lists"]; return f, L["land_regions"] + L["sea_regions"], w, h


def predict(lat, lon):
    x, z = np.array([lon, lat, 1.0]) @ M; nx, nz = MAP.fwd_world(x, z); return float(nx), float(nz)


def plan(f, names, w, h):
    anchors = []
    for k, (_, lat, lon) in SEATS.items():
        n = f"3k_main_{k}_capital" if f"3k_main_{k}_capital" in names else f"3k_dlc06_{k}_capital"
        if n not in names: continue
        m = (f["region"] == names.index(n)) & (f["slot"] == 0)
        if not m.any(): continue
        r, c = np.argwhere(m).mean(0); ax, az = centre(int(round(c)), int(round(r)))
        px, pz = predict(lat, lon); anchors.append((px, pz, ax - px, az - pz, k))
    A = np.array([a[:4] for a in anchors])
    out = {}
    for key, (grp, seat, lat, lon) in NEW.items():
        px, pz = predict(lat, lon)
        d = np.hypot(A[:, 0] - px, A[:, 1] - pz); idx = np.argsort(d)[:4]; wts = 1 / (d[idx] + 5.0) ** 2
        cx, cz = px + (A[idx, 2] * wts).sum() / wts.sum(), pz + (A[idx, 3] * wts).sum() / wts.sum()
        c, r = nearest_hex(np.array([cx]), np.array([cz]), w, h); out[key] = (grp, seat, int(c[0]), int(r[0]))
    resid = np.hypot(A[:, 2], A[:, 3]) / 0.7
    return out, anchors, resid


if __name__ == "__main__":
    f, names, w, h = load()
    out, anchors, resid = plan(f, names, w, h)
    print(f"{len(anchors)} anchors, raw georef residual (hexes) median {np.median(resid):.1f}, max {resid.max():.1f}")
    for key, (grp, seat, c, r) in out.items():
        reg = names[f["region"][r, c]] if f["region"][r, c] >= 0 else "-"
        print(f"{grp:8s} {key:10s} {seat:24s} hex ({c},{r}) terr {f['terr'][r, c]} imp {f['imp'][r, c]} in {reg}")
