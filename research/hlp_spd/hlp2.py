"""HLP prototype v2 (clean): the game's A*-family grid (nav bit 7, beach edges gated by the search's HLCIs, port links),
phase 1 (FIND_REGION_BORDER), determine_transition_points with descending (x,y) sets, transition costs, matrix.
usage: hlp2.py [key=value ...]   knobs: centre=zero|blocked  cost=zero|blocked  matrix=blocked|zero"""
import heapq, pickle, sys, os
import numpy as np
from ppd import DIRS
from hlp_parse import parse

K = dict(centre="zero", cost="blocked", matrix="blocked", order="desc", strict="True", last="-1", vec="AB")


def hexdist(a, b):
    (x1, y1), (x2, y2) = a, b
    s3 = x1 - x2; s2 = ((x1 + 1) >> 1) - ((x2 + 1) >> 1) - y2 + y1; s1 = s3 - s2
    return max(abs(s3), abs(s2), abs(s1))


class Grid:
    def __init__(self, p, model_zero, model_plain, slots, hlci):
        self.p = p
        self.e_zero, self.types, self.costs, self.links = model_zero
        self.e_plain = model_plain[0]
        self.slot = np.zeros((p.H, p.W), bool)
        for x, y in slots: self.slot[y, x] = True
        self.hlci = hlci
        self.gate_cache = {}

    def gated(self, settle, cc, ce):
        key = (settle, cc, ce)
        if key in self.gate_cache: return self.gate_cache[key]
        e = (self.e_zero if settle == "zero" else self.e_plain).copy()
        for a, l, ent, lev in self.p.beaches:
            on_e = cc != ce and a == cc
            on_l = cc != ce and l == cc
            for (x, y, m) in ent:
                for k in range(6):
                    if m >> k & 1: e[y, x, k] = (e[y, x, k] | 0x80) if on_e else (e[y, x, k] & 0x7F)
            for (x, y, m) in lev:
                for k in range(6):
                    if m >> k & 1: e[y, x, k] = (e[y, x, k] | 0x80) if on_l else (e[y, x, k] & 0x7F)
        self.gate_cache[key] = e
        return e

    def neighbours(self, e, x, y, reverse=False):
        p = self.p
        for k, (dq, dr) in enumerate(DIRS[x & 1]):
            nx, ny = x + dq, y + dr
            if not (0 <= nx < p.W and 0 <= ny < p.H): continue
            eb = e[ny, nx, (k + 3) % 6] if reverse else e[y, x, k]
            if not eb & 0x80: continue
            yield (nx, ny), int(self.costs[eb & 0x7F])
        if self.types[y, x] == 5:
            for h in self.links.get((x, y), ()):
                if self.types[h[1], h[0]] == 5: yield h, 500

    def dijkstra(self, src, settle, cc, ce, targets=None, stop=None, blocked_ok=()):
        """settle=blocked: slot hexes cannot be entered (except those in blocked_ok)."""
        e = self.gated(settle, cc, ce)
        dist = {src: 0}; prev = {}; done = set(); pq = [(0, 0, src)]; n = 0
        remaining = set(targets) if targets else None
        while pq:
            d, _, u = heapq.heappop(pq)
            if u in done: continue
            done.add(u)
            if stop is not None and stop(u, d): break
            if remaining is not None:
                remaining.discard(u)
                if not remaining: break
            for v, c in self.neighbours(e, u[0], u[1]):
                if v in done: continue
                if settle == "blocked" and self.slot[v[1], v[0]] and v not in blocked_ok: continue
                nd = d + c
                if nd < dist.get(v, 1 << 62):
                    dist[v] = nd; prev[v] = u; n += 1
                    heapq.heappush(pq, (nd, n, v))
        return dist, prev, done

    def path(self, a, b, settle):
        cc, ce = int(self.hlci[a[1], a[0]]), int(self.hlci[b[1], b[0]])
        dist, prev, done = self.dijkstra(a, settle, cc, ce, targets=[b], blocked_ok=(b,))
        if b not in done: return None, []
        pth = [b]
        while pth[-1] != a: pth.append(prev[pth[-1]])
        return dist[b], pth[::-1]


def phase1(G, am, aid, centre):
    H = int(G.hlci[centre[1], centre[0]])
    e = G.gated("zero", H, 0)
    done = set(); pq = [(0, centre)]; b = 0; borders = {}; order = []
    while pq:
        d, (x, y) = heapq.heappop(pq)
        if (x, y) in done: continue
        done.add((x, y))
        t = G.types[y, x]
        if t in (0, 1):
            a = int(am[y, x])
            if a == aid: b = max(b, d)
            else:
                if a not in borders: borders[a] = set(); order.append(a)
                borders[a].add((x, y)); continue
        for h, c in G.neighbours(e, x, y):
            if h not in done: heapq.heappush(pq, (d + c, h))
    return b, borders, order


def SK(h):
    return (-h[0], -h[1]) if K["order"] == "desc" else h


def nearest(sset, pt):
    best = None; bd = None
    for h in sorted(sset, key=SK):
        d = hexdist(h, pt)
        if bd is None or d < bd: best, bd = h, d
    return best


def build_entries(G, am, ra):
    entries = []
    for r, R in enumerate(ra):
        for i, a in enumerate(R["areas"]):
            if a["type"] not in (0, 3, 4): continue
            aid = r | (i << 9)
            centre = a["centre"]
            if R["settlement"] is not None:
                sx, sy = R["settlement"]
                if am[sy, sx] == aid: centre = (sx, sy)
            entries.append(dict(region=r, aid=aid, centre=centre, a=a["id"], type=a["type"]))
    for E in entries:
        b, borders, order = phase1(G, am, E["aid"], E["centre"])
        E["b"] = b
        E["segs"] = [dict(nb=nb, border=borders[nb]) for nb in order]
    return entries


PC = {}
def cost(G, a, b):
    if a == b: return 0
    if (a, b) not in PC: PC[(a, b)] = G.path(a, b, K["cost"])[0]
    return PC[(a, b)]


CP = {}
def determine(G, ra, E, S, T, F):
    def atype(aid): return ra[aid & 0x1FF]["areas"][aid >> 9]["type"]
    f1 = (atype(E["aid"]) == 0) != (atype(F["aid"]) == 0)
    key = (E["centre"], F["centre"])
    if key not in CP: CP[key] = [] if K["centre"] == "none" else G.path(E["centre"], F["centre"], K["centre"])[1]
    path = CP[key]
    q = pp = None
    for h in path:
        if h in T["border"]: pp = h
        if q is None and h in S["border"]: q = h
    copyA = set(S["border"]); copyB = set(T["border"])
    def emit(pa, qb):
        cab = cost(G, pa, qb); cba = cost(G, qb, pa)
        E["tr"].append(dict(p=pa, q=qb, cost=cab, to=F["aid"], idx=len(E["tr"]), f1=f1, f2=False))
        F["tr"].append(dict(p=qb, q=pa, cost=cba, to=E["aid"], idx=len(F["tr"]), f1=f1, f2=False))
    if pp is not None and q is not None:
        emit(pp, q)
        copyA = {h for h in copyA if hexdist(h, q) >= 10}
        copyB = {h for h in copyB if hexdist(h, pp) >= 10}
    while True:
        vec = sorted(copyA, key=SK) + sorted(copyB, key=SK)
        if not vec: break
        last = vec[-1]
        cluster = set(); stack = [last]
        while stack:
            u = stack.pop()
            if u in cluster: continue
            cluster.add(u)
            for v in vec:
                if hexdist(u, v) == 1 and v not in cluster: stack.append(v)
        c = (sum(h[0] for h in cluster) // len(cluster), sum(h[1] for h in cluster) // len(cluster))
        bc = nearest(copyA, c); ac = nearest(copyB, c)
        ok = False
        if bc is not None and ac is not None:
            n150 = nearest(S["border"], ac); n14c = nearest(T["border"], bc)
            if hexdist(bc, ac) < 2 * hexdist(n150, ac) and hexdist(bc, ac) < 2 * hexdist(bc, n14c): ok = True
        if ok:
            emit(ac, bc)
            copyA = {h for h in copyA if hexdist(h, bc) >= 10}
            copyB = {h for h in copyB if hexdist(h, ac) >= 10}
        else:
            copyA.discard(last); copyB.discard(last)


def match(G, ra, entries):
    by = {E["aid"]: E for E in entries}
    for E in entries:
        E["tr"] = []
        for S in E["segs"]: S["matched"] = False
    for E in entries:
        for S in E["segs"]:
            if S["matched"]: continue
            F = by.get(S["nb"])
            if F is None: continue
            T = next((s for s in F["segs"] if s["nb"] == E["aid"]), None)
            if T is None: continue
            determine(G, ra, E, S, T, F)
            S["matched"] = T["matched"] = True


def matrix(G, E):
    tr = E["tr"]; out = []
    for t in tr:
        others = [u["p"] for u in tr if u is not t]
        dist, _, _ = G.dijkstra(t["p"], K["matrix"], 0, 0, targets=others or None, blocked_ok=tuple(others))
        out.extend(dist.get(u["p"]) for u in tr if u is not t)
    return out


def compare(nodes, entries, with_matrix=False):
    ref = {s["area"]: s for n in nodes for s in n["subs"]}
    mine = {E["aid"]: E for E in entries}
    st = dict(areas=len(set(ref) & set(mine)), centre=0, a=0, b=0, ntr=0, trset=0, pq=0, pq_cost=0, mat=0)
    tot = 0
    for aid, s in ref.items():
        E = mine[aid]
        st["centre"] += E["centre"] == s["centre"]; st["a"] += E["a"] == s["a"]; st["b"] += E["b"] == s["b"]
        st["ntr"] += len(E["tr"]) == len(s["tr"])
        rs = {(t["p"], t["q"], t["to"]): t for t in s["tr"]}
        ms = {(t["p"], t["q"], t["to"]): t for t in E["tr"]}
        st["trset"] += set(rs) == set(ms)
        tot += len(rs)
        common = set(rs) & set(ms)
        st["pq"] += len(common)
        st["pq_cost"] += sum(rs[k]["cost"] == ms[k]["cost"] for k in common)
    st["transitions"] = tot
    return st


if __name__ == "__main__":
    for kv in sys.argv[1:]:
        k, v = kv.split("="); K[k] = v
    p = pickle.load(open("/tmp/ppd07.pkl", "rb"))
    mz = pickle.load(open("/tmp/model07c.pkl", "rb")); mp = pickle.load(open("/tmp/model07.pkl", "rb"))
    am, ra = pickle.load(open("/tmp/areas07.pkl", "rb"))
    prim, port = pickle.load(open("/tmp/slots07.pkl", "rb"))
    hl = np.load("/tmp/hlci07.npy")
    G = Grid(p, mz, mp, prim | port, hl)
    h, nodes, _, _ = parse("../../output/hlp_spd/vanilla/campaign_maps/3k_dlc07_main_map/hlp_data.esf")
    cache = "/tmp/hlp2_entries07.pkl"
    if os.path.exists(cache): entries = pickle.load(open(cache, "rb"))
    else:
        entries = build_entries(G, am, ra); pickle.dump(entries, open(cache, "wb"))
    match(G, ra, entries)
    pickle.dump(entries, open("/tmp/hlp2_result07.pkl", "wb"))
    print(K, compare(nodes, entries))
