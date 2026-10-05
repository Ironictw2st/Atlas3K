import heapq, numpy as np, collections
from ppd import DIRS

def road_masks(p):
    road=np.zeros((p.H,p.W),np.uint8)
    for pairs,hexes in p.roads:
        for x,y,m in hexes: road[y,x]|=m
    return road

def dijkstra(p, src, road, road_cost=100, reverse=False):
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
            if not reverse: ex,ey,ek=x,y,k
            else: ex,ey,ek=nx,ny,(k+3)%6
            e=cells[ey,ex,ek]
            if not e&0x80: continue
            c=costs[e&0x7f]
            if road[ey,ex]>>ek&1: c=road_cost
            nd=d+c
            if nd<dist[ny,nx]:
                dist[ny,nx]=nd; heapq.heappush(pq,(nd,nx,ny))
    return dist
