#!/usr/bin/env python3
"""City bars vs "hourglass" corridors (user 2026-10-01, quoting a CAIME dev: "avoid hourglass-shaped corridors - rivers,
beaches, cliff, other slots, impassable"). A hex is pinched when, by CAIME's PlugHolesImpassable test (IsStandable:
passable, no river / beach / cliff unless sprawl, not a slot hex), its neighbour ring reads 010 / 011011 / 000000.
Every town with a pinched hex within 2 hexes of its footprint (Dantu, Wan, Zhaoling, Yuanling + 27 more; none on the
towns that show bars) is fixed:
  * inland towns: footprint translated (cube coords) to the nearest spot in its region where the footprint + 2 rings
    have no pinch AND CAIME's sprawl rule holds (<= 1 hazard patch touching, none within 2 hexes not touching);
    cut roads re-routed (BFS, no river crossings);
  * ports (slot 1+) or no such spot: pinched hexes outside the footprint (not road / bridge) become impassable,
    repeated until clean, kept only if CAIME's sprawl rule still holds.
In place on hex/map.hex (backup hex/map_pre_pinch_<ts>.hex); log town_pinch_fix.json. Args: region keys (default all)."""
import json, shutil, struct, sys, time, zlib
from collections import deque
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
import town_fix as T
from hexgrid import neighbour, direction_between
MAXMOVE = 8
HEX = HERE / "hex" / "map.hex"
DRY = "--dry" in sys.argv
if not DRY: shutil.copy2(HEX, HERE / "hex" / f"map_pre_pinch_{time.strftime('%Y%m%d_%H%M%S')}.hex")
b, P, w, h, g, f, names = T.load(HEX)
G = g.copy(); imp = f["imp"].copy(); slot = f["slot"].copy(); sprawl = f["sprawl"].copy(); road = f["road"].copy()
terr, river, bridge, reg = f["terr"], f["river"], f["bridge"], f["region"]
NB = {}


def nb(c, r):
    k = (c, r)
    if k not in NB: NB[k] = [neighbour(c, r, d) for d in range(6)]
    return NB[k]


def inb(p): return 0 <= p[0] < w and 0 <= p[1] < h


def standable(c, r):
    s = sprawl[r, c] > 0
    return (((terr[r, c] == 0) or (terr[r, c] > 1 and (s or bridge[r, c]))) and (river[r, c] == 0 or s)
            and not imp[r, c] and slot[r, c] < 0)


def pinched(c, r):
    if not standable(c, r): return False
    s = [inb(q) and standable(*q) for q in nb(c, r)]
    for d in range(6):
        a = [s[(d + i) % 6] for i in range(6)]
        if (not a[0] and a[1] and not a[2]) or (not a[0] and a[1] and a[2] and not a[3] and a[4] and a[5]) or not any(a):
            return True
    return False


def rings(F, n):
    area = set(F); out = []
    for _ in range(n):
        ring = {q for p in area for q in nb(*p) if inb(q)} - area; out.append(ring); area |= ring
    return area, out


def hazard(c, r): return bool(imp[r, c] or river[r, c] or terr[r, c] > 1)


def hazard_ok(F):
    """CAIME SprawlValidator.ValidateHazardOutline: <= 1 hazard component touching, none in the 2-ring not touching."""
    _, (r1, r2) = rings(F, 2)
    hz = {p for p in r1 | r2 if hazard(*p)}
    comp = {}; cid = 0
    for p in hz:
        if p in comp: continue
        st = [p]; comp[p] = cid
        while st:
            a = st.pop()
            for q in nb(*a):
                if inb(q) and q not in comp and q not in F and hazard(*q) and abs(q[0] - p[0]) < 60 and abs(q[1] - p[1]) < 60:
                    comp[q] = cid; st.append(q)
        cid += 1
    touch = {comp[p] for p in r1 if p in comp}
    return len(touch) <= 1 and all(comp[p] in touch for p in hz)


def town_pinches(F):
    area, _ = rings(F, 2)
    return [p for p in area if pinched(*p)]


def footprint(k):
    return {(int(c), int(r)) for r, c in zip(*np.nonzero(((slot >= 0) | (sprawl > 0)) & (reg == k)))}


args = [a for a in sys.argv[1:] if not a.startswith("--")]
keys = args or [names[int(k)] for k in sorted({int(x) for x in np.unique(reg[slot == 0])})]
log = {}
for name in keys:
    k = names.index(name); F = footprint(k)
    pin = town_pinches(F)
    if not pin: continue
    port = bool(((slot > 0) & (reg == k)).any())
    entry = {"pinched_before": len(pin), "port": port, "hazard_ok_before": hazard_ok(F)}
    moved = False
    if not port:
        old = {p: (int(slot[p[1], p[0]]), int(sprawl[p[1], p[0]])) for p in F}
        town_other = ((slot >= 0) | (sprawl > 0)) & (reg != k)
        cands = sorted((max(abs(dq), abs(dr), abs(dq + dr)), dq, dr) for dq in range(-MAXMOVE, MAXMOVE + 1)
                       for dr in range(-MAXMOVE, MAXMOVE + 1) if 0 < max(abs(dq), abs(dr), abs(dq + dr)) <= MAXMOVE)

        def place(mapping):
            for c, r in F: slot[r, c] = -1; sprawl[r, c] = 0
            for p, (s, sp) in mapping.items(): slot[p[1], p[0]] = s; sprawl[p[1], p[0]] = sp

        for n, dq, dr in cands:
            m2 = {T.cube_shift(p, (dq, dr)): v for p, v in old.items()}
            F2 = set(m2)
            if not all(inb(p) and reg[p[1], p[0]] == k and terr[p[1], p[0]] == 0 and not imp[p[1], p[0]]
                       and not river[p[1], p[0]] and not bridge[p[1], p[0]] for p in F2): continue
            a2, _ = rings(F2, 1)
            if any(town_other[q[1], q[0]] for q in a2): continue
            place(m2)
            cur = F2
            if hazard_ok(F2) and not town_pinches(F2):
                moved = True; entry.update(move=[dq, dr], dist=n)
                ends = set()
                for c, r in F:
                    for d, q in enumerate(nb(c, r)):
                        if inb(q) and q not in F and q not in F2 and road[q[1], q[0]] and (road[q[1], q[0]] >> ((d + 3) % 6)) & 1:
                            ends.add(q); road[q[1], q[0]] &= ~(1 << ((d + 3) % 6))
                for c, r in F:
                    if (c, r) not in F2: road[r, c] = 0
                rr = []
                for e in sorted(ends):
                    prev = {e: None}; qu = deque([e]); hit = None
                    while qu and hit is None:
                        a = qu.popleft()
                        for d, q in enumerate(nb(*a)):
                            if not inb(q) or q in prev or abs(q[0] - e[0]) > 30 or abs(q[1] - e[1]) > 30: continue
                            if (river[a[1], a[0]] >> d) & 1 or terr[q[1], q[0]] != 0 or (imp[q[1], q[0]] and q not in F2): continue
                            prev[q] = a
                            if q in F2: hit = q; break
                            qu.append(q)
                    if hit is None: rr.append(None); continue
                    path = [hit]
                    while prev[path[-1]] is not None: path.append(prev[path[-1]])
                    path.reverse()
                    for a, bq in zip(path, path[1:]):
                        d = direction_between(a, bq); road[a[1], a[0]] |= 1 << d; road[bq[1], bq[0]] |= 1 << ((d + 3) % 6)
                    rr.append(len(path))
                entry["roads"] = rr
                break
            for c, r in F2: slot[r, c] = -1; sprawl[r, c] = 0
            place(old)
    if not moved:
        F = footprint(k); added = []
        for _ in range(6):
            pin = [p for p in town_pinches(F) if p not in F and not road[p[1], p[0]] and not bridge[p[1], p[0]] and terr[p[1], p[0]] == 0]
            if not pin: break
            for c, r in pin: imp[r, c] = 1; added.append((c, r))
        if added and not hazard_ok(F):
            for c, r in added: imp[r, c] = 0
            entry["fill_rejected"] = len(added)
        else:
            entry["filled"] = added
        if not port and town_pinches(F):                      # no clear spot (Wan): open the region's own impassable land
            for c, r in added: imp[r, c] = 0                  # around the town, 1-3 rings deep, until clean
            for depth in (1, 2, 3):
                area, _ = rings(F, depth)
                cl = [p for p in area if p not in F and imp[p[1], p[0]] and terr[p[1], p[0]] == 0 and reg[p[1], p[0]] == k]
                for c, r in cl: imp[r, c] = 0
                if not town_pinches(F) and hazard_ok(F): entry["opened"] = cl; break
                for c, r in cl: imp[r, c] = 1
            else:
                for c, r in added: imp[r, c] = 1
    F = footprint(k)
    entry["pinched_after"] = len(town_pinches(F)); entry["hazard_ok_after"] = hazard_ok(F)
    log[name] = entry; print(name, entry)
print(len(log), "towns treated;", sum(1 for v in log.values() if v["pinched_after"]), "still pinched")
if not DRY:
    G[..., 2] = ((((slot + 1) & 15) << 4) | ((imp & 1) << 3) | (g[..., 2] & 7)).astype(np.uint8)
    G[..., 3] = ((g[..., 3] & 0x80) | ((road & 63) << 1) | (sprawl & 1)).astype(np.uint8)
    out = bytearray(b); out[P + 8:P + 8 + 16 * w * h] = G.tobytes()
    out[-4:] = struct.pack("<I", zlib.crc32(bytes(out[:-4])) & 0xFFFFFFFF); HEX.write_bytes(bytes(out))
    json.dump(log, open(HERE / "town_pinch_fix.json", "w"), indent=1)
