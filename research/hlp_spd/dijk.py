import heapq, numpy as np
from ppd import DIRS

def dijkstra(p, src, reverse=False):
    W,H=p.W,p.H
    INF=0xffffffff
    dist=np.full((H,W),INF,dtype=np.int64)
    sx,sy=src
    dist[sy,sx]=0
    pq=[(0,sx,sy)]
    cells=p.cells; costs=p.costs
    while pq:
        d,x,y=heapq.heappop(pq)
        if d!=dist[y,x]: continue
        for k,(dq,dr) in enumerate(DIRS[x&1]):
            nx,ny=x+dq,y+dr
            if not (0<=nx<W and 0<=ny<H): continue
            if not reverse:
                e=cells[y,x,k]
            else:
                # edge from neighbour back to (x,y): direction (k+3)%6
                e=cells[ny,nx,(k+3)%6]
            if not e&0x80: continue
            nd=d+costs[e&0x7f]
            if nd<dist[ny,nx]:
                dist[ny,nx]=nd; heapq.heappush(pq,(nd,nx,ny))
    return dist
