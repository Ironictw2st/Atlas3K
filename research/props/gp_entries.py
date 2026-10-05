"""Entry-level diff of two global_props.bin containers (layout: u32 count, (C-string name, u32 offset from the first
body) per entry, bodies back to back - GlobalProps.cs). Reports name sets, order, sizes and byte-identical bodies.
usage: gp_entries.py <a.bin> <b.bin> [n_show]"""
import struct, sys, collections


def parse(p):
    b = open(p, "rb").read(); o = 0
    n, = struct.unpack_from("<I", b, o); o += 4
    names, offs = [], []
    for _ in range(n):
        e = b.index(b"\0", o); names.append(b[o:e].decode("utf-8")); o = e + 1
        offs.append(struct.unpack_from("<I", b, o)[0]); o += 4
    start = o
    order = sorted(range(n), key=lambda i: offs[i])
    bodies = {}
    for k, i in enumerate(order):
        s = start + offs[i]; e = start + offs[order[k + 1]] if k + 1 < n else len(b)
        bodies[names[i]] = b[s:e]
    return names, bodies, b[:start]


if __name__ == "__main__":
    na, ba, ha = parse(sys.argv[1]); nb, bb, hb = parse(sys.argv[2])
    show = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    sa, sb = set(na), set(nb)
    print(f"entries a {len(na)} b {len(nb)}; common {len(sa & sb)}; only a {len(sa - sb)}; only b {len(sb - sa)}")
    print("  only a:", sorted(sa - sb)[:show]); print("  only b:", sorted(sb - sa)[:show])
    common = [n for n in na if n in sb]
    same = [n for n in common if ba[n] == bb[n]]
    print(f"byte-identical bodies {len(same)}/{len(common)}; table order equal {na == nb}")
    first = next((i for i, (x, y) in enumerate(zip(na, nb)) if x != y), None)
    print("  first table order difference at", first, na[first:first + 3] if first is not None else "", nb[first:first + 3] if first is not None else "")
    diff = [n for n in common if ba[n] != bb[n]]
    sz = collections.Counter("same size" if len(ba[n]) == len(bb[n]) else "size differs" for n in diff)
    print("differing bodies:", dict(sz))
    for n in diff[:show]: print(f"  {n}: {len(ba[n])} vs {len(bb[n])}")
    print("total size", sum(map(len, ba.values())), sum(map(len, bb.values())))
