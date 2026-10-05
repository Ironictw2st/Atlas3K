"""A*-family grid as the game's CAMPAIGN_PATHFINDER sees it for a given setup: nav bit 7 edges, beach edge gating by
the search's HLCI (embark edges on when the search HLCI is the pair's enter HLCI, disembark edges when it is the
leave HLCI; both off for non-HLCI setups), port links (type 5 <-> type 5, cost 500)."""
import numpy as np
from ppd import DIRS
DIRBIT = {}
def beach_masks(p):
    """per pair: (enterHlci, leaveHlci, list of (x,y,mask) for enter edges, leave edges)"""
    return [(a, l, ent, lev) for a, l, ent, lev in p.beaches]
def nav_edges(p, e, search_hlci):
    """returns copy of edge array with bit7 reflecting beach gating for this search HLCI"""
    e2 = e.copy()
    for a, l, ent, lev in p.beaches:
        on_e = search_hlci != 0 and search_hlci == a
        on_l = search_hlci != 0 and search_hlci == l
        for (x, y, m) in ent:
            for k in range(6):
                if m >> k & 1:
                    e2[y, x, k] = (e2[y, x, k] | 0x80) if on_e else (e2[y, x, k] & 0x7F)
        for (x, y, m) in lev:
            for k in range(6):
                if m >> k & 1:
                    e2[y, x, k] = (e2[y, x, k] | 0x80) if on_l else (e2[y, x, k] & 0x7F)
    return e2
