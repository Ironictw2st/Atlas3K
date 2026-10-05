#!/usr/bin/env python3
"""Vanilla village / farmstead cluster templates (user 2026-10-03: "the props are so far apart, look at how every other
region has props, that should be the standard").

ONE-OFF, read-only: the ORIGINAL 190E kit layers (un-warped, so a cluster keeps its real spacing) -> every settlement-type
entity (model path under /settlements/) -> single-linkage clusters (LINK units) -> clusters 4..30 hexes from any town of
the original map.hex with >= MIN_PIECES pieces and radius <= MAX_R. Per template: climate of the centre hex, port flag
(port_* pieces: wants a river / coast), piece count, radius, and each piece's entity XML with its transform as offsets
(dx, dz from the centre, dy = height above the original ground at the centre, rotation, scale).
Output korea_ref/village_templates.json; village_dress.py stamps them on the new regions."""
import json, re, sys
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from scipy.spatial import cKDTree
from scipy.sparse.csgraph import connected_components
from scipy.sparse import coo_matrix
Image.MAX_IMAGE_PIXELS = None
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
ORIG = Path(r"Z:/Claude/TerryClone/output/backups/main190_originals_20260929_130639")
SRC = ORIG / "ak190E_terrain_3k_dlc07_main_map"
OUT = HERE / "korea_ref" / "village_templates.json"
OUT_AMB = HERE / "korea_ref" / "ambient_templates.json"
LINK, MIN_PIECES, MAX_R = 1.0, 8, 4.5
U2W = 0.000218712; W0 = 3.12725
SEA_Y = 14219 * U2W - W0      # stilt / port villages stand on the water: their base is sea level, not the sea floor
CLIMATES = ['arid', 'cold', 'default', 'subtropical', 'temperate']
LIFE = ("ECPointLight", "ECCompositeScene", "ECVFX", "ECDecal")
ATTACH = 0.6           # attachments within the cluster radius + ATTACH units belong to the village
AMB_LINK = 0.6
POS = re.compile(r'<ECTransform position="([^"]*)" rotation="([^"]*)" scale="([^"]*)"')


def piece(e, p, cx, cz, gc):
    """Entity XML with id / transform placeholders + offsets from the cluster centre (dy above the centre ground)."""
    pm = POS.search(e)
    e = re.sub(r'<entity id="[0-9a-f]+"', '<entity id="@ID@"', e, count=1)
    e = POS.sub('<ECTransform position="@POS@" rotation="@ROT@" scale="@SCL@"', e, count=1)
    return dict(e=e, dx=round(float(p[0] - cx), 4), dz=round(float(p[2] - cz), 4), dy=round(float(p[1] - gc), 4),
                rot=[float(v) for v in pm.group(2).split()], scl=pm.group(3))


def main():
    import town_fix as T
    from hexgrid import HX, HZ, nearest_hex
    _, _, w, h, _, f, names = T.load(str(ORIG / "190Expanded_map.hex"))
    town = (f["slot"] >= 0) | (f["sprawl"] > 0)
    dt = ndi.distance_transform_edt(~town, sampling=(HZ, HX))           # world units to the nearest town hex
    hgt = np.array(Image.open(SRC / "3k_dlc07_main_map.height.191fd803c1a801d.tif")); H8, W8 = hgt.shape
    def ground(x, z):
        px = np.clip(np.rint(x / HX * 8 + 4).astype(int), 0, W8 - 1); py = np.clip(np.rint(H8 - 1 - (z / HZ * 8 + 4)).astype(int), 0, H8 - 1)
        return hgt[py, px].astype(np.float64) * U2W - W0
    terry = open(SRC / "3k_dlc07_main_map.terry", encoding="utf-8", errors="replace").read()
    used = set(re.findall(r'id="([0-9a-f]+)"', terry))
    ents, xyz, tr = [], [], []
    life, lxyz = [], []                       # lights / living scenes / vfx / decals: village attachments or ambient life
    for p in sorted(SRC.glob("3k_dlc07_main_map.*.layer")):
        if p.name.split(".")[-2] not in used: continue
        t = open(p, encoding="utf-8", errors="replace").read()
        for e in re.findall(r"<entity .*?</entity>", t, re.S):
            if any("<" + c in e for c in LIFE):
                pm = POS.search(e)
                if pm: life.append(e); lxyz.append(tuple(map(float, pm.group(1).split())))
                continue
            m = re.search(r'model_path="([^"]*)"', e)
            if not m or "/settlements/" not in m.group(1).lower().replace("\\", "/"): continue
            pm = POS.search(e)
            if not pm: continue
            x, y, z = map(float, pm.group(1).split())
            ents.append(e); xyz.append((x, y, z)); tr.append((pm.group(2), pm.group(3)))
    xyz = np.array(xyz); print(f"{len(ents):,} settlement-type entities in the referenced original layers")
    tree = cKDTree(xyz[:, [0, 2]]); pr = tree.query_pairs(LINK, output_type="ndarray")
    n = len(ents); A = coo_matrix((np.ones(len(pr)), (pr[:, 0], pr[:, 1])), shape=(n, n))
    nc, lab = connected_components(A, directed=False)
    c_, r_ = nearest_hex(xyz[:, 0], xyz[:, 2], w, h)
    g0 = ground(xyz[:, 0], xyz[:, 2])
    lxyz = np.array(lxyz); ltree = cKDTree(lxyz[:, [0, 2]]); attached = np.zeros(len(life), bool)
    temps, rej = [], {"small": 0, "big": 0, "near_town": 0, "far": 0, "water": 0}
    order = np.argsort(lab); bounds = np.searchsorted(lab[order], np.arange(nc + 1))
    for k in range(nc):
        idx = order[bounds[k]:bounds[k + 1]]
        if len(idx) < MIN_PIECES: rej["small"] += 1; continue
        cx, cz = xyz[idx, 0].mean(), xyz[idx, 2].mean()
        rad = float(np.hypot(xyz[idx, 0] - cx, xyz[idx, 2] - cz).max())
        if rad > MAX_R: rej["big"] += 1; continue
        cc, rr = nearest_hex(np.array([cx]), np.array([cz]), w, h); cc, rr = int(cc[0]), int(rr[0])
        d = float(dt[r_[idx], c_[idx]].min()) / HX                       # hexes from the nearest town, closest piece
        if d < 4: rej["near_town"] += 1; continue
        if d > 30: rej["far"] += 1; continue
        if f["terr"][rr, cc] != 0: rej["water"] += 1; continue
        ci = int(f["climate"][rr, cc]); gc = max(float(ground(np.array([cx]), np.array([cz]))[0]), SEA_Y)   # one base: a building's pieces stay stacked
        pieces = [piece(ents[i], xyz[i], cx, cz, gc) for i in idx]
        for j in ltree.query_ball_point([cx, cz], rad + ATTACH):
            attached[j] = True
            pieces.append(piece(life[j], lxyz[j], cx, cz, gc))
        mp = " ".join(re.search(r'model_path="([^"]*)"', ents[i]).group(1).lower() for i in idx)
        temps.append(dict(climate=CLIMATES[ci] if 0 <= ci < len(CLIMATES) else "default", port="port_" in mp,
                          n=len(idx), r=round(rad, 3), town_d=round(d, 1), src=[round(cx, 2), round(cz, 2)], pieces=pieces))
    # ambient life: the rest, grouped (a 4-season leaf set, a herd), away from every settlement-type piece
    amb = []
    far = tree.query(lxyz[:, [0, 2]])[0] > 1.5
    sel = np.flatnonzero(~attached & far)
    st = cKDTree(lxyz[sel][:, [0, 2]]); pr2 = st.query_pairs(AMB_LINK, output_type="ndarray")
    m_ = len(sel); A2 = coo_matrix((np.ones(len(pr2)), (pr2[:, 0], pr2[:, 1])), shape=(m_, m_))
    _, lab2 = connected_components(A2, directed=False)
    for g in np.unique(lab2):
        ii = sel[lab2 == g]
        cx, cz = lxyz[ii, 0].mean(), lxyz[ii, 2].mean()
        cc, rr = nearest_hex(np.array([cx]), np.array([cz]), w, h); cc, rr = int(cc[0]), int(rr[0])
        if f["terr"][rr, cc] != 0: continue
        gc = max(float(ground(np.array([cx]), np.array([cz]))[0]), SEA_Y)
        names_ = " ".join(re.search(r'(?:vfx|path|model_path)="([^"]*)"', life[j]).group(1).split("/")[-1] for j in ii if re.search(r'(?:vfx|path|model_path)="([^"]*)"', life[j]))
        ci = int(f["climate"][rr, cc])
        amb.append(dict(climate=CLIMATES[ci] if 0 <= ci < len(CLIMATES) else "default", names=names_,
                        pieces=[piece(life[j], lxyz[j], cx, cz, gc) for j in ii]))
    land = int((f["terr"] == 0).sum())
    json.dump(dict(land=land, groups=amb), open(OUT_AMB, "w", encoding="utf-8"))
    import collections as _c
    print(f"attachments {int(attached.sum())} of {len(life)} life entities; ambient groups {len(amb)} "
          f"({len(amb) / land * 1000:.2f} per 1000 land hexes) {_c.Counter(a['climate'] for a in amb)}")
    print(f"{nc:,} clusters; templates {len(temps)} ({rej}); {len(temps) / land * 1000:.2f} per 1000 land hexes")
    import collections
    print("by climate", collections.Counter(t["climate"] for t in temps), "port", sum(t["port"] for t in temps),
          "pieces median", int(np.median([t["n"] for t in temps])))
    json.dump(temps, open(OUT, "w", encoding="utf-8"))
    print("->", OUT)


if __name__ == "__main__":
    main()
