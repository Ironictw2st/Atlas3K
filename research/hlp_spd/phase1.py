import heapq, numpy as np
from gamepf import type_masks
from ppd import DIRS
MASKS = type_masks()
NAV = 0x80
NOEXP = None
def phase1(p, model, am, area_idx, centre, hlci=None, alias=None):
    """Dijkstra from centre; own-area land/sea hexes: track max cost and expand; other-area land/sea hexes:
    record as border (per neighbour area) and do not expand; other hexes: expand without recording."""
    e, types, costs, links = model
    W, H = p.W, p.H
    done = {}
    pq = [(0, centre)]
    b = 0
    borders = {}
    while pq:
        d, (x, y) = heapq.heappop(pq)
        if (x, y) in done: continue
        done[(x, y)] = d
        t = types[y, x]
        expand = True
        if t in (0, 1):
            a = int(am[y, x])
            if alias is not None: a = alias.get(a, a)
            if a == area_idx:
                b = max(b, d)
            else:
                borders.setdefault(a, set()).add((x, y)); expand = False
        if not expand: continue
        if NOEXP is not None and t in NOEXP: continue
        tm = MASKS[t]
        for k, (dq, dr) in enumerate(DIRS[x & 1]):
            nx, ny = x + dq, y + dr
            if not (0 <= nx < W and 0 <= ny < H) or (nx, ny) in done: continue
            if not tm >> types[ny, nx] & 1: continue
            if hlci is not None and hlci[ny, nx] != hlci[y, x]: continue
            if NAV and not e[y, x, k] & NAV: continue
            heapq.heappush(pq, (d + costs[e[y, x, k] & 0x7F], (nx, ny)))
        for h in links.get((x, y), ()):
            if h not in done: heapq.heappush(pq, (d + 500, h))
    return b, borders, done
