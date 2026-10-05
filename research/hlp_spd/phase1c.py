import heapq, numpy as np
from ppd import DIRS
NAVBIT = 0x80
def expand(p, model, x, y, mode=None, reverse=False):
    e, types, costs, links = model
    for k, (dq, dr) in enumerate(DIRS[x & 1]):
        nx, ny = x + dq, y + dr
        if not (0 <= nx < p.W and 0 <= ny < p.H): continue
        eb = e[ny, nx, (k + 3) % 6] if reverse else e[y, x, k]
        if eb & NAVBIT != NAVBIT: continue
        yield (nx, ny), None, costs[eb & 0x7F]
    if types[y, x] == 5:
        for h in links.get((x, y), ()):
            if types[h[1], h[0]] == 5: yield h, None, 500
def phase1(p, model, am, area_idx, centre, hlci=None):
    e, types, costs, links = model
    done = set(); pq = [(0, centre)]; b = 0; borders = {}; order = []
    while pq:
        d, (x, y) = heapq.heappop(pq)
        if (x, y) in done: continue
        done.add((x, y))
        t = types[y, x]
        if t in (0, 1):
            a = int(am[y, x])
            if a == area_idx: b = max(b, d)
            else:
                if a not in borders: borders[a] = set(); order.append(a)
                borders[a].add((x, y)); continue
        for h, nm, c in expand(p, model, x, y):
            if hlci is not None and hlci[h[1], h[0]] != hlci[y, x]: continue
            if h not in done: heapq.heappush(pq, (d + c, h))
    return b, borders, order
