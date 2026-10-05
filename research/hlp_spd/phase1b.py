import heapq, numpy as np
from gamepf import type_masks
from ppd import DIRS
MASKS = type_masks(extended=True)
LANDISH = (0, 4, 5, 6, 7, 8, 9)
def expand(p, model, x, y, mode, reverse=False):
    """mode for beach hexes: 'L' entered from land (may only go on to sea), 'S' entered from sea (only to land)."""
    e, types, costs, links = model
    t = types[y, x]
    tm = MASKS[t]
    for k, (dq, dr) in enumerate(DIRS[x & 1]):
        nx, ny = x + dq, y + dr
        if not (0 <= nx < p.W and 0 <= ny < p.H): continue
        u = types[ny, nx]
        if not tm >> u & 1: continue
        if t == 3:
            if mode == 'L' and u != 1: continue
            if mode == 'S' and u == 1: continue
        c = costs[e[ny, nx, (k + 3) % 6] & 0x7F] if reverse else costs[e[y, x, k] & 0x7F]
        nm = None
        if u == 3: nm = 'S' if t == 1 else 'L'
        yield (nx, ny), nm, c
    for h in links.get((x, y), ()):
        yield h, None, 500
def phase1(p, model, am, area_idx, centre):
    e, types, costs, links = model
    done = set(); pq = [(0, centre, None)]; b = 0; borders = {}; order = []
    while pq:
        d, (x, y), mode = heapq.heappop(pq)
        key = (x, y, mode)
        if key in done: continue
        done.add(key)
        t = types[y, x]
        if t in (0, 1):
            a = int(am[y, x])
            if a == area_idx: b = max(b, d)
            else:
                if a not in borders: borders[a] = set(); order.append(a)
                borders[a].add((x, y)); continue
        for h, nm, c in expand(p, model, x, y, mode):
            if (h[0], h[1], nm) not in done: heapq.heappush(pq, (d + c, h, nm))
    return b, borders, order
