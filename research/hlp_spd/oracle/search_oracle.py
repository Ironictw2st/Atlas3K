"""DLL oracle for the SPD landmark search: runs empirecampaign.modder.x64.dll's own FUN_18059f480 (the search loop of
reprocess_spd_data) over a fake CAMPAIGN_PATHFINDER built from Atlas3K's grid dump, and records the settled hexes.

usage: search_oracle.py <grid dump prefix> <ppd> <landmark x> <landmark y> <reverse 0|1> <out.bin> [nolinks]
The grid dump comes from `hlp-spd --dump-grid <prefix>` (.edges = 6 edge bytes per hex, .types = hex types).
Output: (u16 x, u16 y, u32 cost) per settled hex, in settle order (same format as SPD_POPS)."""
import ctypes, os, struct, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from ppd import Ppd, parse_rest

B = r"C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\assembly_kit\binaries"
os.add_dll_directory(B)
dll = ctypes.WinDLL(os.path.join(B, "empirecampaign.modder.x64.dll"))
base = dll._handle
def fn(va, res, *args):
    return ctypes.CFUNCTYPE(res, *args)(base + va - 0x180000000)

prefix, ppd_path = sys.argv[1], sys.argv[2]
lx, ly, rev, out = int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), sys.argv[6]
nolinks = len(sys.argv) > 7 and sys.argv[7] == "nolinks"
p = Ppd(ppd_path); parse_rest(p)
W, H = p.W, p.H
n = W * H
edges = np.fromfile(prefix + ".edges", np.uint8).reshape(n, 6)
types = np.fromfile(prefix + ".types", np.uint8)

keep = []  # keep every buffer alive
def buf(nbytes):
    b = ctypes.create_string_buffer(nbytes); keep.append(b); return b
def addr(b): return ctypes.addressof(b)

# HEX array: 6 edge bytes + u16 (type << 12)
hexes = np.zeros((n, 8), np.uint8)
hexes[:, :6] = edges
hexes[:, 6:8] = (types.astype(np.uint16) << 12).view(np.uint8).reshape(n, 2)
hex_buf = buf(n * 8); ctypes.memmove(hex_buf, hexes.tobytes(), n * 8)

pf = buf(0x900)
def put(b, off, fmt, *v): struct.pack_into(fmt, b, off, *v)
put(pf, 0xa8, "<II", W, H)
put(pf, 0x110 + 4, "<I", n); put(pf, 0x110 + 8, "<Q", addr(hex_buf))
# cost table at +0x478: ppd costs at i, i+64, i+128, i+192; beach 1/2; road 0x3e
table = [0] * 256
for i, c in enumerate(p.costs[:64]):
    for b0 in range(0, 256, 64): table[i + b0] = c
for b0 in range(0, 256, 64):
    table[1 + b0] = 1250; table[2 + b0] = 1250; table[0x3e + b0] = 100
put(pf, 0x478, "<256I", *table)

# bridge links: hash (y*0x3f8+x) % M, buckets begin = vec[b], end = vec[b+1]; nodes: +8 next, +0x10 key, +0x1c count, +0x20 data
links = {}
if not nolinks:
    for a, b2 in p.bridges:
        for x, y in a: links[(x, y)] = [(bx, by) for bx, by in b2]
        for x, y in b2: links[(x, y)] = [(ax, ay) for ax, ay in a]
M = 4093
buckets = [[] for _ in range(M)]
for (x, y), l in links.items(): buckets[(y * 0x3f8 + x) % M].append(((x, y), l))
nodes = [kv for bk in buckets for kv in bk]
node_buf = buf(max(1, len(nodes) + 1) * 0x30)
sentinel = addr(node_buf) + len(nodes) * 0x30
vec = []
i = 0
for bk in buckets:
    vec.append(addr(node_buf) + i * 0x30); i += len(bk)
vec.append(sentinel)
for j, ((x, y), l) in enumerate(nodes):
    data = buf(4 * len(l)); struct.pack_into(f"<{len(l)}I", data, 0, *[(yy << 16) | xx for xx, yy in l])
    o = j * 0x30
    put(node_buf, o + 8, "<Q", addr(node_buf) + (j + 1) * 0x30)
    put(node_buf, o + 0x10, "<I", (y << 16) | x)
    put(node_buf, o + 0x1c, "<I", len(l)); put(node_buf, o + 0x20, "<Q", addr(data))
vec_buf = buf(8 * len(vec)); struct.pack_into(f"<{len(vec)}Q", vec_buf, 0, *vec)
put(pf, 0x90 + 4, "<I", len(vec)); put(pf, 0x90 + 8, "<Q", addr(vec_buf))

# search object (FUN_18059f430 layout): [0] pathfinder, +8 capacity, +0xc count, [2] heap, [3..] visited map, [0x11] callback,
# [0x12] max cost, +0x94 extended move table, +0x95 reverse
s = buf(0x100)
fn(0x18059f430, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(addr(s), addr(pf))
cap = 1 << 25
heap = buf(cap * 8)
put(s, 8, "<II", cap, 1); put(s, 0x10, "<Q", addr(heap))
put(heap, 0, "<II", (ly << 16) | lx, 0)
put(s, 0x90, "<I", 0xFFFFFFFF); put(s, 0x94, "<BB", 1, rev)

rec = np.zeros((n * 2, 2), np.uint32); cnt = [0]
CB = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint32))
def call(self, pos, cost):
    rec[cnt[0]] = (pos[0], cost[0]); cnt[0] += 1
    return 2
cb = CB(call)
vt = buf(8 * 6)
for k in range(6): put(vt, 8 * k, "<Q", ctypes.cast(cb, ctypes.c_void_p).value)
impl = buf(0x40); put(impl, 0, "<Q", addr(vt))
put(s, 0x88, "<Q", addr(impl))
done = fn(0x18059f480, ctypes.c_bool, ctypes.c_void_p, ctypes.c_int)(addr(s), -1)
r = rec[:cnt[0]]
o = np.zeros(len(r), dtype=[("x", "<u2"), ("y", "<u2"), ("c", "<u4")])
o["x"] = r[:, 0] & 0xFFFF; o["y"] = r[:, 0] >> 16; o["c"] = r[:, 1]
o.tofile(out)
print("done", done, "settled", cnt[0], "links", len(nodes))
