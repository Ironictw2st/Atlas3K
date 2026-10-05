"""Prototype of the CAI_TRANSITION_DATA builder (EMPIRECAMPAIGNAI::CAI_REGION_BORDER_ANALYSER), for field-level
comparison with CA's hlp_data.esf. Models:
  spd model (settlement slot edges cost 0)    -> phase 1 (b, border sets)
  blocked model (settlement slot hexes blocked) -> paths, transition costs, distance matrix
usage: hlp_proto.py  (vanilla dlc07, pickles from /tmp)"""
import heapq, pickle, sys, math
import numpy as np
from gamepf import type_masks
from ppd import DIRS
from phase1b import phase1, expand
from hlp_parse import parse

MASKS = type_masks()
PATH_MODEL = [None, None]


def hexdist(a, b):
    (x1, y1), (x2, y2) = a, b
    s3 = x1 - x2; s2 = ((x1 + 1) >> 1) - ((x2 + 1) >> 1) - y2 + y1; s1 = s3 - s2
    return max(abs(s3), abs(s2), abs(s1))


def neighbours(p, model, x, y, blocked, reverse=False):
    e, types, costs, links = model
    tm = MASKS[types[y, x]]
    for k, (dq, dr) in enumerate(DIRS[x & 1]):
        nx, ny = x + dq, y + dr
        if not (0 <= nx < p.W and 0 <= ny < p.H): continue
        if blocked is not None and blocked[ny, nx]: continue
        if not tm >> types[ny, nx] & 1: continue
        if not (e[ny, nx, (k + 3) % 6] if reverse else e[y, x, k]) & 0x80: continue
        c = costs[e[ny, nx, (k + 3) % 6] & 0x7F] if reverse else costs[e[y, x, k] & 0x7F]
        yield (nx, ny), c
    for h in links.get((x, y), ()):
        if blocked is None or not blocked[h[1], h[0]]:
            yield h, 500


def shortest_path(p, model, blocked, src, dst):
    dist = {(src, None): 0}; prev = {}
    pq = [(0, 0, src, None)]; n = 0; done = set(); end = None
    while pq:
        d, _, u, m = heapq.heappop(pq)
        if (u, m) in done: continue
        done.add((u, m))
        if u == dst: end = (u, m); break
        for v, nm, c in expand(p, model, u[0], u[1], m):
            if blocked is not None and blocked[v[1], v[0]] and v != dst: continue
            if (v, nm) in done: continue
            nd = d + c
            if nd < dist.get((v, nm), 1 << 62):
                dist[(v, nm)] = nd; prev[(v, nm)] = (u, m); n += 1
                heapq.heappush(pq, (nd, n, v, nm))
    if end is None: return None, []
    path = [end]
    while path[-1] != (src, None): path.append(prev[path[-1]])
    return dist[end], [h for h, _ in path[::-1]]


def shortest_path_old(p, model, blocked, src, dst):
    """Dijkstra src->dst (dst may be blocked); returns (cost, list of hexes)."""
    dist = {src: 0}; prev = {}
    pq = [(0, 0, src)]; n = 0
    done = set()
    while pq:
        d, _, u = heapq.heappop(pq)
        if u in done: continue
        done.add(u)
        if u == dst: break
        for v, c in neighbours(p, model, u[0], u[1], None if False else blocked):
            if v in done: continue
            nd = d + c
            if nd < dist.get(v, 1 << 62):
                dist[v] = nd; prev[v] = u; n += 1
                heapq.heappush(pq, (nd, n, v))
        # allow stepping onto the destination even if blocked
        if blocked is not None:
            for v, c in neighbours(p, model, u[0], u[1], None):
                if v == dst and v not in done:
                    nd = d + c
                    if nd < dist.get(v, 1 << 62):
                        dist[v] = nd; prev[v] = u; n += 1
                        heapq.heappush(pq, (nd, n, v))
    if dst not in dist: return None, []
    path = [dst]
    while path[-1] != src: path.append(prev[path[-1]])
    return dist[dst], path[::-1]


_PC = {}
_CP = {}
V = dict(vec='AB', strict=True, last=-1, order='xy')
def SK(h): return h if V['order'] == 'xy' else (-h[0], -h[1]) if V['order'] == 'desc' else (h[1], h[0])
def path_cost(p, model, blocked, a, b):
    if a == b: return 0
    if (a, b) in _PC: return _PC[(a, b)]
    _PC[(a, b)] = _path_cost(p, model, blocked, a, b)
    return _PC[(a, b)]


def _path_cost(p, model, blocked, a, b):
    c, _ = shortest_path(p, model, blocked, a, b)
    return c


def build(p, spd_model, blk_model, blocked, am, ra):
    nreg = len(ra)
    # area entries per region (types 0,3,4), with centre
    entries = {}
    for r, R in enumerate(ra):
        lst = []
        for i, a in enumerate(R["areas"]):
            if a["type"] not in (0, 3, 4): continue
            aid = r | (i << 9)
            centre = a["centre"]
            if R["settlement"] is not None:
                sx, sy = R["settlement"]
                if am[sy, sx] == aid: centre = (sx, sy)
            lst.append(dict(aid=aid, centre=centre, a=a["id"], type=a["type"], settled=centre == R["settlement"]))
        entries[r] = lst
    # phase 1
    for r in range(nreg):
        for E in entries[r]:
            b, borders, order = phase1(p, spd_model, am, E["aid"], E["centre"])
            E["b"] = b
            E["segs"] = [dict(nb=nb, border=set(borders[nb]), used=set(), matched=False) for nb in order]
            E["tr"] = []  # (p, q, cost, target, idx, f1, f2)
    return entries


def match(p, blk_model, blocked, entries, ra):
    nreg = len(ra)
    for r in entries:
        for E in entries[r]:
            E["tr"] = []
            for S in E["segs"]: S["matched"] = False; S["used"] = set()
    by_aid = {E["aid"]: E for r in entries for E in entries[r]}
    for r in range(nreg):
        for E in entries[r]:
            for S in E["segs"]:
                if S["matched"]: continue
                F = by_aid.get(S["nb"])
                if F is None: continue
                T = next((s for s in F["segs"] if s["nb"] == E["aid"]), None)
                if T is None: continue
                determine(p, blk_model, blocked, E, S, T, F, ra)
                S["matched"] = T["matched"] = True
    return entries


def area_type(ra, aid):
    return ra[aid & 0x1FF]["areas"][aid >> 9]["type"]


def add_tr(E, pp, qq, cost, target, f1, f2):
    E["tr"].append(dict(p=pp, q=qq, cost=cost, to=target, idx=len(E["tr"]), f1=f1, f2=f2))


def determine(p, model, blocked, E, S, T, F, ra):
    f1 = (area_type(ra, E["aid"]) == 0) != (area_type(ra, F["aid"]) == 0)
    key = (E["centre"], F["centre"])
    if key not in _CP: _CP[key] = shortest_path(p, PATH_MODEL[0], PATH_MODEL[1], E["centre"], F["centre"])[1]
    path = _CP[key]
    q = None; pp = None
    for h in path:
        if h in T["border"]: pp = h          # last A-hex on path
        if q is None and h in S["border"]: q = h   # first B-hex on path
    copyA = set(S["border"]); copyB = set(T["border"])   # B hexes, A hexes
    if pp is not None and q is not None:
        S["used"].add(q); T["used"].add(pp)
        cba = path_cost(p, model, blocked, q, pp); cab = path_cost(p, model, blocked, pp, q)
        add_tr(E, pp, q, cab, F["aid"], f1, False)
        add_tr(F, q, pp, cba, E["aid"], f1, False)
        copyA = {h for h in copyA if hexdist(h, q) >= 10}
        copyB = {h for h in copyB if hexdist(h, pp) >= 10}
    while True:
        vec = sorted(copyA, key=SK) + sorted(copyB, key=SK) if V['vec'] == 'AB' else sorted(copyB, key=SK) + sorted(copyA, key=SK)
        if not vec: break
        last = vec[V['last']]
        cluster = set(); stack = [last]
        while stack:
            u = stack.pop()
            if u in cluster: continue
            cluster.add(u)
            for v in vec:
                if hexdist(u, v) == 1 and v not in cluster: stack.append(v)
        cx = sum(h[0] for h in cluster) // len(cluster); cy = sum(h[1] for h in cluster) // len(cluster)
        def nearest(sset, pt):
            best = None; bd = None
            for h in sorted(sset, key=SK):
                d = hexdist(h, pt)
                if bd is None or d < bd or (not V['strict'] and d == bd): best, bd = h, d
            return best
        bcand = nearest(copyA, (cx, cy)); acand = nearest(copyB, (cx, cy))
        ok = False
        if bcand is not None and acand is not None:
            n150 = nearest(S["border"], acand); n14c = nearest(T["border"], bcand)
            if hexdist(bcand, acand) < 2 * hexdist(n150, acand) and hexdist(bcand, acand) < 2 * hexdist(bcand, n14c):
                ok = True
        if ok:
            S["used"].add(bcand); T["used"].add(acand)
            cba = path_cost(p, model, blocked, bcand, acand); cab = path_cost(p, model, blocked, acand, bcand)
            add_tr(E, acand, bcand, cab, F["aid"], f1, False)
            add_tr(F, bcand, acand, cba, E["aid"], f1, False)
            copyA = {h for h in copyA if hexdist(h, bcand) >= 10}
            copyB = {h for h in copyB if hexdist(h, acand) >= 10}
        else:
            copyA.discard(last); copyB.discard(last)


if __name__ == "__main__":
    p = pickle.load(open("/tmp/ppd07.pkl", "rb"))
    m7c = pickle.load(open("/tmp/model07c.pkl", "rb")); mh = pickle.load(open("/tmp/modelhlp.pkl", "rb"))
    am, ra = pickle.load(open("/tmp/areas07.pkl", "rb"))
    blocked = mh[1] == 2
    e, types, costs, links = pickle.load(open("/tmp/model07.pkl", "rb"))
    blk_model = (e, pickle.load(open("/tmp/model07.pkl", "rb"))[1], costs, links)
    h, nodes, _, _ = parse("../../output/hlp_spd/vanilla/campaign_maps/3k_dlc07_main_map/hlp_data.esf")
    slot_blocked = (mh[1] == 2) & (blk_model[1] != 2)
    PATH_MODEL[0] = m7c; PATH_MODEL[1] = None
    import os
    if os.path.exists("/tmp/hlp_phase1_07.pkl"): entries = pickle.load(open("/tmp/hlp_phase1_07.pkl", "rb"))
    else:
        entries = build(p, m7c, blk_model, slot_blocked, am, ra); pickle.dump(entries, open("/tmp/hlp_phase1_07.pkl", "wb"))
    if os.path.exists("/tmp/hlp_cache07.pkl"): _PC.update(pickle.load(open("/tmp/hlp_cache07.pkl", "rb"))[0]); _CP.update(pickle.load(open("/tmp/hlp_cache07.pkl", "rb"))[1])
    for kv in sys.argv[1:]:
        k, v = kv.split("="); V[k] = {"True": True, "False": False}.get(v, int(v) if v.lstrip("-").isdigit() else v)
    match(p, blk_model, slot_blocked, entries, ra)
    pickle.dump((_PC, _CP), open("/tmp/hlp_cache07.pkl", "wb"))
    pickle.dump(entries, open("/tmp/hlp_entries07.pkl", "wb"))
    # compare
    ref = {s["area"]: s for n in nodes for s in n["subs"]}
    mine = {E["aid"]: E for r in entries for E in entries[r]}
    print("areas ref", len(ref), "mine", len(mine), "common", len(set(ref) & set(mine)))
    stats = dict(centre=0, a=0, b=0, ntr=0, trset=0, trpq=0, cost=0)
    tot_tr = 0
    for aid, s in ref.items():
        E = mine.get(aid)
        if E is None: continue
        stats["centre"] += E["centre"] == s["centre"]
        stats["a"] += E["a"] == s["a"]
        stats["b"] += E["b"] == s["b"]
        stats["ntr"] += len(E["tr"]) == len(s["tr"])
        rs = {(t["p"], t["q"], t["to"]) for t in s["tr"]}
        ms = {(t["p"], t["q"], t["to"]) for t in E["tr"]}
        stats["trset"] += rs == ms
        tot_tr += len(rs)
        stats["trpq"] += len(rs & ms)
        rc = {(t["p"], t["q"]): t["cost"] for t in s["tr"]}
        stats["cost"] += sum(1 for t in E["tr"] if rc.get((t["p"], t["q"])) == t["cost"])
    print(stats, "transitions ref", tot_tr)
