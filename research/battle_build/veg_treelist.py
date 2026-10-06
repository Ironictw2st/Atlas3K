"""Battle tree list (FASTBIN0 TREE_LIST v3) writer + BOB's debug XML, with BOB's ordering: items sorted by
(model bytes, x, y, z), models in CA hash-map order of their sorted insertion. Item = x, y, z, scale (f32), rotation
byte, is_freeform byte."""
import struct
from decimal import Decimal, ROUND_HALF_UP
import numpy as np
from veg_cahash import hash_map_order

F = np.float32
ROT_K = F(40.7436637878418)          # 256 / 2pi
TWO_PI = F(6.2831854820251465)


def rot_byte(r):
    """bob_vegetation FUN_180009fe0: wrap once into [0, 2pi), then (int)(r * 256/2pi)."""
    r = F(r)
    if r < 0:
        r = F(r + TWO_PI)
    if TWO_PI <= r:
        r = F(r + F(-6.2831854820251465))
    return int(F(r * ROT_K)) & 0xFF


def build(items):
    """items: (model key, x, y, z, scale, rot byte, freeform) -> [(key, [items])] in BOB order."""
    items = sorted(items, key=lambda t: (t[0].encode("latin1"), t[1], t[2], t[3]))
    groups = {}
    for it in items:
        groups.setdefault(it[0], []).append(it)
    return [(k, groups[k]) for k in hash_map_order([it[0] for it in items])]


def to_bin(lst):
    out = bytearray(b"FASTBIN0" + struct.pack("<HI", 3, len(lst)))
    for k, its in lst:
        kb = k.encode("latin1")
        out += struct.pack("<H", len(kb)) + kb + struct.pack("<I", len(its))
        for _, x, y, z, s, r, ff in its:
            out += struct.pack("<ffffBB", x, y, z, s, r, 1 if ff else 0)
    return bytes(out)


def fmt(v):
    """MSVC printf %f: the exact binary value rounded half away from zero to 6 decimals."""
    return str(Decimal(float(v)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def to_xml(lst):
    L = ["<TREE_LIST serialise_version='3'>", "\t<TREE_LIST>"]
    for k, its in lst:
        L.append(f"\t\t<BATTLE_TREE_ITEM_VECTOR key='{k}'>")
        L.append("\t\t\t<value>")
        for _, x, y, z, s, r, ff in its:
            L.append(f"\t\t\t\t<BATTLE_TREE_ITEM x='{fmt(x)}' y='{fmt(y)}' z='{fmt(z)}' scale='{fmt(s)}' "
                     f"rotation='{r}' is_freeform='{'true' if ff else 'false'}'/>")
        L.append("\t\t\t</value>")
        L.append("\t\t</BATTLE_TREE_ITEM_VECTOR>")
    L += ["\t</TREE_LIST>", "</TREE_LIST>"]
    return "\r\n".join(L) + "\r\n"
