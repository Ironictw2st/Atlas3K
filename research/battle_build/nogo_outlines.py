"""Prototype of BOB's bmd_nogo_data terrain outlines (empireutility no_go_outlines_from_heights), float32 throughout.
Pipeline (decompiles in Z:/Claude/BattleMaps/research/bob_re/bmd_nogo):
  1. HEIGHTFIELD_OUTLINE_DATA_PROVIDER: a cell is no-go when the field normal's y < sin((90 - 30) deg), the 30 being
     maximum_passable_slope_angle_degrees (read at runtime with Frida); min height -inf.
  2. BLUR_OUTLINE_DATA_PROVIDER::blur(3 taps, 0.1): separable triangle blur over the extents [0, w-1) x [0, h-1)
     (BOOL provider extents are inclusive w-1/h-1, loops are exclusive), then thresholded to 1.0/0.0; is_point_nogo
     = value >= 0.5.
  3. OUTLINE_CALCULATOR::compute (marching boundary over cell corners, start patterns 1 / 9, table at 0x18171c250),
     outlines whose bbox is <= 6 cells on both axes dropped.
  4. points -> world: (float)p * scale + offset (scale 2 = cell size, offset 0).
  5. three simplification passes (FUN_180efc6c0): (3x, 0.99, lookahead 10, expand+contract),
     (1x, 3.0, 4, expand only), (1x, 1.0, 4, expand+contract).
usage: nogo_outlines.py <heights.npy | frida .bin> [bob bmd_nogo_data.bin to compare]"""
import math, struct, sys
import numpy as np

F = np.float32


def nogo_cells(H, slope_deg=30.0, cell=2.0):
    h, w = H.shape
    s = F(cell)
    thr = F(math.sin(F((F(90) - F(slope_deg)) * F(0.01745329238474369))))
    out = np.zeros((h, w), bool)
    a2 = F(s + s); b2 = F(s + s)
    for y in range(h):
        for x in range(w):
            c = H[y, x]
            l = H[y, x - 1] if x > 0 else c
            r = H[y, x + 1] if x < w - 1 else c
            u = H[y - 1, x] if y > 0 else c
            d = H[y + 1, x] if y < h - 1 else c
            f7 = F(s + s); f4 = F(s + s)
            f6 = F(F(u - d) * f4)
            f5 = F(F(l - r) * f7)
            f7 = F(f7 * f4)
            ln = F(math.sqrt(F(F(F(f7 * f7) + F(f5 * f5)) + F(f6 * f6))))
            ny = F(f7 * F(F(1) / ln))
            out[y, x] = ny < thr
    return out


def nogo_cells_np(H, slope_deg=30.0, cell=2.0):
    """Vectorised nogo_cells (same float32 operations)."""
    s = F(cell)
    thr = F(math.sin(F((F(90) - F(slope_deg)) * F(0.01745329238474369))))
    P = np.pad(H, 1, mode="edge")
    l = P[1:-1, :-2]; r = P[1:-1, 2:]; u = P[:-2, 1:-1]; d = P[2:, 1:-1]
    f = F(s + s)
    f6 = ((u - d).astype(F) * f).astype(F)
    f5 = ((l - r).astype(F) * f).astype(F)
    f7 = F(f * f)
    ln = np.sqrt(((F(f7 * f7) + (f5 * f5).astype(F)).astype(F) + (f6 * f6).astype(F)).astype(F)).astype(F)
    ny = (f7 * (F(1) / ln).astype(F)).astype(F)
    return ny < thr


def blur(bool_field, taps=3, threshold=0.1):
    h, w = bool_field.shape
    buf1 = bool_field.astype(F)            # data
    buf2 = np.zeros((h, w), F)             # scratch
    x1, y1 = w - 1, h - 1                  # extents (inclusive maxima), loops exclusive
    f = F(F(1) / F(taps))
    wts = [F(F(F(taps - abs(i)) * f) * f) for i in range(-taps, taps + 1)]
    for y in range(0, y1):
        row = buf1[y]
        for x in range(0, x1):
            acc = F(0)
            for i in range(-taps, taps + 1):
                xi = x + i
                xi = 0 if xi < 0 else (x1 - 1 if xi >= x1 else xi)
                acc = F(acc + F(row[xi] * wts[i + taps]))
            buf2[y, x] = acc
    for y in range(0, y1):
        for x in range(0, x1):
            acc = F(0)
            for i in range(-taps, taps + 1):
                yi = y + i
                yi = 0 if yi < 0 else (y1 - 1 if yi >= y1 else yi)
                acc = F(acc + F(buf2[yi, x] * wts[i + taps]))
            buf1[y, x] = F(1) if acc > F(threshold) else F(0)
    return buf1


def blur_np(bool_field, taps=3, threshold=0.1):
    """Vectorised blur, same per-element float32 sums in tap order."""
    h, w = bool_field.shape
    buf1 = bool_field.astype(F)
    buf2 = np.zeros((h, w), F)
    x1, y1 = w - 1, h - 1
    f = F(F(1) / F(taps))
    wts = [F(F(F(taps - abs(i)) * f) * f) for i in range(-taps, taps + 1)]
    xs = np.arange(x1)
    acc = np.zeros((y1, x1), F)
    for i in range(-taps, taps + 1):
        xi = np.clip(xs + i, 0, x1 - 1)
        acc = (acc + (buf1[:y1][:, xi] * wts[i + taps]).astype(F)).astype(F)
    buf2[:y1, :x1] = acc
    ys = np.arange(y1)
    acc = np.zeros((y1, x1), F)
    for i in range(-taps, taps + 1):
        yi = np.clip(ys + i, 0, y1 - 1)
        acc = (acc + (buf2[yi][:, :x1] * wts[i + taps]).astype(F)).astype(F)
    buf1[:y1, :x1] = np.where(acc > F(threshold), F(1), F(0))
    return buf1


# move table (empireutility 0x18171c250): pattern -> (move x, move y, 3 point offsets, mark bits)
TABLE = {
    0: (1, 0, (0, 0), (0, 0), (0, 0), 0b0),
    1: (1, 0, (-1, 0), (-1, -1), (0, -1), 0b1),
    2: (0, 1, (-2, -1), (-1, -1), (-1, 0), 0b10),
    3: (1, 0, (-2, -1), (-1, -1), (0, -1), 0b11),
    4: (0, -1, (0, -1), (-1, -1), (-1, -2), 0b100),
    5: (0, -1, (-1, 0), (-1, -1), (-1, -2), 0b101),
    6: (0, 1, (-2, -1), (-1, -1), (-1, 0), 0b10),
    7: (0, -1, (-2, -1), (-1, -1), (-1, -2), 0b111),
    8: (-1, 0, (-1, -2), (-1, -1), (-2, -1), 0b1000),
    9: (-1, 0, (-1, -2), (-1, -1), (-2, -1), 0b1000),
    10: (0, 1, (-1, -2), (-1, -1), (-1, 0), 0b1010),
    11: (1, 0, (-1, -2), (-1, -1), (0, -1), 0b1011),
    12: (-1, 0, (0, -1), (-1, -1), (-2, -1), 0b1100),
    13: (-1, 0, (-1, 0), (-1, -1), (-2, -1), 0b1101),
    14: (0, 1, (0, -1), (-1, -1), (-1, 0), 0b1110),
    16: (0, -1, (0, -1), (-1, -1), (-1, -2), 0b100),
    17: (1, 0, (-1, 0), (-1, -1), (0, -1), 0b1),
}


class Calc:
    def __init__(self, data):
        self.h, self.w = data.shape
        self.d = data.astype(np.int64)     # 0 / 1, labels >= 2

    def get(self, x, y): return int(self.d[y, x])

    def pattern(self, x, y):
        b = 0
        w, h = self.w, self.h
        if y < h:
            if x < w and self.get(x, y): b = 1
            if x != 0 and x - 1 < w and self.get(x - 1, y): b |= 2
        if y != 0 and y - 1 < h:
            if x != 0 and x - 1 < w and self.get(x - 1, y - 1): b |= 8
            if x < w and self.get(x, y - 1): b |= 4
        return b

    def scan(self):
        while self.sy < self.h:
            x = self.sx
            while x < self.w:
                if self.get(x, self.sy) == 1:
                    p = self.pattern(x, self.sy)
                    if p == 1: self.sx = x; return True
                    if p == 9 and self.get(x - 1, self.sy - 1) > 1: self.sx = x; return True
                x += 1
                self.sx = x
            self.sy += 1
            self.sx = 0
        return False

    @staticmethod
    def add_point(edges, p, closed):
        if closed[0]: return
        if edges and edges[0] == p: closed[0] = True
        if len(edges) < 3:
            edges.append(p); return
        a, b = edges[-2], edges[-1]
        if a[0] == b[0] == p[0]:           # vertical run: extend
            if p[1] != b[1]: edges[-1] = (b[0], p[1])
            return
        if a[1] == b[1] == p[1]:           # horizontal run: extend
            if p[0] != b[0]: edges[-1] = (p[0], b[1])
            return
        edges.append(p)

    def inside_existing(self, x, y, outlines):
        """FUN_180ef9a20 / OUTLINE_DATA_CONTAINER::is_point_inside_outline over the outlines found so far."""
        for e, (x0, y0, x1, y1) in zip(outlines, self.boxes):
            if not (x0 <= x <= x1 and y0 <= y <= y1): continue
            inside = False; on_edge = False
            n = len(e)
            for i in range(n - 1):
                a = e[i]; b = e[0] if i == n - 2 else e[i + 1]
                if a[0] == b[0]:
                    lo, hi = min(a[1], b[1]), max(a[1], b[1])
                    if a[0] < x:
                        if lo <= y < hi: inside = not inside
                    elif x == a[0] and lo <= y <= hi:
                        on_edge = True; break
                elif y == a[1] and min(a[0], b[0]) <= x <= max(a[0], b[0]):
                    on_edge = True; break
            if inside and not on_edge: return True
        return False

    def compute(self, min_size=6):
        self.boxes = []
        self.sx = self.sy = 0
        label = 2
        max_count = (self.w * self.h) >> 2
        outlines = []
        found = self.scan()
        while found:
            if self.inside_existing(self.sx, self.sy, outlines):
                self.sx += 1
                found = self.scan()
                continue
            x, y = self.sx, self.sy
            px, py, prev_pat = x, y, 0
            mn = [x, y]; mx = [x, y]
            edges = []; closed = [False]; count = 0
            while True:
                pat = self.pattern(x, y)
                e = pat
                if pat == 9:
                    if prev_pat == 0 or y < py: e = 17     # (param_7 < param_5): y < previous y
                elif pat == 6:
                    if x < px: e = 16
                mvx, mvy, p1, p2, p3, mark = TABLE[e]
                if not closed[0]:
                    q1 = (x + 1 + p1[0], y + 1 + p1[1]); q2 = (x + 1 + p2[0], y + 1 + p2[1]); q3 = (x + 1 + p3[0], y + 1 + p3[1])
                    if len(edges) < 3:
                        self.add_point(edges, q1, closed); self.add_point(edges, q2, closed); self.add_point(edges, q3, closed)
                    else:
                        if q1 != edges[-2] and q2 != edges[-1]:
                            self.add_point(edges, q1, closed); self.add_point(edges, q2, closed)
                        self.add_point(edges, q3, closed)
                if mark & 1: self.d[y, x] = label
                if mark & 2: self.d[y, x - 1] = label
                if mark & 4: self.d[y - 1, x] = label
                if mark & 8: self.d[y - 1, x - 1] = label
                px, py, prev_pat = x, y, pat
                x += mvx; y += mvy
                mn = [min(mn[0], x), min(mn[1], y)]; mx = [max(mx[0], x), max(mx[1], y)]
                count += 1
                if closed[0] or count >= max_count: break
            if count != max_count:
                if not (min_size and mx[0] - mn[0] <= min_size and mx[1] - mn[1] <= min_size):
                    outlines.append(edges)
                    self.boxes.append((mn[0], mn[1], mx[0], mx[1]))
            label += 1
            self.sx += 1
            found = self.scan()
        return outlines


def seg_hits(S, a, b):
    """FUN_180efb820's test of segment S (x0,y0,x1,y1) against edge a->b: proper crossing (t != 0, 1)."""
    x3, y4 = a; x1, y2 = b
    f16 = F(S[2] - S[0]); f17 = F(S[3] - S[1])
    d = F(F(F(x1 - x3) * f17) - F(F(y2 - y4) * f16))
    if not abs(d) > 0: return False
    f18 = F(x3 - S[0]); f19 = F(y4 - S[1]); inv = F(F(1) / d)
    t = F(F(F(f19 * f16) - F(f18 * f17)) * inv)
    if not (0 <= t <= 1): return False
    s = F(F(F(F(x1 - x3) * f19) - F(F(y2 - y4) * f18)) * inv)
    return 0 <= s <= 1 and t != 0 and t != 1


def seg_hits_new(S, a, b):
    """FUN_180efa230's test against the new list's edge a->b (its own operand order)."""
    x22, y23, x24, y25 = S
    x4, y5 = a; x2, y3 = b
    d = F(F(F(y25 - y23) * F(x2 - x4)) - F(F(x24 - x22) * F(y3 - y5)))
    if not abs(d) > 0: return False
    inv = F(F(1) / d)
    t = F(F(F(F(x24 - x22) * F(y5 - y23)) - F(F(y25 - y23) * F(x4 - x22))) * inv)
    if not (0 <= t <= 1): return False
    s = F(F(F(F(x2 - x4) * F(y5 - y23)) - F(F(y3 - y5) * F(x4 - x22))) * inv)
    return 0 <= s <= 1 and t != 0 and t != 1


def shortcut_ok(outlines, k, j, new):
    S = (new[-1][0], new[-1][1], outlines[k][j][0], outlines[k][j][1])
    for o, pts in enumerate(outlines):
        if o == k:
            for a, b in zip(new, new[1:]):
                if seg_hits_new(S, a, b): return False
        n = len(pts)
        if n > 1 and j < n:
            for e in range(j, n):
                a = pts[e]; b = pts[0] if e == n - 1 else pts[e + 1]
                if seg_hits(S, a, b): return False
    return True


def simplify(outlines, done, iterations, err, lookahead, expand, contract):
    err = F(err)
    for _ in range(iterations):
        for k in range(len(outlines)):
            if done[k]: continue
            pts = outlines[k]; n = len(pts)
            new = []
            i = 0
            while i < n:
                p = pts[i]; new.append(p)
                best, best_err = -1, F(err + err)
                j = i + 2
                count = 0
                while j < n - 1:
                    if count >= lookahead: break
                    q = pts[j]
                    dx = F(q[0] - p[0]); dy = F(q[1] - p[1])
                    seglen = F(math.sqrt(F(F(dy * dy) + F(dx * dx))))
                    maxd = F(0); fail = False
                    for m in range(i + 1, j):
                        r = pts[m]
                        rx = F(r[0] - p[0]); ry = F(r[1] - p[1])
                        if seglen <= 0:
                            t = F(0)
                        else:
                            inv = F(F(1) / seglen)
                            t = F(F(F(F(ry * inv) * dy) * inv) + F(F(F(rx * inv) * dx) * inv))
                            if not (t >= 0): t = F(0)
                        if t >= 1: t = F(1)
                        ex = F(F(F(dx * t) + p[0]) - r[0]); ey = F(F(F(dy * t) + p[1]) - r[1])
                        dist = F(math.sqrt(F(F(ey * ey) + F(ex * ex))))
                        if maxd <= dist: maxd = dist
                        if err <= dist: break
                        side = F(F(dy * rx) - F(dx * ry)) > 0
                        if (not contract and side) or (not expand and not side): fail = True; break
                    if not (fail or err <= maxd or best_err < maxd):
                        best, best_err = j, maxd
                    count += 1
                    j += 1
                if best != -1 and shortcut_ok(outlines, k, best, new):
                    i = best
                else:
                    i += 1
            if len(new) > 2:
                if len(new) == n: done[k] = True
                outlines[k] = new
    return outlines


def nogo_outlines(H, slope=30.0, cell=2.0, offset=(0.0, 0.0)):
    ng = nogo_cells_np(H, slope, cell)
    b = blur_np(ng)
    data = (b >= F(0.5)).astype(np.int64)
    raw = Calc(data).compute(6)
    sc = F(cell)
    outs = [[(F(F(F(px) * sc) + F(offset[0])), F(F(F(py) * sc) + F(offset[1]))) for (px, py) in e[:-1]] for e in raw]
    done = [False] * len(outs)
    simplify(outs, done, 3, 0.99, 10, True, True)
    done = [False] * len(outs)
    simplify(outs, done, 1, 3.0, 4, True, False)
    done = [False] * len(outs)
    simplify(outs, done, 1, 1.0, 4, True, True)
    return raw, outs


if __name__ == "__main__":
    src = sys.argv[1]
    H = np.load(src) if src.endswith(".npy") else np.fromfile(src, F).reshape(1025, 1025)
    raw, outs = nogo_outlines(H)
    print(f"{len(raw)} raw outlines, sizes {[len(e) for e in raw]}; simplified {[len(o) for o in outs]}")
    if len(sys.argv) > 2:
        sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
        import bmd_codec as bc
        t, _ = bc.decode_file(open(sys.argv[2], "rb").read())
        to = [c for c in t.children if c.tag == "TERRAIN_OUTLINES"][0]
        bob = [[tuple(p.raw) for p in eo.children[0].children] for eo in to.children]
        print("bob sizes", [len(b) for b in bob])
        for k, (a, b) in enumerate(zip(outs, bob)):
            same = [tuple(map(float, p)) for p in a] == [tuple(map(float, p)) for p in b]
            print(k, "IDENTICAL" if same else "differs", a[:5], b[:5])
