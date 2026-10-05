"""Dump the preamble (enum tag types + values, season codes) of every bmd body in a global_props.bin.
Layout (BmdBody.Parse): FASTBIN0, u16 35, 6 bytes, u32 n types, per type (u16, str, u32 n, n str), u16, u32 n seasons,
n str, 47 bytes. str = u16 length + bytes. usage: preambles.py <global_props.bin> [n_show]  (importable: preambles())"""
import struct, sys, collections
sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
from gp_entries import parse


def pre(b):
    o = 16
    def s():
        nonlocal o
        n, = struct.unpack_from("<H", b, o); v = b[o + 2:o + 2 + n].decode("latin1"); o += 2 + n; return v
    nt, = struct.unpack_from("<I", b, o); o += 4
    types = []
    for _ in range(nt):
        o += 2; name = s(); n, = struct.unpack_from("<I", b, o); o += 4
        types.append((name, [s() for _ in range(n)]))
    o += 2; ns, = struct.unpack_from("<I", b, o); o += 4
    seasons = [s() for _ in range(ns)]
    return types, seasons, o + 47


def preambles(path):
    names, bodies, _ = parse(path)
    return {n: pre(bodies[n]) for n in names}


if __name__ == "__main__":
    P = preambles(sys.argv[1]); show = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    seas = collections.Counter(tuple(v[1]) for v in P.values())
    print("bodies", len(P)); print("season lists:", seas.most_common(8))
    tc = collections.Counter(tuple(t for t, _ in v[0]) for v in P.values())
    print("enum type lists:", tc.most_common(8))
    for n, v in list(P.items())[:show]: print(n.split("bmd_objects.")[-1], [(t, len(x)) for t, x in v[0]], v[1])
