"""3K map.hex grid helpers, matching CAIME (Hex.Directions_FlatTop, MapHexFile.ReadHexData16/WriteHexData16).

Grid: flat-top hexes, column offset, row 0 = SOUTH, odd columns sit half a hex north.
Directions (edge-mask bit order): 0 up, 1 up-right, 2 down-right, 3 down, 4 down-left, 5 up-left.
World centre of hex (col, row): x = col * 0.668, z = row * 0.772 + (col & 1) * 0.386.

16-byte record:
  b0  bits0-1 terrain (0 land, 1 sea, 2 beach, 3 cliff) | region index+1 low 5 bits << 3
  b1  region index+1 high 8 bits
  b2  bit3 impassable | town slot index+1 << 4
  b3  bit0 town sprawl | road edge mask << 1 | bit7 bridge
  b4  river edge mask (6 bits) | trade route mask low 2 bits << 6
  b5  trade route mask high 4 bits | ground type+1 low 4 bits << 4
  b6  ground type+1 high 3 bits | attrition+1 << 3
  b7  climate+1 << 1
  b8  restriction (3 bits) | area of interest+1 << 3
  b9  reserved for CAIME (non-zero on 855 vanilla hexes; carried as an area value)
  b10-14 reserved (0)
  b15 region edge mask << 2   (IsBorder = mask > 0)
"""
import numpy as np

HX, HZ = 0.668, 0.772
DIRS = [  # [parity][dir] -> (dcol, drow)
    [(0, 1), (1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0)],
    [(0, 1), (1, 1), (1, 0), (0, -1), (-1, 0), (-1, 1)],
]


def neighbour(col, row, d):
    dc, dr = DIRS[col & 1][d]
    return col + dc, row + dr


def neighbour_arrays(h, w):
    """For each direction: (nrow, ncol, valid) arrays of shape (h, w)."""
    rows, cols = np.mgrid[0:h, 0:w]
    par = cols & 1
    out = []
    for d in range(6):
        dc = np.where(par == 0, DIRS[0][d][0], DIRS[1][d][0])
        dr = np.where(par == 0, DIRS[0][d][1], DIRS[1][d][1])
        nc, nr = cols + dc, rows + dr
        valid = (nc >= 0) & (nc < w) & (nr >= 0) & (nr < h)
        out.append((np.clip(nr, 0, h - 1), np.clip(nc, 0, w - 1), valid))
    return out


def centre(col, row):
    return col * HX, row * HZ + (col & 1) * (HZ / 2)


def nearest_hex(x, z, w, h):
    """Nearest hex (col, row) to world points (arrays), checking the two candidate columns."""
    x = np.asarray(x, float); z = np.asarray(z, float)
    best_c = best_r = best_d = None
    c0 = np.floor(x / HX).astype(int)
    for c in (c0 - 1, c0, c0 + 1, c0 + 2):
        cc = np.clip(c, 0, w - 1)
        r = np.clip(np.rint((z - (cc & 1) * (HZ / 2)) / HZ).astype(int), 0, h - 1)
        cx, cz = centre(cc, r)
        d = (cx - x) ** 2 + ((cz - z) * 1.0) ** 2
        if best_d is None:
            best_c, best_r, best_d = cc, r, d
        else:
            m = d < best_d
            best_c = np.where(m, cc, best_c); best_r = np.where(m, r, best_r); best_d = np.where(m, d, best_d)
    return best_c, best_r


# cube coordinates. Flipping rows to grow south (row_s = -row) makes odd columns shoved "up", i.e. the standard
# "even-q" layout: r = row_s - (col + (col & 1)) / 2.
def to_cube(col, row):
    q = col
    r = -row - (col + (col & 1)) // 2
    return q, r, -q - r


def from_cube(q, r):
    col = q
    row = -(r + (col + (col & 1)) // 2)
    return col, row


def cube_round(q, r, s):
    rq, rr, rs = round(q), round(r), round(s)
    dq, dr, ds = abs(rq - q), abs(rr - r), abs(rs - s)
    if dq > dr and dq > ds:
        rq = -rr - rs
    elif dr > ds:
        rr = -rq - rs
    return rq, rr


def hex_line(a, b):
    """Hexes (col, row) from a to b inclusive, each consecutive pair adjacent."""
    aq, ar, as_ = to_cube(*a); bq, br, bs = to_cube(*b)
    n = max(abs(aq - bq), abs(ar - br), abs(as_ - bs))
    if n == 0:
        return [a]
    out = []
    for i in range(n + 1):
        t = i / n
        q = aq + (bq - aq) * t + 1e-6; r = ar + (br - ar) * t + 1e-6; s = as_ + (bs - as_) * t - 2e-6
        out.append(from_cube(*cube_round(q, r, s)))
    return out


def direction_between(a, b):
    """Direction index from hex a to adjacent hex b, or -1."""
    for d in range(6):
        if neighbour(a[0], a[1], d) == (b[0], b[1]):
            return d
    return -1
