import heapq, numpy as np
from ppd import DIRS
def dijkstra_mask(p, src, road, allowed, road_cost=100):
    W,H=p.W,p.H; INF=1<<62
    dist={src:0}; pq=[(0,src)]
    cells=p.cells; costs=p.costs
    while pq:
        d,(x,y)=heapq.heappop(pq)
        if d!=dist[(x,y)]: continue
        for k,(dq,dr) in enumerate(DIRS[x&1]):
            nx,ny=x+dq,y+dr
            if not (0<=nx<W and 0<=ny<H) or not allowed[ny,nx]: continue
            e=cells[y,x,k]
            if not e&0x80: continue
            c=100 if road[y,x]>>k&1 else costs[e&0x7f]
            nd=d+c
            if nd<dist.get((nx,ny),INF):
                dist[(nx,ny)]=nd; heapq.heappush(pq,(nd,(nx,ny)))
    return dist
