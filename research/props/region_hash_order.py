"""BOB's per-cell region order: a CA hash map keyed by region name (murmur_hash), list kept sorted by bucket
(h % (n - 1)), insertion order inside a bucket. Tests murmur variants / table sizes against BOB's entry order.
usage: region_hash_order.py <bob global_props.bin> <trace.csv>"""
import csv, re, sys, collections, struct
sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
from gp_entries import parse
M32 = 0xffffffff
def murmur2(d, seed=0):
    m, r = 0x5bd1e995, 24; h = (seed ^ len(d)) & M32; i = 0
    while len(d) - i >= 4:
        k = struct.unpack_from("<I", d, i)[0]; k = (k * m) & M32; k ^= k >> r; k = (k * m) & M32
        h = (h * m) & M32; h ^= k; i += 4
    rem = len(d) - i
    if rem >= 3: h ^= d[i + 2] << 16
    if rem >= 2: h ^= d[i + 1] << 8
    if rem >= 1: h ^= d[i]; h = (h * m) & M32
    h ^= h >> 13; h = (h * m) & M32; h ^= h >> 15
    return h
def rotl(x, r): return ((x << r) | (x >> (32 - r))) & M32
def murmur3(d, seed=0):
    c1, c2 = 0xcc9e2d51, 0x1b873593; h = seed; n = len(d) // 4
    for i in range(n):
        k = struct.unpack_from("<I", d, 4 * i)[0]; k = (k * c1) & M32; k = rotl(k, 15); k = (k * c2) & M32
        h ^= k; h = rotl(h, 13); h = (h * 5 + 0xe6546b64) & M32
    t = d[4 * n:]; k = 0
    if len(t) >= 3: k ^= t[2] << 16
    if len(t) >= 2: k ^= t[1] << 8
    if len(t) >= 1:
        k ^= t[0]; k = (k * c1) & M32; k = rotl(k, 15); k = (k * c2) & M32; h ^= k
    h ^= len(d); h ^= h >> 16; h = (h * 0x85ebca6b) & M32; h ^= h >> 13; h = (h * 0xc2b2ae35) & M32; h ^= h >> 16
    return h
first = {}
for r in csv.reader(open(sys.argv[2], encoding="utf-8")):
    m = re.search(r"bmd_objects\.(.+)\.(\d+)\.(\d+)\.bin$", r[0]); key = (m.group(1), int(m.group(2)))
    first[key] = min(first.get(key, 1 << 64), int(r[2], 16))
nb, _, _ = parse(sys.argv[1])
bycell = collections.defaultdict(list)
for n in nb:
    m = re.search(r"bmd_objects\.(.+)\.(\d+)\.bin$", n)
    if m and not re.search(r"\.\d+\.\d+\.bin$", n): bycell[int(m.group(2))].append(m.group(1))
multi = {c: rs for c, rs in bycell.items() if len(rs) > 1}
for name, hf in [("murmur2", murmur2), ("murmur3", murmur3)]:
    for seed in (0x4a545eed,):
        ok = 0; sizes = collections.Counter()
        for c, rs in multi.items():
            for nb_ in [2 ** k + 1 for k in range(1, 12)]:
                order = sorted(rs, key=lambda r: (hf(r.encode(), seed) % (nb_ - 1), first.get((r, c), 0)))
                if order == rs: ok += 1; sizes[(len(rs), nb_)] += 1; break
        print(name, seed, "cells matched", ok, "of", len(multi), sorted(sizes.items())[:20])

# one global map: region -> per-cell bodies; insertion order = first object (lowest id) of the region overall
gfirst = {}
for (r, c), v in first.items(): gfirst[r] = min(gfirst.get(r, 1 << 64), v)
regions = sorted({r for rs in bycell.values() for r in rs})
print("regions", len(regions))
for nb_ in [2 ** k + 1 for k in range(1, 13)] + [len(regions) + 1]:
    rank = {r: i for i, r in enumerate(sorted(regions, key=lambda r: (murmur3(r.encode(), 0x4a545eed) % (nb_ - 1), gfirst.get(r, 0))))}
    ok = sum(sorted(rs, key=rank.get) == rs for rs in multi.values())
    print(nb_, ok, "of", len(multi))
