import pickle, numpy as np
from ppd import DIRS
def make(p, base, slots, mode, types_ok=(0,1)):
    e, types, costs, links = base
    e2 = e.copy()
    S = np.zeros((p.H, p.W), bool)
    for (x, y) in slots: S[y, x] = True
    ys, xs = np.nonzero(S)
    for y, x in zip(ys, xs):
        for k, (dq, dr) in enumerate(DIRS[x & 1]):
            nx, ny = x + dq, y + dr
            if not (0 <= nx < p.W and 0 <= ny < p.H): continue
            if not (types[ny, nx] in types_ok or S[ny, nx]): continue
            if mode in ("both", "out"): e2[y, x, k] &= 0xC0
            if mode in ("both", "in"): e2[ny, nx, (k + 3) % 6] &= 0xC0
            if mode == "slotslot" and S[ny, nx]: e2[y, x, k] &= 0xC0
    return (e2, types, costs, links)
