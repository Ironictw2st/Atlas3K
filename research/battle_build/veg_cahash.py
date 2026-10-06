"""CA::murmur_hash and CA_STD hash-map iteration order (port of Atlas3K.Formats.CaHash)."""


def murmur(data, seed=0x4A545EED):
    if isinstance(data, str):
        data = data.encode("latin1")
    c1, c2 = 0xCC9E2D51, 0x1B873593
    h = seed
    n = len(data) // 4
    rotl = lambda x, r: ((x << r) | (x >> (32 - r))) & 0xFFFFFFFF
    for i in range(n):
        k = int.from_bytes(data[4 * i:4 * i + 4], "little")
        k = (k * c1) & 0xFFFFFFFF
        k = (rotl(k, 15) * c2) & 0xFFFFFFFF
        h ^= k
        h = (rotl(h, 13) * 5 + 0xE6546B64) & 0xFFFFFFFF
    tail = data[4 * n:]
    if tail:
        k = 0
        if len(tail) == 3:
            k ^= tail[2] << 16
        if len(tail) >= 2:
            k ^= tail[1] << 8
        k ^= tail[0]
        h ^= (rotl((k * c1) & 0xFFFFFFFF, 15) * c2) & 0xFFFFFFFF
    h ^= len(data)
    h ^= h >> 16
    h = (h * 0x85EBCA6B) & 0xFFFFFFFF
    h ^= h >> 13
    h = (h * 0xC2B2AE35) & 0xFFFFFFFF
    h ^= h >> 16
    return h


def hash_map_order(keys, h=murmur):
    nb = 1
    buckets = [[]]
    seen = set()
    for key in keys:
        if key in seen:
            continue
        seen.add(key)
        if len(seen) / nb > 1.0:
            old = [k for b in buckets for k in b if k != key]
            nb = nb * 2 + 1
            buckets = [[] for _ in range(nb)]
            for k in old:
                buckets[h(k) % nb].append(k)
        buckets[h(key) % nb].append(key)
    return [k for b in buckets for k in b]
