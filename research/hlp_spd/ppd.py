"""Minimal pathfinding.ppd reader (layout from CAIME's PpdFile)."""
import struct
import numpy as np

DIRS = [[(0, 1), (1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0)],
        [(0, 1), (1, 1), (1, 0), (0, -1), (-1, 0), (-1, 1)]]  # (dq, dr) by q parity


class Ppd:
    def __init__(self, path):
        b = open(path, "rb").read()
        self.raw = b
        p = 0
        self.magic, self.version, n = struct.unpack_from("<QIi", b, p); p += 16
        self.regions = []
        for _ in range(n):
            l, = struct.unpack_from("<i", b, p); p += 4
            self.regions.append(b[p:p + l].decode("latin1")); p += l
        self.W, self.H = struct.unpack_from("<HH", b, p); p += 4
        self.cells = np.frombuffer(b, np.uint8, self.W * self.H * 8, p).reshape(self.H, self.W, 8); p += self.W * self.H * 8
        nc, = struct.unpack_from("<i", b, p); p += 4
        self.costs = list(struct.unpack_from(f"<{nc}H", b, p)); p += 2 * nc
        ntg, = struct.unpack_from("<H", b, p); p += 2
        self.tile_groups = [struct.unpack_from("<HH", b, p + 4 * i) for i in range(ntg)]; p += 4 * ntg
        self.after_tg = p

    def tile_group(self):
        c = self.cells
        return ((c[:, :, 7].astype(np.int32) & 0xF) << 8) | c[:, :, 6]

    def hex_type(self):
        return self.cells[:, :, 7] >> 4


def parse_rest(p):
    """Parse the sections after the tile groups (CAIME layout). Fills p.region_edges, beaches, hlci, bridges,
    heuristic, border_hexes, cumulative, roads, restrictions."""
    b = p.raw; o = p.after_tg
    u16 = lambda: struct.unpack_from("<H", b, o)[0]
    p.region_edges = []
    for _ in range(len(p.regions)):
        n, = struct.unpack_from("<H", b, o); o += 2
        p.region_edges.append([struct.unpack_from("<HHB", b, o + 5 * i) for i in range(n)]); o += 5 * n
    n, = struct.unpack_from("<H", b, o); o += 2
    p.beaches = []
    for _ in range(n):
        a, l = struct.unpack_from("<HH", b, o); o += 4
        ne, = struct.unpack_from("<H", b, o); o += 2
        ent = [struct.unpack_from("<HHB", b, o + 5 * i) for i in range(ne)]; o += 5 * ne
        nl, = struct.unpack_from("<H", b, o); o += 2
        lev = [struct.unpack_from("<HHB", b, o + 5 * i) for i in range(nl)]; o += 5 * nl
        p.beaches.append((a, l, ent, lev))
    n, = struct.unpack_from("<H", b, o); o += 2
    p.hlci = [struct.unpack_from("<HH", b, o + 4 * i) for i in range(n)]; o += 4 * n
    n, = struct.unpack_from("<H", b, o); o += 2
    p.bridges = []
    for _ in range(n):
        n0, = struct.unpack_from("<H", b, o); o += 2
        a = [struct.unpack_from("<HH", b, o + 4 * i) for i in range(n0)]; o += 4 * n0
        n1, = struct.unpack_from("<H", b, o); o += 2
        c = [struct.unpack_from("<HH", b, o + 4 * i) for i in range(n1)]; o += 4 * n1
        p.bridges.append((a, c))
    ntg = len(p.tile_groups)
    p.heuristic = np.frombuffer(b, np.uint32, ntg * ntg, o).reshape(ntg, ntg); o += 4 * ntg * ntg
    n, = struct.unpack_from("<i", b, o); o += 4
    p.border_hexes = [struct.unpack_from("<HH", b, o + 4 * i) for i in range(n)]; o += 4 * n
    p.cumulative = np.frombuffer(b, np.int32, ntg, o); o += 4 * ntg
    n, = struct.unpack_from("<H", b, o); o += 2
    p.roads = []
    for _ in range(n):
        k, = struct.unpack_from("<i", b, o); o += 4
        pairs = [struct.unpack_from("<HH", b, o + 4 * i) for i in range(k)]; o += 4 * k
        m, = struct.unpack_from("<H", b, o); o += 2
        hexes = [struct.unpack_from("<HHB", b, o + 5 * i) for i in range(m)]; o += 5 * m
        p.roads.append((pairs, hexes))
    p.restrictions = None
    if len(b) - o > 4:
        nr = b[o]; o += 1
        p.restrictions = []
        for _ in range(nr):
            k, = struct.unpack_from("<i", b, o); o += 4
            p.restrictions.append([struct.unpack_from("<HHB", b, o + 5 * i) for i in range(k)]); o += 5 * k
    p.tail = b[o:]
    return p
