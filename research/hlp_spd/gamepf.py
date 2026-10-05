"""Python model of the game's CAMPAIGN_PATHFINDER grid and the SPD landmark search (empirecampaign FUN_18059f480)."""
import heapq, numpy as np
from ppd import DIRS

# allowed type transitions: MASK[t] bit u = may move from hex type t to type u (FUN_1805fa120 + FUN_1805d3a70)
def type_masks(extended=True):
    m = [0] * 10
    B = [(0,0),(1,1),(4,4),(8,8),(9,9),(0,6),(6,0),(1,3),(3,1),(0,4),(4,0),(1,8),(8,1),(1,7),(7,1),(0,5),(5,0),
         (4,5),(5,4),(8,7),(7,8),(4,6),(6,4),(8,3),(3,8),(9,0),(0,9),(9,3),(3,9),(9,4),(4,9),(9,5),(5,9)]
    A = [(0,3),(3,0),(0,7),(7,0),(4,7),(7,4),(4,3),(3,4),(9,7),(7,9)]
    for t, u in B + (A if extended else []):
        m[t] |= 1 << u
    return m

def build(p, road_cost=100, land_to_sea=1250, sea_to_land=1250, road_slot=0x3e):
    """Returns (edges[H,W,6] cost index, types[H,W], cost table[256], bridge links dict)."""
    e = p.cells[:, :, :6].copy()
    e = (e & 0xBF) | ((e >> 1) & 0x40)          # bit6 := bit7
    types = (p.cells[:, :, 7] >> 4).astype(np.int32)
    costs = np.zeros(256, np.int64)
    for i, c in enumerate(p.costs):
        for b in (0, 0x40, 0x80, 0xC0): costs[i + b] = c
    for b in (0, 0x40, 0x80, 0xC0):
        costs[1 + b] = land_to_sea; costs[2 + b] = sea_to_land
        costs[road_slot + b] = road_cost
    W, H = p.W, p.H
    def setmask(x, y, mask):
        for k in range(6):
            if mask >> k & 1: e[y, x, k] = (e[y, x, k] & 0xC0) | road_slot
    for pairs, hexes in p.roads:
        for x, y, m in hexes:
            if types[y, x] != 6:
                setmask(x, y, m)
            else:
                for k, (dq, dr) in enumerate(DIRS[x & 1]):
                    nx, ny = x + dq, y + dr
                    if 0 <= nx < W and 0 <= ny < H:
                        setmask(nx, ny, 1 << ((k + 3) % 6))
                    setmask(x, y, 1 << k)
    links = {}
    for a, b in p.bridges:
        for h in a: links.setdefault(h, []).extend(b)
        for h in b: links.setdefault(h, []).extend(a)
    return e, types, costs, links

def search(p, model, src, reverse=False, masks=None):
    e, types, costs, links = model
    masks = masks or type_masks()
    W, H = p.W, p.H
    INF = 0xFFFFFFFF
    dist = np.full((H, W), INF, np.int64)
    done = np.zeros((H, W), bool)
    pq = [(0, src)]
    while pq:
        d, (x, y) = heapq.heappop(pq)
        if done[y, x]: continue
        done[y, x] = True; dist[y, x] = d
        tm = masks[types[y, x]]
        for k, (dq, dr) in enumerate(DIRS[x & 1]):
            nx, ny = x + dq, y + dr
            if not (0 <= nx < W and 0 <= ny < H) or done[ny, nx]: continue
            if not tm >> types[ny, nx] & 1: continue
            c = costs[e[ny, nx, (k + 3) % 6] & 0x7F] if reverse else costs[e[y, x, k] & 0x7F]
            if c == -1: continue
            heapq.heappush(pq, (d + c, (nx, ny)))
        for h in links.get((x, y), ()):
            if not done[h[1], h[0]]:
                heapq.heappush(pq, (d + 500, h))
    return dist
