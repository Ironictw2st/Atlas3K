"""warscape WS_SCENE_NODE_TERRAIN_EDITOR_V3::build_hf_influence_map / get_hf_influence_value (the 1281² edge fade the
procedural vegetation multiplies tree heights by), for a tile without cell mask and link points; checked against
the Frida dump of bob_vegetation's map (action_map_a8). usage: veg_hf_influence.py <label>"""
import json, sys
import numpy as np

F = np.float32
E = F(2.7182817459106445)
K = F(-4.409999370574951)
SCALE = F(1.0123047828674316)


def edge(coord, lo, hi, d):
    """FUN_1803e8e20: the fade across a cell, towards the neighbour value on the near side."""
    c = F(coord)
    f4 = F(F(F(d) * F(0.5)) + F(0.25))
    if c < F(F(d + 1) * F(0.5)):
        t = F(c - F(2.0))
        nb = lo
    else:
        t = F(F(F(d) - c) - F(2.0))
        nb = hi
    t = F(0.0) if not (F(0.0) <= t) else (F(5000.0) if F(5000.0) < t else t)
    return F(F(F(t / f4) * F(F(1.0) - nb)) + nb)


def value(px, py, d, w, h):
    if not (0 <= px < d * w and 0 <= py < d * h):
        return F(0.0)
    ix, iy = px // d, py // d
    one, zero = F(1.0), F(0.0)
    U = one if iy != 0 else zero
    D = one if iy != h - 1 else zero
    L = one if ix != 0 else zero
    R = one if ix != w - 1 else zero
    TL = one if ix != 0 and iy != 0 else zero
    TR = one if ix != w - 1 and iy != 0 else zero
    BL = one if ix != 0 and iy != h - 1 else zero
    BR = one if ix != w - 1 and iy != h - 1 else zero
    # corner / side completion (0x18033da03 ..)
    if TL == 0 and L == 1 and U == 1: TL = one
    if BL == 0 and L == 1 and D == 1: BL = one
    if TR == 0 and R == 1 and U == 1: TR = one
    if BR == 0 and R == 1 and D == 1: BR = one
    if L == 1 and U == 1 and TR == 1 and R == 0:
        R = one
        if U == 1 and TL == 1 and L == 0: L = one
    else:
        if R == 1 and U == 1 and TL == 1:
            if L == 0: L = one
        elif L == 0 and ix > 0 and (TL == 1 or BL == 1):
            L = one
    if R == 0 and ix < w - 1 and (TR == 1 or BR == 1): R = one
    if U == 0 and iy > 0 and (TL == 1 or TR == 1): U = one
    if D == 0 and iy < h - 1 and (BL == 1 or BR == 1): D = one
    if TL == 0 and L != U: TL = one
    if BL == 0 and L != D: BL = one
    if TR == 0 and R != U: TR = one
    if BR == 0 and R != D: BR = one
    lx, ly = F(px - ix * d), F(py - iy * d)
    A = edge(lx, BL, BR, d)
    B = edge(lx, TL, TR, d)
    C = edge(ly, B, A, d)
    Dv = edge(lx, L, R, d)
    Ev = edge(ly, U, D, d)
    v = F(C * F(Dv * Ev))
    r = np.power(E, F(F(v * v) * K), dtype=np.float32)
    return F(F(F(1.0) - F(r)) * SCALE)


def build(d=128, w=8, h=8):
    n = (w + 2) * d + 1
    out = np.zeros((n, n), F)
    for y in range(n):
        for x in range(n):
            out[y, x] = value(x - d, y - d, d, w, h)
    return out


if __name__ == "__main__":
    label = sys.argv[1]
    root = r"Z:/Claude/BattleMaps/research/bob_re/frida_veg/"
    for line in open(root + label + ".jsonl"):
        p = json.loads(line)
        if p["kind"] == "action_map_a8":
            ref = np.fromfile(root + label + "_bin/" + p["file"], F).reshape(p["h"], p["w"])
    mine = build()
    eq = mine.view(np.uint32) == ref.view(np.uint32)
    print("identical", eq.mean(), "max abs diff", np.abs(mine - ref).max())
    bad = np.argwhere(~eq)
    for y, x in bad[:10]:
        print(y, x, repr(mine[y, x]), repr(ref[y, x]))
