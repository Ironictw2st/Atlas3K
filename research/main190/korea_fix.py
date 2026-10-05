#!/usr/bin/env python3
"""Korea pass: beaches, textures, trees and roads. Run after rebuild_main.py, dem_fill.py and class_fill.py.

Korea = the ironic_region_{baek,baekje,dongokjeo,dongye,gyeongju,hanseong,jinbeongun,kimhae,lelang,ye}_* regions.
map.hex (hex/map.hex, the input is kept as hex/map_prekorea.hex):
  * coast: cliff -> beach wherever the sea side does not face east. The west and south coasts (Yellow Sea tidal
    flats, the southern archipelago) become beach; the steep east coast stays rocky.
  * roads: Korea's own roads are replaced. Nodes = every settlement (slot-0 hex) plus the gateway hexes where roads
    enter from outside Korea (to Liaodong/Xuantu, which are left untouched). Edges = the relative neighbourhood
    graph of the nodes (links only between towns with no third town between them). Each edge is routed by Dijkstra
    over passable plain land: slope and river crossings cost extra, foreign town slots are avoided, and existing
    new road is cheap so routes merge into trunks. The result follows the valleys, with no stubs, no parallel
    lattices and no roads on the coast or impassable ground.
rasters (terrain/; the class_fill.py output it starts from is copied to terrain/_pre_korea/, so always run
class_fill.py -> korea_fix.py together):
  * blend: Korea's flat class-4 fill is redrawn from the Shandong/Hebei distributions (lowland/hill by Korea
    height rank, mountain near impassable) with patchy noise; other painted details are kept. Beach hexes -> sand (0).
  * tree: lowland redrawn from the same area's tree-per-blend-class distribution (farmland); hills and mountains
    keep 190E's forest; towns, roads and beaches stay clear.
"""
import sys, os, sys, shutil, heapq, struct, zlib
import numpy as np
from pathlib import Path
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent, HERE.parent.parent / "output" / "pylibs"): sys.path.insert(0, str(p))
import tifffile
import crop_scale_map_hex as C, hexmap
from rebuild_hex import unpack
from hexgrid import neighbour, centre, nearest_hex
from terrain_main import FULL, NWW, NWH
from class_fill import smooth_noise, ranked

HEX = HERE / "hex" / "map.hex"; HEX0 = HERE / "hex" / "map_prekorea.hex"
T = HERE / "terrain"; KEEP = T / "_pre_korea"
BLEND = "3k_dlc07_main_map.blend.191fd8068da8020.tif"; TREE = "3k_dlc07_main_map.tree.191fd7dc12fe7e4.tif"
HEIGHT = "3k_dlc07_main_map.height.191fd803c1a801d.tif"
KOREA = ("baek", "baekje", "dongokjeo", "dongye", "gyeongju", "hanseong", "jinbeongun", "kimhae", "lelang", "ye")
LEARN = (740, 900, 520, 680)             # hex cols c0..c1, rows r0..r1: Shandong / Hebei / Liaodong lowlands+hills
try:                                     # the Hexi west pad (warp west columns) shifts every hex column
    from warp import current as _cur; _wp = getattr(_cur(), "west", 0) if hasattr(_cur(), "f") else 0
    LEARN = (LEARN[0] + _wp, LEARN[1] + _wp, LEARN[2], LEARN[3])
except Exception:
    pass
SAND, NO_TREE = 0, 19


def is_korean(n):
    if not n.startswith("ironic_region_"): return False
    k = n[len("ironic_region_"):]
    return any(k.startswith(p + "_capital") or k.startswith(p + "_resource") for p in KOREA)


def hex_px(c, r):
    x, z = centre(np.asarray(c), np.asarray(r))
    return (np.clip((x / NWW * FULL[0]).astype(int), 0, FULL[0] - 1),
            np.clip(((1 - z / NWH) * FULL[1]).astype(int), 0, FULL[1] - 1))


def fix_hex(log):
    if not HEX0.exists(): shutil.copy2(HEX, HEX0)       # rebuild_main.py writes both; map.hex is rewritten from HEX0
    src = HEX0.read_bytes()
    L = hexmap.load(str(HEX0))["lists"]; names = L["land_regions"] + L["sea_regions"]
    P, w, h = C.locate_dims(src)
    g = np.frombuffer(src, np.uint8, 16 * w * h, P + 8).reshape(h, w, 16).copy()
    f = unpack(g)
    kr_ids = [i for i, n in enumerate(names) if is_korean(n)]
    KR = np.isin(f["region"], kr_ids)
    terr, road = f["terr"].copy(), f["road"].copy()
    H = tifffile.imread(str(T / HEIGHT))
    rr, cc = np.mgrid[0:h, 0:w]; px, py = hex_px(cc, rr); hh = H[py, px].astype(np.float32)

    # --- beaches ---
    nb, nw = 0, 0
    for r, c in zip(*np.nonzero(KR & (terr == 3))):
        x0, z0 = centre(c, r); vx = vz = 0.0
        for d in range(6):
            nc, nr = neighbour(c, r, d)
            if 0 <= nc < w and 0 <= nr < h and terr[nr, nc] == 1:
                x1, z1 = centre(nc, nr); vx += x1 - x0; vz += z1 - z0
        if vx > 0.5 * np.hypot(vx, vz): nw += 1; continue            # sea to the east: rocky east coast
        terr[r, c] = 2; nb += 1
    log(f"korea coast: {nb} cliff hexes -> beach, {nw} east-facing cliffs kept; beaches now {int((KR & (terr == 2)).sum())}")

    # --- roads ---
    gate = []
    for r, c in zip(*np.nonzero(KR & (road > 0))):
        for d in range(6):
            if (road[r, c] >> d) & 1:
                nc, nr = neighbour(c, r, d)
                if not KR[nr, nc]: gate.append((c, r, d))
    keep_bits = {}
    for c, r, d in gate: keep_bits[(c, r)] = keep_bits.get((c, r), 0) | (1 << d)
    road[KR] = 0
    for (c, r), b in keep_bits.items(): road[r, c] = b
    towns = {}
    for i in kr_ids:
        m = (f["region"] == i) & (f["slot"] == 0)
        if not m.any(): continue
        if (m & (terr == 0)).any(): m &= terr == 0                       # node on an inland slot hex
        pts = np.argwhere(m); mc = pts.mean(0); r, c = pts[np.argmin(((pts - mc) ** 2).sum(1))]
        towns[names[i]] = (int(c), int(r))
    nodes = list(towns.values()) + sorted(keep_bits)
    labels = [n.replace("ironic_region_", "") for n in towns] + [f"gate{p}" for p in sorted(keep_bits)]
    xy = np.array([centre(c, r) for c, r in nodes])
    D = np.hypot(*(xy[:, None, :] - xy[None, :, :]).transpose(2, 0, 1))
    edges = [(D[a, b], a, b) for a in range(len(nodes)) for b in range(a + 1, len(nodes))
             if not (a >= len(towns) and b >= len(towns))                  # gateways only link to towns
             and not any(max(D[a, k], D[b, k]) < D[a, b] for k in range(len(nodes)) if k not in (a, b))]
    edges.sort()
    own_slot = f["slot"] >= 0
    passable = KR & (terr == 0) & (f["imp"] == 0)
    built = np.zeros((h, w), bool)
    for (c, r) in keep_bits: built[r, c] = True

    def step_cost(c, r, nc, nr, goal_slots):
        if not passable[nr, nc] and not goal_slots[nr, nc]: return None
        k = 0.35 if built[nr, nc] else 1.0
        k += abs(hh[nr, nc] - hh[r, c]) / 600.0
        if f["river"][nr, nc]: k += 3.0
        if own_slot[nr, nc] and not goal_slots[nr, nc]: k += 6.0
        return k

    routed, failed = 0, []
    for _, a, b in edges:
        (ac, ar), (bc, br) = nodes[a], nodes[b]
        goal = np.zeros((h, w), bool)
        for (c, r) in ((ac, ar), (bc, br)):
            reg = f["region"][r, c]
            if own_slot[r, c]: goal |= (f["region"] == reg) & own_slot & (terr == 0)
            goal[r, c] = True
        dist = {(ac, ar): 0.0}; prev = {}; pq = [(0.0, ac, ar)]
        while pq:
            dcur, c, r = heapq.heappop(pq)
            if (c, r) == (bc, br): break
            if dcur > dist.get((c, r), 1e18): continue
            for d in range(6):
                nc, nr = neighbour(c, r, d)
                if not (0 <= nc < w and 0 <= nr < h): continue
                k = step_cost(c, r, nc, nr, goal)
                if k is None: continue
                nd = dcur + k
                if nd < dist.get((nc, nr), 1e18):
                    dist[(nc, nr)] = nd; prev[(nc, nr)] = (c, r); heapq.heappush(pq, (nd, nc, nr))
        if (bc, br) not in prev:
            failed.append(f"{labels[a]}-{labels[b]}"); continue
        # reject detours: a link whose route is > 2.2x the straight line is left to the rest of the network
        path = [(bc, br)]
        while path[-1] != (ac, ar): path.append(prev[path[-1]])
        if len(path) > 2.2 * D[a, b] / 0.7 + 6: failed.append(f"{labels[a]}-{labels[b]} (detour)"); continue
        for (c0, r0), (c1, r1) in zip(path, path[1:]):
            for d in range(6):
                if neighbour(c0, r0, d) == (c1, r1):
                    road[r0, c0] |= 1 << d; road[r1, c1] |= 1 << ((d + 3) % 6)
            built[r0, c0] = built[r1, c1] = True
        routed += 1
    log(f"korea roads: {len(towns)} towns, {len(keep_bits)} gateways, {len(edges)} neighbour links, {routed} routed; "
        f"skipped {failed}; road hexes {int((KR & (road > 0)).sum())} (was {int((KR & (f['road'] > 0)).sum())})")
    g[..., 0] = (g[..., 0] & 0xFC) | terr.astype(np.uint8)
    g[..., 3] = (g[..., 3] & 0x81) | ((road.astype(np.uint8) & 63) << 1)
    out = bytearray(src); out[P + 8:P + 8 + 16 * w * h] = g.tobytes()
    out[-4:] = struct.pack("<I", zlib.crc32(bytes(out[:-4])) & 0xFFFFFFFF)          # trailer = crc32(body)
    HEX.write_bytes(bytes(out)); (HERE / "hex" / "map_korea.hex").write_bytes(bytes(out))   # regions_carve.py input
    return f, terr, road, KR, (w, h)


def fix_rasters(f, terr, road, KR, wh, log):
    w, h = wh
    KEEP.mkdir(exist_ok=True)
    for n in (BLEND, TREE):                     # always the fresh class_fill.py output (run class_fill first)
        shutil.copy2(T / n, KEEP / n)
    bim = Image.open(KEEP / BLEND); B = np.array(bim)
    tim = Image.open(KEEP / TREE); TR = np.array(tim)
    H = tifffile.imread(str(T / HEIGHT))
    # pixel -> hex for the Korea bbox and the learning box (full res)
    def pixels_to_hex(x0, x1, y0, y1, step=1):
        ys, xs = np.mgrid[y0:y1:step, x0:x1:step]
        wx = (xs + 0.5) / FULL[0] * NWW; wz = (1 - (ys + 0.5) / FULL[1]) * NWH
        c, r = nearest_hex(wx, wz, w, h)
        return ys, xs, c, r
    def box_px(c0, c1, r0, r1):
        x0, _ = hex_px(np.array(c0), np.array(0)); x1, _ = hex_px(np.array(c1), np.array(0))
        _, y1 = hex_px(np.array(0), np.array(r0)); _, y0 = hex_px(np.array(0), np.array(r1))
        return int(x0), int(x1), int(y0), int(y1)
    imp_near = f["imp"].astype(bool) & (terr != 1)
    grow = imp_near.copy()
    for d in range(6):
        for r, c in zip(*np.nonzero(imp_near)):
            nc, nr = neighbour(c, r, d)
            if 0 <= nc < w and 0 <= nr < h: grow[nr, nc] = True
    town = (f["slot"] >= 0) | (f["sprawl"] == 1)
    # learn mixes
    ys, xs, c, r = pixels_to_hex(*box_px(*LEARN), step=2)
    lb, lh = B[ys, xs], H[ys, xs]
    land = (terr[r, c] == 0) & ~town[r, c] & ~imp_near[r, c]
    lo, hi = np.percentile(lh[land], [35, 70])
    mix = {"low": land & (lh < lo), "hill": land & (lh > hi), "mountain": imp_near[r, c] & (terr[r, c] == 0)}
    cdfs = {}
    for k, m in mix.items():
        cnt = np.bincount(lb[m], minlength=256).astype(float); cdfs[k] = np.cumsum(cnt) / cnt.sum()
        top = np.argsort(-cnt)[:5]; log(f"  {k:8s} mix: {[(int(t), round(cnt[t] / cnt.sum(), 2)) for t in top]}")
    tq = TR[(ys // 4).clip(0, TR.shape[0] - 1), (xs // 4).clip(0, TR.shape[1] - 1)]
    tree_tab = np.zeros((256, 256)); np.add.at(tree_tab, (lb[land | mix["mountain"]], tq[land | mix["mountain"]]), 1)
    # Korea
    rows, cols = np.nonzero(KR)
    kx0, _ = hex_px(np.array(cols.min() - 2), np.array(0)); kx1, _ = hex_px(np.array(cols.max() + 2), np.array(0))
    _, ky1 = hex_px(np.array(0), np.array(rows.min() - 2)); _, ky0 = hex_px(np.array(0), np.array(rows.max() + 2))
    ys, xs, c, r = pixels_to_hex(int(kx0), int(kx1), int(ky0), int(ky1))
    # Korea = dry ground (sea source below land source) of Korean hexes and of the map.hex sea hexes bordering them:
    # the hex coast sits up to a hex inland of the real waterline, and that dry strip must be textured too
    SEA = tifffile.imread(str(T / "3k_dlc07_main_map.sea_height.191fd804ab3801e.tif"))
    dry = SEA[np.clip(ys // 2, 0, SEA.shape[0] - 1), np.clip(xs // 2, 0, SEA.shape[1] - 1)].astype(np.int32) <= H[ys, xs].astype(np.int32)
    def sea_rings(seed, n):                         # seed hexes + map.hex sea hexes up to n rings out from them
        out = seed.copy(); front = list(zip(*np.nonzero(seed)))
        for _ in range(n):
            nxt = []
            for rr_, cc_ in front:
                for d in range(6):
                    nc, nr = neighbour(cc_, rr_, d)
                    if 0 <= nc < w and 0 <= nr < h and terr[nr, nc] == 1 and not out[nr, nc]: out[nr, nc] = True; nxt.append((nr, nc))
            front = nxt
        return out
    KRx = sea_rings(KR & (terr != 1), 3) | KR
    inK = KRx[r, c] & dry
    hk = H[ys, xs].astype(float)
    rank = np.zeros_like(hk); rank[inK] = ranked(hk[inK])
    u = np.zeros_like(hk); u[inK] = ranked((0.5 * smooth_noise(inK.shape, 12, 11) + smooth_noise(inK.shape, 48, 12))[inK])
    blk = B[ys, xs].copy()
    redo = inK & (blk == 4)                                   # towns too (else their 19-hex footprints stay as red hexagons)
    # mountain zone: blurred + noise-dithered, so its edge is irregular instead of hexagon cells
    from dem_fill import box3
    gz = box3(np.ascontiguousarray(grow[r, c].astype(np.float32)), 5) + 0.25 * smooth_noise(inK.shape, 10, 22)
    kind = np.where(town[r, c], "low", np.where(gz > 0.5, "mountain", np.where(rank > 0.5, "hill", "low")))
    for k in cdfs:
        m = redo & (kind == k); blk[m] = np.searchsorted(cdfs[k], u[m]).clip(0, 255)
    # beach sand: a smooth strip along the real shoreline (land pixels within 3-8 px of water, width varying with
    # smooth noise) next to Korean beach hexes - not whole hex cells (those read as blocky steps in game)
    water = ~dry                                                   # true waterline (see inK above)
    dist = np.full(water.shape, 99, np.int16); cur = water.copy(); dist[cur] = 0
    for k in range(1, 10):
        grown = cur.copy()
        grown[1:] |= cur[:-1]; grown[:-1] |= cur[1:]; grown[:, 1:] |= cur[:, :-1]; grown[:, :-1] |= cur[:, 1:]
        dist[grown & ~cur] = k; cur = grown
    near_beach = sea_rings(KR & (terr == 2), 3)
    width = 3 + 5 * (smooth_noise(water.shape, 24, 21) * 0.5 + 0.5)
    beach = inK & ~water & (dist <= width) & near_beach[r, c]
    log(f"  sand debug: Korea land px {int(inK.sum())}, not water {int((inK & ~water).sum())}, within width of water "
        f"{int((inK & ~water & (dist <= width)).sum())}, near beach hex {int((inK & near_beach[r, c]).sum())}")
    blk[beach] = SAND
    Bn = B.copy(); Bn[ys, xs] = blk
    res = Image.fromarray(Bn, "P"); res.putpalette(bim.getpalette())
    tif = {"compression": "tiff_lzw", "strip_size": res.size[0] * 2, "tiffinfo": {277: 1, 339: 1, 284: 1}}
    res.save(T / BLEND, **tif)
    log(f"korea blend: {int(redo.sum())} class-4 px redrawn, {int(beach.sum())} beach px -> sand")
    # trees (quarter res): sample the pixel at each quarter cell's origin
    q = (ys % 4 == 0) & (xs % 4 == 0)
    qy, qx = ys[q] // 4, xs[q] // 4; qb = blk[q]; qin = inK[q]
    clear = town[r, c][q] | (road[r, c][q] > 0) | beach[q]
    ut = ranked(smooth_noise(inK.shape, 8, 13)[q] + 0.5 * smooth_noise(inK.shape, 32, 14)[q])
    tnew = TR[qy.clip(0, TR.shape[0] - 1), qx.clip(0, TR.shape[1] - 1)].copy()
    low = (kind[q] == "low")                    # farmland: sparse mainland trees; hills/mountains keep 190E forest
    for b in np.unique(qb[qin]):
        m = qin & ~clear & low & (qb == b)
        if m.any() and tree_tab[b].sum():
            tnew[m] = np.searchsorted(np.cumsum(tree_tab[b]) / tree_tab[b].sum(), ut[m]).clip(0, 255)
    tnew[qin & clear & ~town[r, c][q]] = NO_TREE
    ok = (qy < TR.shape[0]) & (qx < TR.shape[1])
    TRn = TR.copy(); TRn[qy[ok], qx[ok]] = tnew[ok]
    res = Image.fromarray(TRn, "P"); res.putpalette(tim.getpalette())
    res.save(T / TREE, **(tif | {"strip_size": res.size[0] * 2}))
    before = np.bincount(TR[qy[ok & qin], qx[ok & qin]], minlength=256); after = np.bincount(TRn[qy[ok & qin], qx[ok & qin]], minlength=256)
    log(f"korea trees: no-tree share {before[NO_TREE] / before.sum():.0%} -> {after[NO_TREE] / after.sum():.0%}")


def current_hex():
    """terr / road / Korea mask from the current hex/map.hex as is (raster-only run: no hex pass)."""
    src = HEX.read_bytes(); L = hexmap.load(str(HEX))["lists"]; names = L["land_regions"] + L["sea_regions"]
    P, w, h = C.locate_dims(src)
    f = unpack(np.frombuffer(src, np.uint8, 16 * w * h, P + 8).reshape(h, w, 16))
    KR = np.isin(f["region"], [i for i, n in enumerate(names) if is_korean(n)])
    return f, f["terr"].copy(), f["road"].copy(), KR, (w, h)


if __name__ == "__main__":
    if "--rasters-only" in sys.argv:                    # map.hex is final (padded / town-fixed): repaint rasters only
        fix_rasters(*current_hex(), print)
    else:
        f, terr, road, KR, wh = fix_hex(print)
        fix_rasters(f, terr, road, KR, wh, print)
