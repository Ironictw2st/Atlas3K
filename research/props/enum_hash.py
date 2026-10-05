"""Find the u32 at body offset 12 (hash of the enum tag types, 0 without types). usage: enum_hash.py <global_props.bin>"""
import sys, collections, struct, zlib, hashlib
sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
from gp_entries import parse
from preambles import pre
nb, bb, _ = parse(sys.argv[1])
samples = {}
for n in nb:
    b = bb[n]; t, s, e = pre(b); h = struct.unpack_from("<I", b, 12)[0]
    if t: samples[tuple((x, tuple(v)) for x, v in t)] = (h, b)
def fnv1a(d, h=0x811c9dc5):
    for c in d: h = ((h ^ c) * 0x01000193) & 0xffffffff
    return h
def ser(t, mode):
    if mode == "names": return "".join(x for x, _ in t).encode()
    if mode == "all": return "".join(x + "".join(v) for x, v in t).encode()
    if mode == "names0": return b"".join(x.encode() + b"\0" for x, _ in t)
    if mode == "all0": return b"".join(x.encode() + b"\0" + b"".join(y.encode() + b"\0" for y in v) for x, v in t)
for t, (h, b) in list(samples.items())[:3]:
    print(hex(h), t[0][0], len(t))
    # the preamble bytes themselves
    _, _, e = pre(b)
    body = b[16:e - 47]
    cands = {"crc_pre": zlib.crc32(body), "crc_pre_all": zlib.crc32(b[16:e]), "fnv_pre": fnv1a(body)}
    for m in ("names", "all", "names0", "all0"):
        d = ser(t, m); cands["crc_" + m] = zlib.crc32(d); cands["fnv_" + m] = fnv1a(d)
        cands["md5_" + m] = struct.unpack("<I", hashlib.md5(d).digest()[:4])[0]
    print([k for k, v in cands.items() if v == h])

# empireutility BMD_META_TAG_COLLECTION::add_available_meta_data / FUN_180f35730
def mix(h, v):
    b = ((v ^ h) + 13) & 0x1f
    return (((h << (b ^ 31)) | (h >> b)) & 0xffffffff) ^ v
def shash(s):
    d = s.encode(); h = 0
    for i in range(0, len(d), 4):
        v = 0
        for c in d[i:i + 4]: v = v * 256 + c
        h = mix(h, v)
    return h
def coll(t, with_types=False):
    h = 0
    for x, vals in t:
        if with_types: h = mix(h, shash(x))
        for v in vals: h = mix(h, shash(v))
    return h
ok = sum(coll(t) == h for t, (h, b) in samples.items()); print("values only", ok, "/", len(samples))
ok = sum(coll(t, True) == h for t, (h, b) in samples.items()); print("types+values", ok, "/", len(samples))
