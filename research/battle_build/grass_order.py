"""EMPIREUTILITY::GRASS_LIST model order: bob_vegetation's CA hash map (FUN_1800340d0 hash, FUN_1800259d0 insert,
FUN_180037f40 rehash). Iteration = bucket order, insertion order inside a bucket.
usage: imported by grass_proto.py"""
import struct

M32 = 0xffffffff


def rot(x, b):  # (x << (b ^ 31)) | (x >> b), as written in the DLL (not a true rotate)
    return ((x << (b ^ 31)) | (x >> b)) & M32


def mix(h, c):
    b = (((c ^ h) & 0xff) + 13) & 31
    return rot(h, b) ^ c


def string_hash(s):  # FUN_180091030: big-endian chunks of up to 4 bytes
    d = s.encode("latin1"); h = 0; i = 0
    while i < len(d):
        c = 0
        for k in range(min(4, len(d) - i)): c = (c << 8) | d[i + k]
        i += 4
        h = rot(h, (((c ^ h) & 0xff) + 13) & 31) ^ c
    return h


def fbits(v): return struct.unpack("<I", struct.pack("<f", float(v)))[0]


def desc_hash(path, f10, f14, f18, flag=0):
    """FUN_1800340d0 without the modulo. f10/f14/f18 = the u32 fields at +0x10/+0x14/+0x18, flag = byte +0x1c."""
    h0 = string_hash(path)
    u6 = rot(flag & 0xff, ((flag & 0xff) + 13) & 31)
    u2 = rot(f14, (((f18 ^ f14) & 0xff) + 13) & 31) ^ f18
    u6 = rot(u2, (((u2 ^ u6) & 0xff) + 13) & 31) ^ u6
    u2 = rot(h0, (((f10 ^ h0) & 0xff) + 13) & 31) ^ f10
    return rot(u2, (((u2 ^ u6) & 0xff) + 13) & 31) ^ u6


class CaHashMap:
    """Ordered like the DLL's map: nb = bucket boundaries (buckets = nb - 1), max load 1.0, starts at nb = 2."""

    def __init__(self, hasher):
        self.hasher = hasher; self.items = []; self.nb = 2

    def _bucket(self, k): return self.hasher(k) % (self.nb - 1)

    def _place(self, order, k):  # insert at the end of its bucket in an ordered list
        b = self._bucket(k)
        pos = len(order)
        for i, o in enumerate(order):
            if self._bucket(o) > b: pos = i; break
        order.insert(pos, k)

    def insert(self, k):
        if k in self.items: return
        count = len(self.items)
        if (count + 1) / (self.nb - 1) > 1.0:
            want = max(-(-count // 1), 2 * self.nb - 1)
            old = self.items; self.nb = want + 1; self.items = []
            for o in old: self._place(self.items, o)
        self._place(self.items, k)
