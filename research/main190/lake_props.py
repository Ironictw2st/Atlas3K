#!/usr/bin/env python3
"""Water for the raised lakes (user 2026-10-02: "there is no water in the new lakes").

3K's campaign only shows sea water where the ground is below sea level (lf u16 14219 = world 0); our new lakes (Qinghai,
Juyan, the Hexi / steppe lakes) sit on the plateau at their DEM level, so they render as dry beds. Vanilla does inland /
raised water with props: 92 of its 97 lake props are rigidmodels/campaign/props/lakes/small_lake_1.wsmodel (a water
disc, LOD0 radius 3.2 at scale 1) at ground height, scales 0.02 - 1.0.

add(out_dir, map_name): for every sea-hex body above sea level, pack small_lake_1 discs into it (largest first, each
disc's radius = its distance to the shore, so the water stays inside the lake), y = the highest lake-bed height under
the disc + a lift, and appends the entities to the layer that holds vanilla's lake props. Called by ak_main.py, so it
survives every rebuild. Report: korea_ref/lake_props.json."""
import json, os, re, sys
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
Image.MAX_IMAGE_PIXELS = None
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
MODEL = "rigidmodels/campaign/props/lakes/small_lake_1.wsmodel"
R1 = 3.2                    # LOD0 radius at scale 1 (model_radius.json)
SEA_U16 = 14219; U2W = 0.000218712; W0 = 3.12725
LIFT = 0.04                 # water a hair above the bed
MIN_R = 0.25                # smallest disc (world units)
HEIGHT = HERE / "terrain" / "3k_dlc07_main_map.height.191fd803c1a801d.tif"


def lakes():
    import town_fix as T
    from hexgrid import HX, HZ
    _, _, w, h, _, f, names = T.load(str(HERE / "hex" / "map.hex"))
    hgt = np.array(Image.open(HEIGHT)); H8 = hgt.shape[0]
    rows, cols = np.mgrid[0:h, 0:w]
    gy = hgt[np.clip(H8 - 1 - (rows * 8 + 4), 0, H8 - 1), np.clip(cols * 8 + 4, 0, hgt.shape[1] - 1)].astype(np.float64)
    water = f["terr"] == 1
    lab, n = ndi.label(water)
    out = []
    for i in range(1, n + 1):
        m = lab == i
        k = int(m.sum())
        if k < 6 or k > 50000: continue                                   # the open sea is not a lake
        g = gy[m]
        if np.median(g) <= SEA_U16 + 300: continue                          # at / below sea level: the sea renders it
        out.append(m)
    return out, gy, (w, h, HX, HZ)


def pack(m, gy, geom):
    w, h, HX, HZ = geom
    dt = ndi.distance_transform_edt(m, sampling=(HZ, HX))                   # world distance to the shore
    covered = np.zeros_like(m)
    rows, cols = np.mgrid[0:h, 0:w]
    rr0, cc0 = np.nonzero(m)
    r0, r1, c0, c1 = rr0.min(), rr0.max() + 1, cc0.min(), cc0.max() + 1
    sub = (slice(r0, r1), slice(c0, c1))
    discs = []
    for _ in range(600):
        cand = np.where(m[sub] & ~covered[sub], dt[sub], 0)
        if cand.max() <= 0: break
        r, c = np.unravel_index(np.argmax(cand), cand.shape); r += r0; c += c0
        rad = min(float(dt[r, c]) + 0.35, R1 * 1.0)
        if rad < MIN_R: break
        x, z = c * HX, r * HZ + (c & 1) * HZ / 2
        X = cols[sub] * HX; Z = rows[sub] * HZ + (cols[sub] & 1) * HZ / 2
        inside = np.hypot(X - x, Z - z) <= rad
        bed = gy[sub][inside & m[sub]]
        y = (float(bed.max()) if bed.size else float(gy[r, c])) * U2W - W0 + LIFT
        covered[sub] |= inside & m[sub]
        discs.append((x, y, z, rad / R1))
        if covered[m].mean() > 0.985: break
    return discs, float(covered[m].mean())


def entity(eid, x, y, z, s, rot):
    return (f'<entity id="{eid}">\n      <ECPropMesh/>\n      <ECMesh model_path="{MODEL}" animation_path=""/>\n'
            '      <ECMeshRenderSettings inherit_from_parent="false" cast_shadow="true" alpha="1" tint_colour="255 255 255 255" '
            'set_tint_colour_from_colour_overlay="false" faction_colour="255 255 255 255"/>\n'
            '      <ECPropHeightPatch has_height_patch="false" apply_height_patch="false"/>\n'
            '      <ECCampaignProperties visible_inside_snow_region="true" visible_outside_snow_region="true" '
            'visible_inside_destruction_region="true" visible_outside_destruction_region="true" visible_in_unseen_shroud="false" '
            'visible_in_seen_shroud="true" no_culling="false" culture_mask="" season_mask=""/>\n'
            '      <ECDLCMask type="Exclude" mask=""/>\n'
            f'      <ECTransform position="{x:.4f} {y:.5f} {z:.4f}" rotation="0 {rot:.2f} 0" scale="{s:.5f} 0.3 {s:.5f}" pivot="0 0 0"/>\n'
            '      <ECTerrainClamp active="false" clamp_to_sea_level="false" terrain_oriented="false" fit_height_to_terrain="false"/>\n'
            '    </entity>')


def add(out_dir, map_name="3k_dlc07_main_map"):
    out_dir = Path(out_dir)
    host = None
    terry = open(out_dir / f"{map_name}.terry", encoding="utf-8", errors="replace").read()
    used = set(re.findall(r'id="([0-9a-f]+)"', terry))           # only layers the project references (stale copies exist)
    for p in sorted(out_dir.glob(f"{map_name}.*.layer")):
        if p.name.split(".")[-2] not in used: continue
        t = open(p, encoding="utf-8").read()
        if "props/lakes/small_lake_1" in t: host = p; break
    if host is None: print("lake_props: no layer with vanilla lake props - skipped"); return
    t = open(host, encoding="utf-8").read()
    # a template entity of this layer, to copy its exact ECTerrainClamp line (attributes vary by layer version)
    tmpl = re.search(r'<entity id="[0-9a-f]+">\s*<ECPropMesh/>\s*<ECMesh model_path="[^"]*small_lake_1[^"]*".*?</entity>', t, re.S).group(0)
    clamp = re.search(r"<ECTerrainClamp[^>]*/>", tmpl).group(0)
    bodies, gy, geom = lakes()
    rng = np.random.default_rng(23)
    ents, report = [], []
    for m in bodies:
        discs, cov = pack(m, gy, geom)
        rr, cc = np.nonzero(m)
        report.append(dict(hex=[int(cc.mean()), int(rr.mean())], hexes=int(m.sum()), discs=len(discs), coverage=round(cov, 3)))
        for (x, y, z, s) in discs:
            eid = "%015x" % int(rng.integers(0x1f00000000000000 >> 4, 0x1fffffffffffffff >> 4))
            ents.append(re.sub(r"<ECTerrainClamp[^>]*/>", clamp, entity(eid, x, y, z, s, float(rng.uniform(0, 360)))))
    i = t.rindex("</entities>") if "</entities>" in t else t.rindex("</entity>") + len("</entity>")
    t = t[:i] + "\n    " + "\n    ".join(ents) + "\n  " + t[i:]
    open(host, "w", encoding="utf-8", newline="").write(t)
    json.dump(dict(host=host.name, lakes=report), open(HERE / "korea_ref" / "lake_props.json", "w"), indent=1)
    print(f"lake_props: {len(ents)} small_lake_1 discs in {len(bodies)} raised lakes -> {host.name}")
    return len(ents)


if __name__ == "__main__":
    bodies, gy, geom = lakes()
    for m in bodies:
        d, cov = pack(m, gy, geom); rr, cc = np.nonzero(m)
        print(f"lake at hex ({int(cc.mean())},{int(rr.mean())}) {int(m.sum())} hexes: {len(d)} discs, coverage {cov:.1%}")
