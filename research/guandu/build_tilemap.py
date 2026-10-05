#!/usr/bin/env python3
"""Build the Guandu tile_map.png from the user's vanilla tile map + the rebuilt Guandu map.hex.

The campaign tile map is the hex grid at 2x2 px per hex (tilemap_hex.py). Colours are BOB tile sets
(terrain/tiles/campaign/_tile_database/_settings.bin): areas (land, mountains, sea, coast) and 1-hex-wide lines
(rivers, roads, canals) with point markers (river start/mouth, crossings, canal links, cliff ends).

 - sea / beach / cliff come from the rebuilt map.hex (vanilla rule: beach hex = sea_coast ffff00, cliff hex =
   blockout_cliff f9ad69, cliff hex touching a beach = cliff end 9f222a)
 - other land takes the area colour of the vanilla hex nearest its scaled-back position (same mapping as the map.hex)
 - line families are redrawn as hex lines between the mapped ends of every vanilla edge (triangle shortcuts pruned),
   never over sea or coast hexes; point markers go to the mapped hex; river mouths are snapped onto the coast.
"""
import sys
from collections import deque
from pathlib import Path
import numpy as np
from PIL import Image

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import crop_scale_map_hex as C
from rebuild_hex import unpack
from hexgrid import neighbour, neighbour_arrays, nearest_hex, centre, hex_line
from tilemap_hex import hex_pixels, read_codes

VANILLA_TM = r"C:/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/assembly_kit/raw_data/terrain/campaigns/3k_dlc07_main_map/tile_map.png"
NEW_HEX = HERE / "hex" / "map_x2.25" / "map.hex"

SEA, BEACH, CLIFF, CLIFF_END, BLACK = 0x3971b7, 0xffff00, 0xf9ad69, 0x9f222a, 0x000000
AREAS = [0x96aa64, 0x53b021, 0x1820c1, 0xb69237, 0x463a76, 0xffff7f, 0x10ffe4]      # generic + mountain kinds
RIVER, START, MOUTH = 0x0000ff, 0xb4b4ff, 0xccccff
X_PAVED, X_IMPERIAL, X_TRACK = 0x7f00ff, 0x2c067f, 0xda43ff                          # river crossings
PAVED, IMPERIAL, TRACK = 0x5d4218, 0xc10018, 0x5d0018
CANAL, CANAL_LINK = 0x000068, 0x0037d0
FAMILIES = [  # (main colour, member colours) - drawn in this order, later overrides earlier
    (TRACK, {TRACK, X_TRACK}), (PAVED, {PAVED, X_PAVED}), (IMPERIAL, {IMPERIAL, X_IMPERIAL}),
    (CANAL, {CANAL, CANAL_LINK}),
    (RIVER, {RIVER, START, MOUTH, X_PAVED, X_IMPERIAL, X_TRACK}),
]
MARKERS = [START, X_PAVED, X_IMPERIAL, X_TRACK, CANAL_LINK]                           # MOUTH handled separately
KNOWN = set(AREAS) | {SEA, BEACH, CLIFF, CLIFF_END, BLACK, RIVER, START, MOUTH, X_PAVED, X_IMPERIAL, X_TRACK,
                      PAVED, IMPERIAL, TRACK, CANAL, CANAL_LINK}


def rgb(c): return np.array([(c >> 16) & 255, (c >> 8) & 255, c & 255], float)


def load_hex(path):
    mh = open(path, "rb").read(); P, w, h = C.locate_dims(mh)
    return unpack(np.frombuffer(mh, np.uint8, 16 * w * h, P + 8).reshape(h, w, 16)), w, h


def old_codes():
    """Per-hex tile code of the vanilla map, cropped to the Guandu box; stray editing colours snapped to the palette."""
    code = read_codes(Image.open(VANILLA_TM))
    ys, xs = hex_pixels(892, 702)
    blk = code[ys, xs]
    # majority colour of each 2x2 block
    hc = blk[..., 0]
    same = (blk == blk[..., :1]).sum(-1)
    for k in range(1, 4):
        better = (blk == blk[..., k:k + 1]).sum(-1) > same
        hc = np.where(better, blk[..., k], hc); same = np.maximum(same, (blk == blk[..., k:k + 1]).sum(-1))
    pal = sorted(KNOWN); P = np.stack([rgb(c) for c in pal])
    unknown = ~np.isin(hc, pal)
    if unknown.any():
        u = np.unique(hc[unknown])
        snap = {int(c): pal[int(np.argmin(((P - rgb(int(c))) ** 2).sum(1)))] for c in u}
        hc = np.vectorize(lambda c: snap.get(int(c), int(c)))(hc)
    return hc[C.ROW0:C.ROW1, C.COL0:C.COL1]


def area_base(hc):
    """Area colour under every old hex: its own if it is an area colour, else the nearest area hex's (BFS)."""
    h, w = hc.shape
    base = np.where(np.isin(hc, AREAS), hc, -1)
    q = deque(zip(*np.nonzero(base >= 0)))
    while q:
        r, c = q.popleft()
        for d in range(6):
            nc, nr = neighbour(c, r, d)
            if 0 <= nc < w and 0 <= nr < h and base[nr, nc] < 0:
                base[nr, nc] = base[r, c]; q.append((nr, nc))
    base[base < 0] = AREAS[0]
    return base


def family_edges(hc, members):
    """Undirected hex edges between adjacent old hexes of one line family, with triangle shortcuts removed."""
    h, w = hc.shape
    inside = np.isin(hc, list(members))
    adj = {}
    for r, c in zip(*np.nonzero(inside)):
        for d in range(6):
            nc, nr = neighbour(c, r, d)
            if 0 <= nc < w and 0 <= nr < h and inside[nr, nc]:
                adj.setdefault((c, r), set()).add((nc, nr))
    changed = True
    while changed:                                        # a-b-c all adjacent: drop the edge that skips the corner
        changed = False
        for a in list(adj):
            for b in list(adj.get(a, ())):
                common = adj[a] & adj.get(b, set())
                if common and len(adj[a]) > 1 and len(adj[b]) > 1:
                    corner = min(common, key=lambda x: len(adj[x]))
                    if len(adj[corner]) <= 2 or len(adj[a]) + len(adj[b]) > 2 * len(adj[corner]):
                        adj[a].discard(b); adj[b].discard(a); changed = True
    return {tuple(sorted((a, b))) for a in adj for b in adj[a]}


def build(log=print):
    N, NW, NH = load_hex(NEW_HEX)
    hc = old_codes(); ch, cw = hc.shape
    sx, sz = NW / cw, NH / ch
    base = area_base(hc)

    def m(c, r):
        x, z = centre(c, r); nc, nr = nearest_hex(x * sx, z * sz, NW, NH); return int(nc), int(nr)

    # areas + coast from the new map.hex
    rows, cols = np.mgrid[0:NH, 0:NW]
    x, z = centre(cols, rows)
    oc, orr = nearest_hex(x / sx, z / sz, cw, ch)
    out = base[orr, oc].copy()
    sea, beach, cliff = N["terr"] == 1, N["terr"] == 2, N["terr"] == 3
    out[sea] = SEA; out[beach] = BEACH; out[cliff] = CLIFF
    coast = beach | cliff
    # no roads/rivers in the dropped (non-playable) area: rebuild_hex clears them from map.hex there too
    sys.path.insert(0, str(HERE.parent)); import hexmap
    L = hexmap.load(str(NEW_HEX))["lists"]; names = L["land_regions"] + L["sea_regions"]
    dropped = np.isin(N["region"], [names.index(n) for n in ("3k_main_reg_non_playable", "3k_main_sea_non_playable") if n in names])
    drawable = lambda p: not sea[p[1], p[0]] and not coast[p[1], p[0]] and not dropped[p[1], p[0]]

    # lines
    for main, members in FAMILIES:
        E = family_edges(hc, members); n = 0
        for a, b in E:
            for p in hex_line(m(*a), m(*b)):
                if drawable(p): out[p[1], p[0]] = main; n += 1
        log(f"{'%06x' % main}: {len(E)} vanilla edges redrawn ({n} hexes)")

    # point markers
    for mk in MARKERS:
        k = 0
        for r, c in zip(*np.nonzero(hc == mk)):
            p = m(c, r)
            if drawable(p): out[p[1], p[0]] = mk; k += 1
        log(f"{'%06x' % mk}: {k} markers")

    # river mouths: onto the nearest coast hex next to the sea, joined to the river by a river line
    NA = neighbour_arrays(NH, NW)
    touch_sea = np.zeros((NH, NW), bool)
    for nr, nc, v in NA: touch_sea |= v & sea[nr, nc]
    shore = ~sea & touch_sea
    placed = 0
    for r, c in zip(*np.nonzero(hc == MOUTH)):
        s = m(c, r)
        seen = {s}; q = deque([s]); target = None
        while q:
            p = q.popleft()
            if shore[p[1], p[0]]: target = p; break
            if len(seen) > 400: break
            for d in range(6):
                n_ = neighbour(p[0], p[1], d)
                if 0 <= n_[0] < NW and 0 <= n_[1] < NH and n_ not in seen and not sea[n_[1], n_[0]]:
                    seen.add(n_); q.append(n_)
        if target is None: continue
        for p in hex_line(s, target)[:-1]:
            if drawable(p): out[p[1], p[0]] = RIVER
        out[target[1], target[0]] = MOUTH; placed += 1
    log(f"river mouths: {placed} placed on the coast")

    # thin the lines: where redrawn lines overlap they can be 2 hexes thick, which no BOB tile matches. A line hex
    # whose same-family neighbours form one contiguous arc of 2+ around it is redundant (the neighbours already
    # connect), so remove it; markers are never removed. Vanilla lines are 1 hex wide with no such hexes.
    removed = 0
    for main, members in FAMILIES:
        fam = set(members) | ({MOUTH} if main == RIVER else set())
        keep = set(MARKERS) | {MOUTH}
        changed = True
        while changed:
            changed = False
            mask = np.isin(out, list(fam))
            for r, c in zip(*np.nonzero(mask & (out == main))):
                ring = []
                for d in range(6):
                    n_ = neighbour(c, r, d)
                    ring.append(0 <= n_[0] < NW and 0 <= n_[1] < NH and out[n_[1], n_[0]] in fam)
                k = sum(ring)
                if k < 2 or k == 6: continue
                arcs = sum(1 for d in range(6) if ring[d] and not ring[d - 1])
                if arcs == 1:
                    out[r, c] = base[orr[r, c], oc[r, c]]; removed += 1; changed = True
    log(f"thinning: {removed} redundant line hexes removed")

    # cliff ends: cliff hex touching a beach
    nb = np.zeros((NH, NW), bool)
    for nr, nc, v in NA: nb |= v & (out[nr, nc] == BEACH)
    ends = (out == CLIFF) & nb
    out[ends] = CLIFF_END
    log(f"cliff ends: {int(ends.sum())}")

    # paint 2x2 blocks; uncovered pixels stay black
    img = np.zeros((2 * NH + 1, 2 * NW), np.int64)
    ys, xs = hex_pixels(NW, NH)
    for k in range(4): img[ys[..., k], xs[..., k]] = out
    rgba = np.stack([(img >> 16) & 255, (img >> 8) & 255, img & 255, np.full_like(img, 255)], -1).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA"), out


if __name__ == "__main__":
    im, out = build()
    im.save(HERE / "tile_map_rebuilt.png")
    vals, cnt = np.unique(out, return_counts=True)
    print(im.size, {('%06x' % v): int(n) for v, n in sorted(zip(vals, cnt), key=lambda t: -t[1])})
