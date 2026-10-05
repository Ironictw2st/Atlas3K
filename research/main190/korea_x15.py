#!/usr/bin/env python3
"""Korea / Liaodong / north rework from SilverCat's maps (Discord 190expanded, 2026-10-02 msgs 1555414339849035826..
1555423316419022889; user: extended layout with North Buyeo + North Okjeo, all new provinces unowned, re-key the Xuantu /
Liaodong provinces, follow SilverCat's rivers, no mountain tiles in the north; new Dongye town = Huali; keep the Suli
Xianbei towns and land, Xuantu trimmed around them).

Inputs: the *_add* images (191E overlay crop, georeferenced in korea_ref/geo.py), korea_ref/match.json (icon <-> town
matching). Stage A (default, read-only): per-hex SilverCat layers (border lines, province fills, rivers), the province /
town plan, a territory carve and the river trace, rendered to korea_ref/preview.png + korea_ref/plan.json.
Stage B (--apply): writes hex/map.hex and regions_new.json (see apply())."""
import collections, heapq, json, shutil, struct, sys, time, zlib
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
Image.MAX_IMAGE_PIXELS = None
HERE = Path(__file__).parent
for p in (HERE / "korea_ref", HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
import geo, town_fix as T, hexmap
from hexgrid import neighbour, neighbour_arrays, HX, HZ

A = Path(r"Z:/Claude/190Expanded/tools/discord/attachments/1028302428963078230")
ADD, FILL = A / "3K_overlay_map_add.png", A / "3K_overlay_map_add3.png"
OWN_FILL = A / "3K_overlay_map_add2.png"

# province plan: (key, label, zhou, [(region key, new?, display name or None = keep, icon id or (x, y) image point, capital?)])
P = {
 "NorthBuyeo": ("3k_ironic_province_north_buyeo", "North Buyeo", "KoreaNorth", [
     ("ironic_region_buyeo_capital", True, "Buyeo-seong", 36, True), ("ironic_region_buyeo_resource_1", True, "Ye-seong", 0, False)]),
 "NorthOkjeo": ("3k_ironic_province_north_okjeo", "North Okjeo", "KoreaNorth", [
     ("ironic_region_bukokjeo_capital", True, "Chaek-seong", 37, True), ("ironic_region_bukokjeo_resource_1", True, "Chiguru", 3, False)]),
 "Goguryeo": ("3k_ironic_province_goguryeo", "Goguryeo", "KoreaNorth", [
     ("ironic_region_dongokjeo_resource_2", False, "Guknae-seong", 39, True), ("ironic_region_goguryeo_resource_1", True, "Yeo-seong", 2, False)]),
 "EastOkjeo": ("3k_ironic_province_dongokjeo", "East Okjeo", None, [
     ("ironic_region_dongokjeo_capital", False, None, 42, True), ("ironic_region_dongokjeo_resource_1", False, None, 7, False)]),
 "Xuantu": ("3k_ironic_province_hyunto", "Xuantu", None, [
     ("ironic_region_hyunto_capital", False, None, 38, True), ("ironic_region_hyunto_resource_1", False, None, 4, False),
     ("ironic_region_hyunto_resource_2", False, None, 1, False)]),
 "Liaodong": ("3k_dlc06_province_liaodong", "Liaodong", None, [
     ("3k_dlc06_liaodong_capital", False, None, 41, True), ("3k_dlc06_liaodong_resource_1", False, None, 5, False),
     ("ironic_region_fanhan_resource_1", True, "Fanhan", 8, False)]),
 "Lelang": ("3k_ironic_province_lelang", "Lelang", None, [
     ("ironic_region_lelang_capital", False, None, 43, True), ("ironic_region_lelang_resource_1", False, None, 10, False),
     ("ironic_region_dongye_resource_1", False, None, 11, False)]),
 "Dongye": ("3k_ironic_province_dongye", "Dongye", None, [
     ("ironic_region_dongye_capital", False, None, 44, True), ("ironic_region_dongye_resource_2", True, "Huali", 13, False)]),
 "Daifang": ("3k_ironic_province_jinbeongun", "Daifang", None, [
     ("ironic_region_jinbeongun_capital", False, None, 45, True), ("ironic_region_jinbeongun_resource_1", False, None, 12, False),
     ("ironic_region_jinbeongun_resource_2", False, None, 15, False)]),
 "Hanseong": ("3k_ironic_province_hanseong", "Hanseong", None, [
     ("ironic_region_hanseong_capital", False, None, 47, True), ("ironic_region_hanseong_resource_1", False, None, 19, False),
     ("ironic_region_hanseong_resource_2", False, None, 16, False), ("ironic_region_hanseong_resource_3", True, "Mosu-guk", 14, False)]),
 "Ye": ("3k_ironic_province_ye", "Ye", None, [
     ("ironic_region_ye_capital", False, None, 21, True), ("ironic_region_ye_resource_1", False, None, 48, False),
     ("ironic_region_ye_resource_2", True, "Uyu-guk", (1125, 1400), False)]),
 "Mahan": ("3k_ironic_province_baekje", "Mahan", None, [
     ("ironic_region_baekje_capital", False, None, 51, True), ("ironic_region_baekje_resource_1", False, "Saryangbeol-guk", 23, False),
     ("ironic_region_baekje_resource_2", False, None, 26, False)]),
 "Jinhan": ("3k_ironic_province_gyeongju", "Jinhan", None, [
     ("ironic_region_gyeongju_capital", False, None, 52, True), ("ironic_region_gyeongju_resource_1", False, None, 27, False),
     ("ironic_region_gyeongju_resource_2", True, "Geungi-guk", 24, False)]),
 "Byeonhan": ("3k_ironic_province_kimhae", "Byeonhan", None, [
     ("ironic_region_kimhae_capital", False, None, 53, True), ("ironic_region_kimhae_resource_1", False, None, 29, False),
     ("ironic_region_kimhae_resource_2", True, "Banpa-guk", 25, False)]),
 "ChimmiDarye": ("3k_ironic_province_baek", "Chimmi Darye", None, [
     ("ironic_region_baek_capital", False, None, 55, True), ("ironic_region_baek_resource_2", False, None, 30, False),
     ("ironic_region_baek_resource_3", False, None, 31, False)]),
 "Tamna": ("3k_ironic_province_tamna", "Tamna", "KoreaSouth", [
     ("ironic_region_tamna_capital", True, "Mugeun-seong", 57, True), ("ironic_region_baek_resource_1", False, "Seobul", 33, False)]),
}
OLD_PROVINCES = {"3k_ironic_province_xuantu"}                 # the x15 export's key for Liaodong+Changli: dropped
MOVE_PX = 20                                                    # existing towns further than this from SilverCat's icon move
LINE_COST, CLASS_COST = 30.0, 12.0
MIN_REGION = 300


def load_imgs():
    a = np.array(Image.open(ADD).convert("RGB")).astype(np.int16)
    c = np.array(Image.open(FILL).convert("RGB")).astype(np.int16)
    return a, c


def icon_xy(m, icon):
    if isinstance(icon, tuple): return icon
    for k in ("match", "new_icons"):
        for x in m[k]:
            if x["icon"] == icon: return tuple(x["img"])
    raise KeyError(icon)


def hex_pixels(w, h, cols, rows):
    x, y = geo.hex_to_img(cols, rows)
    return np.rint(x).astype(int), np.rint(y).astype(int)


def cyan(img):
    R, G, B = img[..., 0].astype(int), img[..., 1].astype(int), img[..., 2].astype(int)
    return (B > R + 45) & (G > R + 30) & (B > 150) & (G > 150)


def thin(mask):
    """Zhang-Suen thinning (no skimage here)."""
    m = mask.copy().astype(np.uint8)
    while True:
        changed = False
        for step in (0, 1):
            P2 = np.roll(m, 1, 0); P3 = np.roll(np.roll(m, 1, 0), -1, 1); P4 = np.roll(m, -1, 1); P5 = np.roll(np.roll(m, -1, 0), -1, 1)
            P6 = np.roll(m, -1, 0); P7 = np.roll(np.roll(m, -1, 0), 1, 1); P8 = np.roll(m, 1, 1); P9 = np.roll(np.roll(m, 1, 0), 1, 1)
            nb = [P2, P3, P4, P5, P6, P7, P8, P9]
            B = sum(nb)
            Aa = sum(((nb[i] == 0) & (nb[(i + 1) % 8] == 1)) for i in range(8))
            if step == 0: c1 = P2 * P4 * P6; c2 = P4 * P6 * P8
            else: c1 = P2 * P4 * P8; c2 = P2 * P6 * P8
            rm = (m == 1) & (B >= 2) & (B <= 6) & (Aa == 1) & (c1 == 0) & (c2 == 0)
            if rm.any(): m[rm] = 0; changed = True
        if not changed: return m.astype(bool)


def corner_graph(cols, rows):
    """Hex-corner graph for the given hexes: corner id -> world (x, z); edges (u, v, (c, r, d))."""
    R = HX / 1.5
    ang = {0: (60, 120), 1: (0, 60), 2: (-60, 0), 3: (-120, -60), 4: (180, 240), 5: (120, 180)}
    key = {}; xy = []; edges = {}
    def cid(x, z):
        k = (round(x * 40), round(z * 40))
        if k not in key: key[k] = len(xy); xy.append((x, z))
        return key[k]
    for c, r in zip(cols.ravel(), rows.ravel()):
        cx, cz = c * HX, r * HZ + (c & 1) * (HZ / 2)
        for d in range(6):
            a1, a2 = np.radians(ang[d])
            u = cid(cx + R * np.cos(a1), cz + R * np.sin(a1)); v = cid(cx + R * np.cos(a2), cz + R * np.sin(a2))
            edges.setdefault((min(u, v), max(u, v)), []).append((int(c), int(r), d))
    return np.array(xy), edges


def world_to_img(x, z):
    c = np.asarray(x) / HX; r = np.asarray(z) / HZ
    c0 = (c - 140) / 1.5; r0 = r / 1.5
    return c0 * geo.PXC - geo.X0, 3024 - (r0 + 0.5) * geo.PXR + geo.YTOP


def stage_a():
    b, Pp, w, h, g, f, names = T.load(str(HERE / "hex" / "map.hex"))
    L = hexmap.load(str(HERE / "hex" / "map.hex"))["lists"]; LAND = L["land_regions"]; NL = len(LAND)
    m = json.load(open(HERE / "korea_ref" / "match.json", encoding="utf-8"))
    add, fill = load_imgs(); IH, IW = add.shape[:2]
    rows, cols = np.mgrid[0:h, 0:w]
    px, py = hex_pixels(w, h, cols, rows)
    inside = (px >= 0) & (px < IW) & (py >= 0) & (py < IH)
    pxc, pyc = np.clip(px, 0, IW - 1), np.clip(py, 0, IH - 1)
    A_ = add[pyc, pxc]; C_ = fill[pyc, pxc]
    # border strokes: dark pixels in long connected strokes only (town icons and the commandery glyphs are compact blobs)
    dark = add.sum(-1) / 3 < 75
    labd, nd = ndi.label(ndi.binary_dilation(dark, iterations=1), structure=np.ones((3, 3)))
    keep = np.zeros(nd + 1, bool)
    for i, sl in enumerate(ndi.find_objects(labd), 1):
        hgt, wid = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        keep[i] = max(hgt, wid) > 45
    stroke = keep[labd] & dark
    line = inside & stroke[pyc, pxc]
    seaish = f["terr"] != 0                                  # coastline strokes are as black as borders: ignore near the sea
    near_sea = seaish.copy()
    for nr_, nc_, v_ in neighbour_arrays(h, w): near_sea |= v_ & seaish[nr_, nc_]
    line &= ~near_sea
    filled = inside & (np.abs(C_ - A_).sum(-1) > 40)
    # province reference fills: median of the fill near each province's icons
    refs = {}
    for pk, (_, _, _, mem) in P.items():
        vals = []
        for (_, _, _, ic, _) in mem:
            x, y = icon_xy(m, ic)
            for dx, dy in ((0, 22), (22, 0), (-22, 0), (0, -22), (16, 16), (-16, 16), (16, -16), (-16, -16)):
                X, Y = int(x + dx), int(y + dy)
                if 0 <= X < IW and 0 <= Y < IH and np.abs(fill[Y, X] - add[Y, X]).sum() > 40: vals.append(fill[Y, X])
        refs[pk] = np.median(np.array(vals), 0) if vals else None
    keys = [k for k in P if refs[k] is not None]
    RF = np.stack([refs[k] for k in keys])
    dist = np.abs(C_[..., None, :] - RF[None, None]).sum(-1)
    cls = np.where(filled, np.argmin(dist, -1), -1)
    cls[filled & (dist.min(-1) > 90)] = -1                    # labels / mixed pixels: unknown
    # who may be re-carved: current Korean / Liaodong regions + non-playable land inside SilverCat's fills
    nj = json.load(open(HERE / "regions_new.json", encoding="utf-8"))
    kor = {mm for _, (_, _, _, mem) in P.items() for (mm, new, *_ ) in mem if not new}
    kor |= {mm for pv in nj["all_provinces"] if pv["key"] in OLD_PROVINCES for mm in pv["members"]}
    kid = {names.index(k) for k in kor if k in names}
    NP = names.index("3k_main_reg_non_playable")
    reg = f["region"]; land = f["terr"] != 1
    opened = ndi.binary_fill_holes(filled & (reg == NP) & land) & (reg == NP) & land & inside
    opened &= (rows < h - 3) & (cols < w - 3) & (cols >= 3)          # the map edge stays non-playable
    elig = land & (np.isin(reg, list(kid)) | opened)
    # seeds: every town's target hex
    seeds = []                                                   # (pk, region key, new, name, cap, (c, r), move)
    cent = {}
    for k in np.unique(reg[f["slot"] == 0]):
        rr, cc = np.nonzero((f["slot"] == 0) & (reg == k)); cent[names[k]] = (cc.mean(), rr.mean())
    for pk, (key, label, zhou, mem) in P.items():
        for (rk, new, nm, ic, cap) in mem:
            x, y = icon_xy(m, ic); c, r = geo.img_to_hex(x, y); c, r = int(round(float(c))), int(round(float(r)))
            move = False
            if not new:
                oc, orr = cent[rk]; ox, oy = geo.hex_to_img(oc, orr)
                move = float(np.hypot(ox - x, oy - y)) > MOVE_PX
                if not move: c, r = int(round(oc)), int(round(orr))
            r = min(r, h - 6)                                    # SilverCat's north reaches past the map top
            seeds.append((pk, rk, new, nm, cap, (c, r), move))
    # territory: multi-source Dijkstra over eligible hexes
    pidx = {k: i for i, k in enumerate(keys)}
    cost = 1.0 + LINE_COST * line
    owner = -np.ones((h, w), np.int32); best = np.full((h, w), np.inf)
    pq = []
    er, ec = np.nonzero(elig & (f["terr"] == 0))
    for i, s in enumerate(seeds):                                # a seed on sea / outside the carve snaps to the nearest land
        c, r = s[5]
        if not (0 <= r < h and 0 <= c < w and elig[r, c] and f["terr"][r, c] == 0):
            j = int(np.argmin((ec - c) ** 2 + (er - r) ** 2)); c, r = int(ec[j]), int(er[j])
            seeds[i] = s[:5] + ((c, r),) + s[6:]
    for s in seeds:                                              # no wall right around a town
        c, r = s[5]; line[max(0, r - 2):r + 3, max(0, c - 2):c + 3] = False
    from class_fill import smooth_noise
    noise = 0.6 * smooth_noise((h, w), 18, 71) + 0.4 * smooth_noise((h, w), 6, 72)
    noise = (noise - noise.min()) / (np.ptp(noise) + 1e-9)
    cost = 1.0 + 2.5 * noise + LINE_COST * line
    NA = neighbour_arrays(h, w)

    seedhex = -np.ones((h, w), np.int32)
    for i, s_ in enumerate(seeds): seedhex[s_[5][1], s_[5][0]] = i

    def carve(ids, mask, offset):
        own = -np.ones((h, w), np.int32); bst = np.full((h, w), np.inf); q = []
        for i in ids:
            c, r = seeds[i][5]
            bst[r, c] = offset.get(i, 0.0); own[r, c] = i; heapq.heappush(q, (bst[r, c], r, c, i))
        while q:
            d, r, c, i = heapq.heappop(q)
            if d > bst[r, c] or own[r, c] != i: continue
            for nr, nc, v in NA:
                if not v[r, c]: continue
                a, bb = nr[r, c], nc[r, c]
                if not mask[a, bb] or (seedhex[a, bb] >= 0 and seedhex[a, bb] != i): continue
                pen = CLASS_COST if (cls[a, bb] >= 0 and cls[a, bb] != pidx.get(seeds[i][0], -9)) else 0.0
                nd = d + cost[a, bb] + pen
                if nd < bst[a, bb]: bst[a, bb] = nd; own[a, bb] = i; heapq.heappush(q, (nd, a, bb, i))
        own[~mask] = -1
        return own

    owner = carve(range(len(seeds)), elig, {})
    # balance inside each province: a town under MIN_REGION hexes gets a head start (power-diagram offsets)
    for pk in P:
        ids = [i for i, s in enumerate(seeds) if s[0] == pk]
        if len(ids) < 2: continue
        zone = np.isin(owner, ids)
        off = {i: 0.0 for i in ids}
        for _ in range(40):
            own = carve(ids, zone, off)
            sz = {i: int((own == i).sum()) for i in ids}
            target = min(MIN_REGION, int(zone.sum() / len(ids) * 0.6))
            small = [i for i in ids if sz[i] < target]
            if not small: break
            for i in small: off[i] -= 4.0
        owner[zone] = own[zone]
    # rivers: SilverCat's cyan strokes inside the area, traced along hex edges
    riv_img = thin(ndi.binary_closing(cyan(add), iterations=2))
    dt = ndi.distance_transform_edt(~riv_img)
    area = elig | (filled & land)
    rr_, cc_ = np.nonzero(area)
    xy, edges = corner_graph(cc_, rr_)
    ex, ey = world_to_img(xy[:, 0], xy[:, 1])
    ex, ey = np.clip(np.rint(ex).astype(int), 0, IW - 1), np.clip(np.rint(ey).astype(int), 0, IH - 1)
    cdist = dt[ey, ex]
    adj = collections.defaultdict(list)
    for (u, v), hx in edges.items():
        if len(hx) < 2: continue                                 # border of the area: skip
        c0, r0, _ = hx[0]; c1, r1, _ = hx[1]
        if f["terr"][r0, c0] == 1 or f["terr"][r1, c1] == 1: continue
        wgt = 0.2 + (0.5 * (cdist[u] + cdist[v])) ** 2 * 0.15
        adj[u].append((v, wgt, (u, v))); adj[v].append((u, wgt, (u, v)))
    # skeleton components -> endpoints -> nearest corners; Steiner-ish tree from the first endpoint
    lab, n = ndi.label(riv_img, structure=np.ones((3, 3)))
    nbc = ndi.convolve(riv_img.astype(int), np.ones((3, 3), int), mode="constant") - 1
    river_edges = set(); traced = 0
    near = cdist < 3
    for comp in range(1, n + 1):
        cm = lab == comp
        if cm.sum() < 25: continue
        ys, xs = np.nonzero(cm & (nbc == 1))
        if len(xs) < 2: continue
        # endpoints -> nearest graph corner with an edge
        cand = np.array([i for i in range(len(xy)) if i in adj])
        pts = []
        for x, y in zip(xs, ys):
            d2 = (ex[cand] - x) ** 2 + (ey[cand] - y) ** 2
            j = int(np.argmin(d2))
            if d2[j] < 15 ** 2: pts.append(int(cand[j]))
        pts = list(dict.fromkeys(pts))
        if len(pts) < 2: continue
        src = pts[0]; dist_ = {src: 0.0}; prev = {src: None}; q = [(0.0, src)]
        while q:
            d, u = heapq.heappop(q)
            if d > dist_.get(u, 1e18): continue
            for v, wgt, e in adj[u]:
                nd = d + wgt
                if nd < dist_.get(v, 1e18): dist_[v] = nd; prev[v] = (u, e); heapq.heappush(q, (nd, v))
        for t in pts[1:]:
            if t not in prev: continue
            u = t
            while prev[u] is not None:
                pu, e = prev[u]; river_edges.add(e); u = pu
            traced += 1
    rhex = []
    for e in river_edges:
        for (c, r, d) in edges[e]: rhex.append((c, r, d))
    plan = dict(seeds=[dict(province=s[0], key=s[1], new=s[2], name=s[3], capital=s[4], hex=list(s[5]), move=s[6]) for s in seeds],
                river_edge_count=len(river_edges), traced=traced)
    np.savez_compressed(HERE / "korea_ref" / "carve.npz", owner=owner, elig=elig, cls=cls, line=line, filled=filled)
    json.dump(dict(plan, river_hex_edges=rhex), open(HERE / "korea_ref" / "plan.json", "w", encoding="utf-8"), indent=0, ensure_ascii=False)
    # preview
    r0, r1, c0, c1 = 600, h, 1000, w
    rng = np.random.default_rng(3)
    pal = {pk: rng.integers(60, 230, 3) for pk in P}
    img = np.zeros((r1 - r0, c1 - c0, 3), np.uint8)
    t_ = f["terr"][r0:r1, c0:c1]; o = owner[r0:r1, c0:c1]
    img[...] = (205, 200, 180); img[t_ == 1] = (60, 90, 150); img[(reg[r0:r1, c0:c1] == NP) & (t_ != 1)] = (150, 145, 130)
    for i, s in enumerate(seeds):
        col = pal[s[0]] * (0.85 if i % 2 else 1.0)
        img[o == i] = col.astype(np.uint8)
    # region borders
    bd = np.zeros_like(o, bool)
    for nr, nc, v in NA:
        nb = owner[nr, nc][r0:r1, c0:c1]
        bd |= v[r0:r1, c0:c1] & (o >= 0) & (nb != o)
    img[bd] = (30, 30, 30)
    for (c, r, d) in rhex:
        if r0 <= r < r1 and c0 <= c < c1: img[r - r0, c - c0] = (0, 160, 255)
    for s in seeds:
        c, r = s[5]
        if r0 <= r < r1 and c0 <= c < c1:
            img[max(0, r - r0 - 2):r - r0 + 3, max(0, c - c0 - 2):c - c0 + 3] = (255, 255, 255) if s[4] else (255, 40, 40)
    Image.fromarray(img[::-1]).resize(((c1 - c0) * 2, (r1 - r0) * 2), Image.NEAREST).save(HERE / "korea_ref" / "preview.png")
    sizes = collections.Counter(owner[owner >= 0].tolist())
    ctx = dict(owner=owner, elig=elig, opened=opened & elig, seeds=seeds, rhex=rhex, NP=NP)
    for i, s in enumerate(seeds):
        print(f"{s[0]:12s} {s[1]:40s} {(s[3] or '-'):14s} {'CAP' if s[4] else '   '} hex{s[5]} {'MOVE' if s[6] else '    '} {sizes.get(i, 0)} hexes")
    print(f"opened non-playable land: {int((elig & (reg == NP)).sum())} hexes; river edges traced {len(river_edges)} ({traced} paths)")
    return ctx


if __name__ == "__main__":
    ctx = stage_a()
    if "--apply" in sys.argv:
        import korea_apply; korea_apply.apply(ctx, P, OLD_PROVINCES)
