"""Generic CAAB ESF tree reader (RPFM layout). esf_tree.py <file> [maxdepth] -> prints record tree with child counts."""
import struct, sys
from esf_flat import cauleb

def read(path):
    b = open(path, "rb").read()
    magic, unk, ts, noff = struct.unpack_from("<IIII", b, 0)
    p = noff
    n, = struct.unpack_from("<H", b, p); p += 2
    names = []
    for _ in range(n):
        l, = struct.unpack_from("<H", b, p); p += 2
        names.append(b[p:p+l].decode("latin1")); p += l
    nu16, = struct.unpack_from("<I", b, p); p += 4
    s16 = {}
    for _ in range(nu16):
        l, = struct.unpack_from("<H", b, p); p += 2
        s = b[p:p+2*l].decode("utf-16le"); p += 2*l
        i, = struct.unpack_from("<I", b, p); p += 4; s16[i] = s
    nu8, = struct.unpack_from("<I", b, p); p += 4
    s8 = {}
    for _ in range(nu8):
        l, = struct.unpack_from("<H", b, p); p += 2
        s = b[p:p+l].decode("latin1"); p += l
        i, = struct.unpack_from("<I", b, p); p += 4; s8[i] = s
    return b, names, s8, s16

SZ = {0x01:1,0x02:1,0x03:2,0x04:4,0x05:8,0x06:1,0x07:2,0x08:4,0x09:8,0x0a:4,0x0b:8,0x0c:8,0x0d:12,0x0e:4,0x0f:4,0x10:2,
      0x12:0,0x13:0,0x14:0,0x15:0,0x16:1,0x17:2,0x18:3,0x19:0,0x1a:1,0x1b:2,0x1c:3,0x1d:0,0x21:4,0x23:1,0x24:2,0x25:4}

def node(b, p, names, root=False):
    t = b[p]
    if t & 0x80:
        if (t & 0x20) or root:
            ni, ver = struct.unpack_from("<HB", b, p+1); q = p + 4
        else:
            ver = (t & 0x1E) >> 1; ni = ((t & 1) << 8) | b[p+1]; q = p + 2
        size, q = cauleb(b, q)
        end = q + size
        groups = []
        if t & 0x40:
            cnt, q = cauleb(b, q)
            end = q + size  # nested-block size counts from after the group count
            for _ in range(cnt):
                gs, q = cauleb(b, q); ge = q + gs; ch = []
                while q < ge:
                    c, q = node(b, q, names); ch.append(c)
                groups.append(ch)
        else:
            ch = []
            while q < end:
                c, q = node(b, q, names); ch.append(c)
            groups.append(ch)
        return ("REC", names[ni], ver, groups, t & 0x40 != 0), end
    if t >= 0x40:
        n, q = cauleb(b, p+1)
        return ("ARR", t, b[q:q+n]), q + n
    q = p + 1 + SZ[t]
    raw = b[p+1:q]
    if t == 0x18 or t == 0x1c: v = int.from_bytes(raw, "big")
    elif t in (0x0c, 0x0d): v = struct.unpack("<" + "f"*(len(raw)//4), raw)
    elif t == 0x0a: v = struct.unpack("<f", raw)[0]
    elif t in (0x12, 0x13): v = t == 0x12
    elif t == 0x14 or t == 0x19 or t == 0x1d: v = 0
    elif t == 0x15: v = 1
    else: v = int.from_bytes(raw, "little", signed=t in (2,3,4,5,0x1a,0x1b))
    return ("VAL", t, v), q

def show(n, depth, maxd, ind=""):
    if n[0] == "REC":
        print(f"{ind}{n[1]} v{n[2]} groups={len(n[3])} children={[len(g) for g in n[3][:5]]}")
        if depth < maxd:
            for g in n[3][:3]:
                for c in g:
                    if c[0] == "REC": show(c, depth+1, maxd, ind+"  ")
                    elif depth+1 <= maxd: print(ind+"  ", c[0], hex(c[1]), c[2] if c[0]=="VAL" else len(c[2]))

if __name__ == "__main__":
    b, names, s8, s16 = read(sys.argv[1])
    root, _ = node(b, 16, names, True)
    show(root, 0, int(sys.argv[2]) if len(sys.argv) > 2 else 2)


def dump(n, ind="", maxarr=24, out=print):
    if n[0] == "REC":
        out(f"{ind}<{n[1]} v{n[2]}{' nested' if n[4] else ''} groups={len(n[3])}>")
        for gi, g in enumerate(n[3]):
            if n[4]: out(f"{ind} [group {gi}]")
            for c in g: dump(c, ind + "  ", maxarr, out)
    elif n[0] == "ARR":
        out(f"{ind}ARR {n[1]:#x} len={len(n[2])} {n[2][:maxarr].hex(' ')}")
    else:
        out(f"{ind}{n[1]:#x} {n[2]}")


def find(n, name, acc=None):
    acc = [] if acc is None else acc
    if n[0] == "REC":
        if n[1] == name: acc.append(n)
        for g in n[3]:
            for c in g: find(c, name, acc)
    return acc
