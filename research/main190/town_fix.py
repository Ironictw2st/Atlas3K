#!/usr/bin/env python3
"""Town fixes on the CAIME-upscaled 190E map.hex (user, 2026-10-01: city bars missing for river / coast towns).

User rule: a settlement placed on a river / coastline needs part of its edge impassable.
 A. Every town whose stock-190E footprint (slots + sprawl) had impassable hexes touching it gets that pattern back,
    placed relative to the town (the upscaler block-copied impassability, then re-pinned the town and widened the
    water, so the pattern ended up shrunk or detached: Jiangling, Yong'an, Kui Pass, Chaling, Shangyong...).
 B. Towns that sit against a river with no impassable edge (Langzhong, Zitong, Luocheng, Zizhong, Xicheng) are moved
    a few hexes away from the river: the whole footprint is translated (cube coordinates keep its shape) to the
    nearest spot in its own region with 3+ hexes clear of river / impassable / coast; the roads that ended at the
    old footprint are redrawn to the new one.
Input/output: hex/map.hex (the input is kept as hex/map_pre_townfix.hex). Log: town_fix.json."""
import json, shutil, struct, sys, zlib
from collections import deque
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
import crop_scale_map_hex as C, hexmap
from rebuild_hex import unpack
from hexgrid import neighbour, to_cube, from_cube, hex_line, direction_between

STOCK = r"Z:/Claude/190Expanded/campaign_maps/map.hex"
HEX = HERE / "hex" / "map.hex"; HEX0 = HERE / "hex" / "map_pre_townfix.hex"
MOVE = ["3k_main_baxi_capital", "3k_main_baxi_resource_2", "3k_main_chengdu_resource_2", "3k_main_chengdu_resource_3",
        "3k_main_shangyong_resource_1", "3k_main_shangyong_capital", "3k_main_changsha_capital", "3k_main_anding_capital",
        "3k_main_wuling_capital", "3k_main_zangke_capital", "3k_main_lingling_resource_2", "3k_main_poyang_resource_3",
        "3k_main_dongjun_resource_1"]
PORT_FIX = ["3k_main_donglai_capital"]
STAMP_SKIP = {"3k_main_langye_resource_2"}  # stamping Buji made it border 2 hazard patches (CAIME); the P fix passes
if (HERE / "town_fix_auto.json").exists():      # towns that lost river / impassable contact vs stock (citybar_features.py)
    _auto = json.load(open(HERE / "town_fix_auto.json")); MOVE += _auto["move"]; PORT_FIX += _auto["port"]     # ports stay put: their land edge along the water becomes impassable
D_SKIP = set(json.load(open(HERE / "town_fix_dskip.json"))) if (HERE / "town_fix_dskip.json").exists() else set()
C_SKIP = set(json.load(open(HERE / "town_fix_cskip.json"))) if (HERE / "town_fix_cskip.json").exists() else set()
A_SKIP = {"3k_main_changsha_capital", "3k_main_anding_capital"}   # restoring their pattern made a second hazard patch
CLEAR = 3                      # hexes between a moved footprint and river / impassable / coast
MAXMOVE = 6


def load(path):
    b = bytearray(Path(path).read_bytes()); P, w, h = C.locate_dims(bytes(b))
    g = np.frombuffer(b, np.uint8, 16 * w * h, P + 8).reshape(h, w, 16)
    names = hexmap.load(str(path))["lists"]; names = names["land_regions"] + names["sea_regions"]
    return b, P, w, h, g, unpack(g), names


def nbrs(c, r, w, h):
    for d in range(6):
        nc, nr = neighbour(c, r, d)
        if 0 <= nc < w and 0 <= nr < h: yield d, nc, nr


def footprint(f, k):
    return {(int(c), int(r)) for r, c in zip(*np.nonzero(((f["slot"] >= 0) | (f["sprawl"] > 0)) & (f["region"] == k)))}


def ring(F, w, h):
    return {(nc, nr) for c, r in F for _, nc, nr in nbrs(c, r, w, h)} - F


def cube_shift(p, T):
    q, r, _ = to_cube(*p); return from_cube(q + T[0], r + T[1])


def translation(F0, F1):
    """Cube translation mapping footprint F0 onto F1 (None if the shapes differ)."""
    a = min((to_cube(*p)[:2], p) for p in F0)[1]; b = min((to_cube(*p)[:2], p) for p in F1)[1]
    qa, ra, _ = to_cube(*a); qb, rb, _ = to_cube(*b); T = (qb - qa, rb - ra)
    return T if {cube_shift(p, T) for p in F0} == F1 else None


def main():
    if not HEX0.exists(): shutil.copy2(HEX, HEX0)
    b, P, w, h, g, f, names = load(HEX0)
    _, _, w0, h0, g0, f0, names0 = load(STOCK)
    assert names == names0
    G = g.copy()                                    # edited raw bytes
    imp = f["imp"].copy(); slot = f["slot"].copy(); sprawl = f["sprawl"].copy(); road = f["road"].copy()
    log = {"A": {}, "B": {}, "skipped": []}
    towns = sorted({int(k) for k in np.unique(f["region"][f["slot"] == 0])})
    hazard_static = (f["river"] > 0) | (f["terr"] != 0) | (f["bridge"] > 0)
    # river runs along hex edges: the hex across a river edge counts as river terrain too (CAIME sprawl validator)
    for r, c in zip(*np.nonzero(f["river"] > 0)):
        for d, nc, nr in nbrs(int(c), int(r), w, h):
            if (f["river"][r, c] >> d) & 1: hazard_static[nr, nc] = True

    # ---- A: restore stock impassable pattern around towns
    for k in towns:
        if names[k] in MOVE or names[k] in A_SKIP: continue
        F0, F1 = footprint(f0, k), footprint(f, k)
        R0 = ring(F0, w0, h0)
        stock_imp = [p for p in R0 if f0["imp"][p[1], p[0]]]
        if not stock_imp: continue
        T = translation(F0, F1)
        if T is None: log["skipped"].append(names[k]); continue
        added = []
        for p in stock_imp:
            c, r = cube_shift(p, T)
            if not (0 <= c < w and 0 <= r < h) or (c, r) in F1: continue
            if f["terr"][r, c] == 1 or road[r, c] or f["bridge"][r, c] or imp[r, c]: continue
            imp[r, c] = 1; added.append((c, r))
        if added: log["A"][names[k]] = {"stock_ring_imp": len(stock_imp), "added": added}

    # ---- B: move river towns away from the river
    for name in MOVE:
        k = names.index(name); F = footprint(f, k)
        haz = hazard_static | (imp > 0)
        # distance (hex steps) from hazard, BFS limited to the town's neighbourhood
        cs = [p[0] for p in F]; rs = [p[1] for p in F]
        c0, c1, r0, r1 = max(0, min(cs) - 20), min(w, max(cs) + 21), max(0, min(rs) - 20), min(h, max(rs) + 21)
        dist = np.full((h, w), 99, int); q = deque()
        for r in range(r0, r1):
            for c in range(c0, c1):
                if haz[r, c]: dist[r, c] = 0; q.append((c, r))
        while q:
            c, r = q.popleft()
            for _, nc, nr in nbrs(c, r, w, h):
                if c0 <= nc < c1 and r0 <= nr < r1 and dist[nr, nc] > dist[r, c] + 1:
                    dist[nr, nc] = dist[r, c] + 1; q.append((nc, nr))
        best = None
        for dq in range(-MAXMOVE, MAXMOVE + 1):
            for dr in range(-MAXMOVE, MAXMOVE + 1):
                n = max(abs(dq), abs(dr), abs(dq + dr))
                if n == 0 or n > MAXMOVE: continue
                F2 = {cube_shift(p, (dq, dr)) for p in F}
                ok = all(0 <= c < w and 0 <= r < h and f["region"][r, c] == k and f["terr"][r, c] == 0 and not imp[r, c]
                         and not hazard_static[r, c] for c, r in F2)
                if not ok: continue
                clear = min(dist[r, c] for c, r in F2)
                score = (clear < CLEAR, n, -clear)
                if best is None or score < best[0]: best = (score, (dq, dr), F2, clear)
        if best is None: log["skipped"].append(name); continue
        _, T, F2, clear = best
        # roads that end at the old footprint: their outside end hexes
        ends = set()
        for c, r in F:
            for d, nc, nr in nbrs(c, r, w, h):
                if (nc, nr) not in F and road[nr, nc] and (road[nr, nc] >> ((d + 3) % 6)) & 1:
                    ends.add((nc, nr)); road[nr, nc] &= ~(1 << ((d + 3) % 6))
        old_slot = {p: (int(slot[p[1], p[0]]), int(sprawl[p[1], p[0]])) for p in F}
        for c, r in F: slot[r, c] = -1; sprawl[r, c] = 0; road[r, c] = 0
        for p, (s, sp) in old_slot.items():
            c, r = cube_shift(p, T); slot[r, c] = s; sprawl[r, c] = sp; imp[r, c] = 0
        drawn = []
        for e in sorted(ends):
            tgt = min(F2, key=lambda p: (abs(to_cube(*p)[0] - to_cube(*e)[0]) + abs(to_cube(*p)[1] - to_cube(*e)[1]) +
                                          abs(to_cube(*p)[2] - to_cube(*e)[2])))
            path = hex_line(e, tgt)
            for a, bb in zip(path, path[1:]):
                d = direction_between(a, bb)
                if d < 0: continue
                road[a[1], a[0]] |= 1 << d; road[bb[1], bb[0]] |= 1 << ((d + 3) % 6); imp[a[1], a[0]] = 0
            drawn.append([list(e), list(tgt), len(path)])
        log["B"][name] = {"shift_cube": T, "clearance": int(clear), "old_slot0": sorted(p for p, v in old_slot.items() if v[0] == 0)[:1],
                          "roads_redrawn": drawn}

    # ---- C: reproduce stock 190E's hazard contact. The upscaler redrew rivers on their scaled course but kept towns
    # at their original size, so a river that hugged a town in 190E now passes a hex away (Linxiang, Linjing,
    # Luoyang, Bushan, Wushang lost their city bars). Every hex next to the stock footprint that was river /
    # impassable / beach / cliff / sea is, relative to the town, made impassable if it is now plain passable land
    # (never roads / bridges).
    log["C"] = {}
    def stock_haz(c, r): return bool(f0["imp"][r, c] or f0["river"][r, c] or f0["terr"][r, c] != 0)
    def now_haz(c, r): return bool(imp[r, c] or f["river"][r, c] or f["terr"][r, c] != 0)
    for k in towns:
        if names[k] in log["B"] or names[k] in C_SKIP or names[k] in PORT_FIX: continue
        F0, F1 = footprint(f0, k), footprint(f, k)
        T = translation(F0, F1)
        if T is None: continue
        added = []
        for p in ring(F0, w0, h0):
            if not stock_haz(*p): continue
            c, r = cube_shift(p, T)
            if not (0 <= c < w and 0 <= r < h) or (c, r) in F1 or now_haz(c, r): continue
            if road[r, c] or f["bridge"][r, c]: continue
            imp[r, c] = 1; added.append((c, r))
        if added: log["C"][names[k]] = added

    # ---- D: close every one-hex gap between a town and a hazard two hexes out (Wushang: the impassable mass to its
    # west sits one passable hex away); towns in D_SKIP would border a second hazard patch (CAIME bottleneck rule)
    log["D"] = {}
    for k in towns:
        if names[k] in log["B"] or names[k] in D_SKIP or names[k] in PORT_FIX: continue
        F = footprint(f, k); R1 = ring(F, w, h); R2 = ring(F | R1, w, h)
        hz = lambda c, r: bool(imp[r, c] or f["river"][r, c] or f["terr"][r, c] in (2, 3))
        near = {p for p in R2 if hz(*p)}
        added = []
        for c, r in R1:
            if hz(c, r) or f["terr"][r, c] != 0 or road[r, c] or f["bridge"][r, c]: continue
            if any((nc, nr) in near for _, nc, nr in nbrs(c, r, w, h)):
                imp[r, c] = 1; added.append((c, r))
        if added: log["D"][names[k]] = added

    # ---- P: ports in PORT_FIX - land ring hexes touching sea / beach / cliff become impassable (not roads / bridges)
    log["P"] = {}
    for name in PORT_FIX:
        k = names.index(name); F = footprint(f, k); added = []
        for c, r in ring(F, w, h):
            if f["terr"][r, c] != 0 or road[r, c] or f["bridge"][r, c] or imp[r, c]: continue
            if any(f["terr"][nr, nc] != 0 for _, nc, nr in nbrs(c, r, w, h)):
                imp[r, c] = 1; added.append((c, r))
        log["P"][name] = added

    # ---- write the edited fields back into the raw bytes (byte2: slot<<4 | imp<<3 | low3; byte3: bridge, road, sprawl)
    G[..., 2] = ((((slot + 1) & 15) << 4) | ((imp & 1) << 3) | (g[..., 2] & 7)).astype(np.uint8)
    G[..., 3] = ((g[..., 3] & 0x80) | ((road & 63) << 1) | (sprawl & 1)).astype(np.uint8)
    # ---- S: ports whose local layout (town + harbour slots + 1 ring) no longer matches stock 190E (the upscaler's
    # coastline repair turned a Huangxian town hex into sea and town-edge hexes into cliff): copy stock's raw hex
    # records for the town, its harbour slots and 2 rings around them, placed at the town's upscaled position;
    # road / river edge bits are then made symmetric across the stamp edge.
    log["S"] = {}
    for name in PORT_FIX:
        if name in STAMP_SKIP: continue
        k = names.index(name); F0 = footprint(f0, k); F1 = footprint(f, k)
        T_ = translation(F0, F1)
        if T_ is None: continue
        town0 = set(F0) | {(nc, nr) for c, r in F0 for _, nc, nr in nbrs(c, r, w0, h0) if f0["slot"][nr, nc] >= 0}
        R1 = ring(town0, w0, h0); R2 = ring(town0 | R1, w0, h0)
        def sig(ff, c, r): return (int(ff["terr"][r, c]), int(ff["imp"][r, c] > 0), int(ff["slot"][r, c]), int(ff["sprawl"][r, c]), int(ff["region"][r, c]))
        diff = 0
        for p0 in town0 | R1:
            c, r = cube_shift(p0, T_)
            if not (0 <= c < w and 0 <= r < h): diff += 99; continue
            cur = (int(f["terr"][r, c]), int(imp[r, c] > 0), int(slot[r, c]), int(sprawl[r, c]), int(f["region"][r, c]))
            diff += cur != sig(f0, *p0)
        if not diff: continue
        area = []
        for p0 in town0 | R1 | R2:
            c, r = cube_shift(p0, T_)
            if 0 <= c < w and 0 <= r < h: G[r, c] = g0[p0[1], p0[0]]; area.append((c, r))
        aset = set(area)
        for c, r in list(aset):
            for d, nc, nr in nbrs(c, r, w, h):
                for byte, shift in ((3, 1), (4, 0)):        # road bits (byte3 bits 1-6), river bits (byte4 bits 0-5)
                    a = (int(G[r, c, byte]) >> (shift + d)) & 1; bb = (int(G[nr, nc, byte]) >> (shift + (d + 3) % 6)) & 1
                    if a and not bb: G[nr, nc, byte] = np.uint8(int(G[nr, nc, byte]) | (1 << (shift + (d + 3) % 6)))
                    if bb and not a: G[r, c, byte] = np.uint8(int(G[r, c, byte]) | (1 << (shift + d)))
        log["S"][name] = {"differing_hexes": diff, "stamped": len(area)}

    out = bytearray(b); out[P + 8:P + 8 + 16 * w * h] = G.tobytes()
    out[-4:] = struct.pack("<I", zlib.crc32(bytes(out[:-4])) & 0xFFFFFFFF)
    HEX.write_bytes(bytes(out))
    json.dump(log, open(HERE / "town_fix.json", "w"), indent=1)
    print(f"A: impassable restored around {len(log['A'])} towns ({sum(len(v['added']) for v in log['A'].values())} hexes)")
    for n_, v in log["B"].items(): print(f"B: {n_} moved {v['shift_cube']} clearance {v['clearance']} roads {len(v['roads_redrawn'])}")
    print(f"C: gap closed at {len(log['C'])} towns ({sum(len(v) for v in log['C'].values())} hexes)")
    print(f"D: one-hex gaps closed at {len(log['D'])} towns ({sum(len(v) for v in log['D'].values())} hexes); D_SKIP {sorted(D_SKIP)}")
    print("P:", {k: len(v) for k, v in log["P"].items()})
    print("S (stamped from stock):", log["S"])
    print("skipped:", log["skipped"])


if __name__ == "__main__":
    main()
