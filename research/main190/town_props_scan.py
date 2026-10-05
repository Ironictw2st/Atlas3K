#!/usr/bin/env python3
"""Props whose real footprint covers a town (user 2026-10-02: steppe town models buried in mountain meshes).
Footprint = LOD0 horizontal radius (korea_ref/model_radius.json, model_radius.py) x max(scale x, scale z) x REACH.
A mountain / rock / area-of-interest prop covers a town when that footprint reaches within MARGIN hexes of any
footprint hex; a vegetation prop when it stands within VEG_RING hexes of a footprint or on a road hex.
Library: covered(entity_text, x, z) for ak_main / x15_land; CLI: scan the kit layers and report per town."""
import glob, json, re, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
REACH = 0.7           # mountain meshes are irregular: their max extent overstates the solid part
MARGIN = 1            # hexes around a town footprint that must stay clear of mountain meshes
VEG_RING = 2
KIT = Path(r"C:/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/assembly_kit_190E/raw_data/terrain/campaigns/3k_190e_expanded_map")
_S = None


def _setup():
    global _S
    if _S is not None: return _S
    import town_fix as T
    from hexgrid import neighbour_arrays, HX, HZ
    from scipy import ndimage as ndi
    _, _, w, h, _, f, names = T.load(str(HERE / "hex" / "map.hex"))
    NA = neighbour_arrays(h, w)
    town = (f["slot"] >= 0) | (f["sprawl"] > 0)
    # only towns that stock 190E doesn't have (stock towns are dressed by CA / 190E on purpose: passes in gorges ...)
    stock = set()
    for line in open(HERE / "source" / "db" / "region_to_province_junctions_tables" / "data__.tsv", encoding="utf-8"):
        a = line.split("	")
        if len(a) >= 3 and not a[0].startswith(("#", "province")): stock.add(a[1])
    newk = [i for i, n in enumerate(names) if n not in stock and not n.startswith("3k_")]
    town &= np.isin(f["region"], newk)
    def grow(m, k):
        for _ in range(k):
            g = m.copy()
            for nr, nc, v in NA: g |= v & m[nr, nc]
            m = g
        return m
    keep_clear = grow(town, MARGIN)
    veg_clear = grow(town, VEG_RING) | ((f["road"] > 0) & (f["terr"] == 0))
    # world-space distance (units) from every hex to the nearest keep-clear hex, via an EDT on the hex grid
    dt, idx = ndi.distance_transform_edt(~keep_clear, sampling=(HZ, HX), return_indices=True)
    rad = json.load(open(HERE / "korea_ref" / "model_radius.json"))
    _S = dict(w=w, h=h, f=f, names=names, town=town, keep=keep_clear, veg=veg_clear, dt=dt, idx=idx, rad=rad, HX=HX, HZ=HZ)
    return _S


def _hex(x, z, S):
    c = int(round(x / S["HX"])); c = min(max(c, 0), S["w"] - 1)
    r = int(round((z - (c & 1) * S["HZ"] / 2) / S["HZ"])); r = min(max(r, 0), S["h"] - 1)
    return c, r


def covered(entity_text, x, z):
    """(True, reason) when the entity is a prop that should go for the towns' sake."""
    m = re.search(r'model_path="([^"]*)"', entity_text)
    if not m: return False, None
    mp = m.group(1).replace("\\", "/").lower()
    S = _setup()
    c, r = _hex(x, z, S)
    if "/vegetation/" in mp:
        return (bool(S["veg"][r, c]), "vegetation near town / on road")
    if not any(k in mp for k in ("/mountains/", "/rocks/", "/area_of_interest/mount")): return False, None
    sc = re.search(r'scale="([-\d.e]+) ([-\d.e]+) ([-\d.e]+)"', entity_text)
    s = max(abs(float(sc.group(1))), abs(float(sc.group(3)))) if sc else 1.0
    reach = S["rad"].get(mp, 0.0) * s * REACH
    return (bool(S["dt"][r, c] < reach), f"mountain reach {reach:.1f}u > {S['dt'][r, c]:.1f}u to a town")


def scan():
    S = _setup()
    terry = open(KIT / "3k_190e_expanded_map.terry", encoding="utf-8", errors="replace").read()
    ids = set(re.findall(r'id="([0-9a-f]+)"', terry))
    hits = {}
    for p in glob.glob(str(KIT / "*.layer")):
        if p.split(".")[-2] not in ids: continue
        t = open(p, encoding="utf-8", errors="replace").read()
        for e in re.findall(r"<entity .*?</entity>", t, re.S):
            mm = re.search(r'<ECTransform position="([-\d.e]+) ([-\d.e]+) ([-\d.e]+)"', e)
            if not mm: continue
            x, z = float(mm.group(1)), float(mm.group(3))
            ok, why = covered(e, x, z)
            if not ok: continue
            c, r = _hex(x, z, S)
            tr, tc = S["idx"][0][r, c], S["idx"][1][r, c]
            # the town nearest to the covered keep-clear hex
            k = S["f"]["region"][tr, tc]
            nm = S["names"][k] if 0 <= k < len(S["names"]) else "?"
            kind = "veg" if "vegetation" in why else "mountain"
            hits.setdefault(nm, {"veg": 0, "mountain": 0, "models": set()})
            hits[nm][kind] += 1
            if kind == "mountain": hits[nm]["models"].add(re.search(r'model_path="([^"]*)"', e).group(1).split("/")[-1])
    return hits


if __name__ == "__main__":
    hits = scan()
    want = sys.argv[1:]
    tot_v = sum(v["veg"] for v in hits.values()); tot_m = sum(v["mountain"] for v in hits.values())
    print(f"{len(hits)} towns/regions with covering props; vegetation {tot_v}, mountain/rock {tot_m}")
    for nm, v in sorted(hits.items(), key=lambda kv: -kv[1]["mountain"]):
        if want and not any(wk in nm for wk in want): continue
        print(f"  {nm:45s} mountain {v['mountain']:3d} veg {v['veg']:4d}  {sorted(v['models'])[:4]}")
