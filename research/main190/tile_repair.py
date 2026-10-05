#!/usr/bin/env python3
"""Tile-map repair: coast / river / crossing hexes whose neighbourhood vanilla never uses get a colour that does.

BOB places campaign tiles by matching the tile map; a coast or line configuration with no matching tile is left
empty and shows in game as a see-through hole (tile_holes.py finds them after a Tilemap run). Vanilla's tile map is
CA-authored, so every hex-level pattern in it has tiles. Pattern = the category of a hex and of its 6 neighbours in
direction order (categories below: all generic/mountain areas are one class, the three roads one, the three
crossings one). For every coast/river/crossing hex whose pattern is not in vanilla's set, candidates are tried and
the one that most reduces the unseen patterns around it is kept (greedy, a few passes).

Changes are visual only (tile map). Crossing -> river removes a bridge model only where BOB had no tile for it
anyway; map.hex (pathfinding, bridges) is untouched.
"""
import sys
from pathlib import Path
import numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
from build_tilemap import SEA, BEACH, CLIFF, CLIFF_END, BLACK, AREAS, RIVER, START, MOUTH, X_PAVED, X_IMPERIAL, X_TRACK, PAVED, IMPERIAL, TRACK
from hexgrid import neighbour_arrays
from tilemap_hex import hex_pixels, read_codes

VAN_TM = r"Z:/Claude/TerryClone/Vanilla/3k_dlc07_main_map/tile_map.png"
VW, VH = 892, 702
CAT = {SEA: 1, BEACH: 2, CLIFF: 3, CLIFF_END: 4, RIVER: 5, START: 6, MOUTH: 7, X_PAVED: 8, X_IMPERIAL: 8, X_TRACK: 8,
       PAVED: 9, IMPERIAL: 9, TRACK: 9, BLACK: 0}            # everything else (areas, canals) -> 10 / 11
CANALS = {0x000068, 0x0037d0}
TARGET = {2, 3, 4, 5, 6, 7, 8}                               # coast, river and crossing hexes get repaired


def cats(out):
    c = np.full(out.shape, 10, np.int64)
    for k, v in CAT.items(): c[out == k] = v
    c[np.isin(out, list(CANALS))] = 11
    return c


def keys(c, NA):
    k = c.copy()
    for nr, nc, v in NA: k = k * 12 + np.where(v, c[nr, nc], 0)
    return k


_VSET = None
def vanilla_set():
    global _VSET
    if _VSET is None:
        code = read_codes(Image.open(VAN_TM)); ys, xs = hex_pixels(VW, VH)
        hexc = code[np.clip(ys[..., 0], 0, code.shape[0] - 1), np.clip(xs[..., 0], 0, code.shape[1] - 1)]
        _VSET = np.unique(keys(cats(hexc), neighbour_arrays(VH, VW)))
    return _VSET


def unseen(out, NA):
    c = cats(out); return (~np.isin(keys(c, NA), vanilla_set())) & np.isin(c, list(TARGET))


XS = {X_PAVED, X_IMPERIAL, X_TRACK}
RIVS = {RIVER, START, MOUTH} | XS
ROADC = {PAVED, IMPERIAL, TRACK}
# crossing layouts BOB tiles reliably: (river sides, road sides) rotated so the smallest description wins. Measured
# on vanilla (count >= 4) and against tile_holes.py: a straight river with the road across it, or the one bent layout
# vanilla uses 4x. ((0,2),(1,4)) - bent river, road inner/opposite - is never in vanilla and 10/10 of ours were holes.
GOOD_X = {((0, 3), (1, 4)), ((0, 3), (1, 5)), ((0, 3), (2, 5)), ((0, 2), (1, 5)),
          ((0, 2), (1, 3)), ((0, 3), (1, 2, 4)), ((0,), (1, 4))}   # + the rarer layouts vanilla also uses
# not included although vanilla has it twice: ((0, 3), (1,)) - road on one side only; 2/2 of ours were holes


def x_sig(out, NA, r, c):
    rv = [d for d, (nr, nc, v) in enumerate(NA) if v[r, c] and int(out[nr[r, c], nc[r, c]]) in RIVS]
    rd = [d for d, (nr, nc, v) in enumerate(NA) if v[r, c] and int(out[nr[r, c], nc[r, c]]) in ROADC]
    best = None
    for base in rv or [0]:
        s = (tuple(sorted((d - base) % 6 for d in rv)), tuple(sorted((d - base) % 6 for d in rd)))
        best = s if best is None or s < best else best
    return best


def fix_crossings(out, NA, land_of, log=print):
    """Crossings in a layout BOB can't tile: move a road end one side round the crossing (road stays connected),
    else draw plain river (visual only - map.hex keeps the bridge)."""
    NH, NW = out.shape
    def nb(r, c, d):
        nr, nc, v = NA[d]; return (int(nr[r, c]), int(nc[r, c])) if v[r, c] else None
    def adj(a, b):
        return any(nb(*a, d) == b for d in range(6))
    moved = dropped = 0
    for r, c in zip(*np.nonzero(np.isin(out, list(XS)))):
        if x_sig(out, NA, r, c) in GOOD_X: continue
        done = False
        # road on one side only (it stops at the river): continue it one hex onto open land on another side
        rds = [d for d in range(6) if nb(r, c, d) and int(out[nb(r, c, d)]) in ROADC]
        if len(rds) == 1:
            colour = int(out[nb(r, c, rds[0])])
            for dn in sorted(range(6), key=lambda k: -abs(((k - rds[0]) % 6) - 3)):   # straight across first
                n = nb(r, c, dn)
                if n is None or int(out[n]) not in AREAS: continue
                keep = int(out[n]); out[n] = colour
                if x_sig(out, NA, r, c) in GOOD_X: done = True; break
                out[n] = keep
        if done: moved += 1; continue
        for d in range(6):
            o = nb(r, c, d)
            if o is None or int(out[o]) not in ROADC: continue
            beyond = [nb(*o, k) for k in range(6)]
            beyond = [b for b in beyond if b and b != (r, c) and int(out[b]) in ROADC | XS]
            if len(beyond) > 1: continue                        # junction: leave it
            for dn in ((d + 1) % 6, (d - 1) % 6):
                n = nb(r, c, dn)
                if n is None or int(out[n]) not in AREAS: continue
                if beyond and not (adj(n, beyond[0]) or n == beyond[0]): continue
                keep_o, keep_n = int(out[o]), int(out[n])
                out[n] = keep_o; out[o] = land_of(*o)
                if x_sig(out, NA, r, c) in GOOD_X: done = True; break
                out[o], out[n] = keep_o, keep_n
            if done: break
        if done: moved += 1
        else: out[r, c] = RIVER; dropped += 1
    log(f"crossings: {moved} road ends moved or extended to a tileable layout, {dropped} drawn as plain river (no tile for them)")


def repair(out, log=print, passes=4):
    """out: hex-level tile colours (NH, NW), modified in place. Returns the number of hexes changed."""
    NH, NW = out.shape; NA = neighbour_arrays(NH, NW)
    vs = vanilla_set(); before = int(unseen(out, NA).sum()); changed = 0

    def local_bad(r, c):
        pts = [(r, c)] + [(nr[r, c], nc[r, c]) for nr, nc, v in NA if v[r, c]]
        n = 0
        for (a, b) in pts:
            if CAT.get(int(out[a, b]), 10) not in TARGET: continue
            k = CAT.get(int(out[a, b]), 11 if int(out[a, b]) in CANALS else 10)
            for nr, nc, v in NA:
                x = int(out[nr[a, b], nc[a, b]]) if v[a, b] else None
                k = k * 12 + (0 if x is None else CAT.get(x, 11 if x in CANALS else 10))
            n += int(not np.isin(k, vs))
        return n

    def land_of(r, c):
        ns = [int(out[nr[r, c], nc[r, c]]) for nr, nc, v in NA if v[r, c] and int(out[nr[r, c], nc[r, c]]) in AREAS]
        return max(set(ns), key=ns.count) if ns else AREAS[0]

    fix_crossings(out, NA, land_of, log)
    for it in range(passes):
        bad = unseen(out, NA); n_it = 0
        for r, c in zip(*np.nonzero(bad)):
            cur = int(out[r, c]); cat = CAT.get(cur)
            cand = {4: [BEACH, CLIFF], 3: [CLIFF_END, BEACH, SEA], 2: [SEA, land_of(r, c)], 7: [SEA, RIVER],
                    8: [RIVER], 6: [RIVER, land_of(r, c)], 5: [MOUTH]}.get(cat, [])
            base = local_bad(r, c); best = None
            for x in cand:
                out[r, c] = x; s = local_bad(r, c)
                if s < base and (best is None or s < best[0]): best = (s, x)
            out[r, c] = best[1] if best else cur
            if best: n_it += 1
        changed += n_it
        if not n_it: break
    # measured holes from previous BOB rounds (tile_holes.py --feedback): recolour exactly those hexes, cycling
    # through the alternatives one round at a time
    fb_path = HERE / "holes" / "feedback.json"
    if fb_path.exists():
        import json
        fb = json.load(open(fb_path)); nfb = 0
        for key, n in fb.items():
            c, r = map(int, key.split(","))
            if not (0 <= r < NH and 0 <= c < NW): continue
            cur = int(out[r, c]); cat = CAT.get(cur)
            alts = {8: [RIVER], 4: [BEACH, CLIFF, SEA], 3: [BEACH, SEA], 2: [SEA, land_of(r, c)], 7: [SEA, RIVER]}.get(cat)
            if not alts:
                # round 8 (user: tiles missing along rivers and roads): a line hex that keeps being a hole is dropped -
                # a one-hex gap in the road / river beats a see-through hole; on an area hex, the adjacent line hexes go
                if cat == 9 or (cat in (5, 6) and n >= 2):
                    out[r, c] = land_of(r, c); nfb += 1
                elif cat not in TARGET and n >= 2:
                    for nr_, nc_, v_ in NA:
                        if v_[r, c] and CAT.get(int(out[nr_[r, c], nc_[r, c]])) in (5, 6, 9):
                            q = (int(nr_[r, c]), int(nc_[r, c])); out[q] = land_of(*q); nfb += 1
                continue
            out[r, c] = alts[min(n, len(alts)) - 1]; nfb += 1
        log(f"feedback: {nfb} measured-hole hexes recoloured ({len(fb)} listed)")
    # re-apply the coast rule after any recolouring: a cliff touching beach is an end, an end touching no beach a cliff
    for _ in range(2):
        nbB = np.zeros((NH, NW), bool)
        for nr, nc, v in NA: nbB |= v & (out[nr, nc] == BEACH)
        out[(out == CLIFF) & nbB] = CLIFF_END; out[(out == CLIFF_END) & ~nbB] = CLIFF
    after = int(unseen(out, NA).sum())
    log(f"tile repair: unseen coast/river/crossing patterns {before} -> {after} ({changed} hexes recoloured)")
    return changed
