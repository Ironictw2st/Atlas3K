"""Prototype codec for BOB battle BMD files (FASTBIN0 v35 BATTLE_MAP_DEFINITION_DATA): bmd_data.bin,
<climate>_procedural_bmd_data.bin, bmd_nogo_data.bin. The binary is decoded into an element tree that mirrors BOB's
debug .xml (same tags, attribute names and order), using the layout table in bmd_layout.json. Checks:
  bin -> tree -> bin   byte-identical
  bin -> tree -> xml   identical to BOB's .xml
usage: bmdcodec.py <file.bin> [more.bin ...]   (looks for <file>.xml next to each)"""
import json, struct, sys
from pathlib import Path

LAYOUT = json.loads((Path(__file__).resolve().parents[2] / "src/Atlas3K.Formats/Battle/Data/bmd_layout.json").read_text())

SCALAR = {"u8": "<B", "bool": "<B", "u16": "<H", "i16": "<h", "u32": "<I", "i32": "<i", "u64": "<Q", "i64": "<q",
          "f32": "<f", "f64": "<d", "ver": "<H"}


class Node:
    __slots__ = ("tag", "attrs", "children", "text", "raw")

    def __init__(self, tag):
        self.tag, self.attrs, self.children, self.text, self.raw = tag, [], [], None, []


def spec_for(tag, parent, ver=None):
    for k in ([f"{parent}>{tag}@{ver}", f"{tag}@{ver}"] if ver is not None else []) + [f"{parent}>{tag}", tag]:
        if k in LAYOUT:
            return LAYOUT[k]
    raise KeyError(f"no layout for {parent}>{tag} (ver {ver})")


class Reader:
    def __init__(self, data):
        self.d, self.p = data, 0

    def scalar(self, t):
        if t == "str":
            n, = struct.unpack_from("<H", self.d, self.p); self.p += 2
            s = self.d[self.p:self.p + n].decode("utf-8"); self.p += n
            return s
        if t == "wstr":
            n, = struct.unpack_from("<H", self.d, self.p); self.p += 2
            s = self.d[self.p:self.p + 2 * n].decode("utf-16-le"); self.p += 2 * n
            return s
        f = SCALAR[t]; v, = struct.unpack_from(f, self.d, self.p); self.p += struct.calcsize(f)
        return v


def fmt(t, v, enum=None):
    if enum is not None:
        return enum[v] if 0 <= v < len(enum) else str(v)
    if t == "bool": return "true" if v else "false"
    if t in ("f32", "f64"): return ("%f" % v)[:31]   # BOB formats into a 32-byte buffer
    return str(v)


TRACE = False


def decode(r, tag, parent, ops=None):
    if TRACE: print(f"  @{r.p:#x} {parent}>{tag}  {r.d[r.p:r.p+24].hex(' ')}")
    n = Node(tag)
    ops = ops if ops is not None else spec_for(tag, parent)
    i = 0
    while i < len(ops):
        op = ops[i]
        kind = op[0]
        if kind == "a":                      # ["a", name, type, (enum list name)]
            t = op[2]; v = r.scalar(t)
            n.attrs.append((op[1], fmt(t, v)))
            n.raw.append(v)
            if op[1] == "serialise_version":
                # version-specific layout continues
                key_tag = f"{parent}>{tag}@{v}" if f"{parent}>{tag}@{v}" in LAYOUT else (f"{tag}@{v}" if f"{tag}@{v}" in LAYOUT else None)
                if key_tag and ops is not LAYOUT[key_tag]:
                    ops = LAYOUT[key_tag]; i = [j for j, o in enumerate(ops) if o[0] == "a" and o[1] == "serialise_version"][0]
        elif kind == "e":                    # ["e", tag]
            n.children.append(decode(r, op[1], tag))
        elif kind == "l":                    # ["l", container_tag, item_tag]  -> <container> with u32 count items
            c = Node(op[1]); cnt = r.scalar("u32")
            for _ in range(cnt):
                c.children.append(decode(r, op[2], op[1]))
            n.children.append(c)
        elif kind == "L":                    # ["L", item_tag] count + items directly under this element
            cnt = r.scalar("u32")
            for _ in range(cnt):
                n.children.append(decode(r, op[1], tag))
        elif kind == "t":                    # ["t", type] text
            v = r.scalar(op[1]); n.text = fmt(op[1], v); n.raw.append(v)
        elif kind == "skip":                 # ["skip", nbytes, name] unknown bytes kept as hex attr (debug)
            n.attrs.append(("#" + op[2], r.d[r.p:r.p + op[1]].hex())); r.p += op[1]
        else:
            raise ValueError(op)
        i += 1
    return n


META = []   # [(type name, [values])] of the file being written, from META_TAG_KEYS


def meta_comments(n):
    """BOB annotates a non-zero meta_tags element with the tag names its flags and mask select (bit i = i-th value
    over all META_TAG_KEYS entries in order)."""
    a = dict(n.attrs); flags, mask = int(a["flags"]), int(a["mask"])
    if not flags and not mask: return []
    bits = [(name, v) for name, values in META for v in values]
    sel = [f"{t}.{v}" for i, (t, v) in enumerate(bits) if flags >> i & 1]
    msel = []
    for i, (t, v) in enumerate(bits):
        if mask >> i & 1 and t not in msel: msel.append(t)
    out = []
    if sel: out.append("flags = " + "; ".join(sel) + ";")
    if msel: out.append("mask = " + "; ".join(msel) + ";")
    return out


def to_xml(n, depth=0, out=None):
    out = out if out is not None else []
    ind = "\t" * depth
    attrs = "".join(f" {k}='{v}'" for k, v in n.attrs if not k.startswith("#"))
    if n.tag == "meta_tags" and (com := meta_comments(n)):
        out.append(f"{ind}<{n.tag}{attrs}>")
        for c in com: out.append(f"{ind}\t<!-- {c} -->")
        out.append(f"{ind}</{n.tag}>")
        return out
    if n.text is not None:
        out.append(f"{ind}<{n.tag}{attrs}>{n.text}</{n.tag}>")
    elif not n.children:
        out.append(f"{ind}<{n.tag}{attrs}/>")
    else:
        out.append(f"{ind}<{n.tag}{attrs}>")
        for c in n.children: to_xml(c, depth + 1, out)
        out.append(f"{ind}</{n.tag}>")
    return out


def put(out, t, v):
    if t == "str":
        b = v.encode("utf-8"); out += struct.pack("<H", len(b)) + b
    elif t == "wstr":
        b = v.encode("utf-16-le"); out += struct.pack("<H", len(b) // 2) + b
    else:
        out += struct.pack(SCALAR[t], v)


def encode(n, parent, out, ops=None):
    """Inverse of decode: writes the node (attributes from raw values, children in layout order)."""
    ops = ops if ops is not None else spec_for(n.tag, parent)
    ai = ci = 0
    i = 0
    while i < len(ops):
        op = ops[i]; kind = op[0]
        if kind == "a":
            v = n.raw[ai]; ai += 1; put(out, op[2], v)
            if op[1] == "serialise_version":
                for key in (f"{parent}>{n.tag}@{v}", f"{n.tag}@{v}"):
                    if key in LAYOUT and ops is not LAYOUT[key]:
                        ops = LAYOUT[key]; i = [j for j, o in enumerate(ops) if o[0] == "a" and o[1] == "serialise_version"][0]
                        break
        elif kind == "e":
            encode(n.children[ci], n.tag, out); ci += 1
        elif kind == "l":
            c = n.children[ci]; ci += 1
            out += struct.pack("<I", len(c.children))
            for x in c.children: encode(x, op[1], out)
        elif kind == "L":
            items = [c for c in n.children[ci:] if c.tag == op[1]]
            out += struct.pack("<I", len(items))
            for x in items: encode(x, n.tag, out)
            ci += len(items)
        elif kind == "t":
            put(out, op[1], n.raw[0])
        elif kind == "skip":
            out += bytes.fromhex(dict(n.attrs)["#" + op[2]])
        i += 1
    return out


def encode_file(root):
    out = bytearray(b"FASTBIN0")
    encode(root, "", out)
    return bytes(out)


def decode_file(data):
    assert data[:8] == b"FASTBIN0", data[:8]
    r = Reader(data); r.p = 8
    root = decode(r, "BATTLE_MAP_DEFINITION_DATA", "")
    return root, r.p


def main():
    global TRACE
    ok = True
    args = sys.argv[1:]
    if args and args[0] == "--trace": TRACE = True; args = args[1:]
    for f in args:
        data = Path(f).read_bytes()
        try:
            root, end = decode_file(data)
        except Exception as e:
            print(f"{f}: DECODE FAILED {e!r}"); ok = False; continue
        META[:] = [(dict(e.attrs)["name"], [v.text for v in e.children[0].children])
                   for e in root.children[0].children[0].children]
        xml = "\r\n".join(to_xml(root)) + "\r\n"
        ref = Path(f).with_suffix(".xml")
        status = f"consumed {end}/{len(data)}" + ("  bin IDENTICAL" if encode_file(root) == data else "  bin DIFF")
        if ref.exists():
            want = ref.read_bytes().decode("utf-8", errors="replace")
            if xml == want:
                status += "  xml IDENTICAL"
            else:
                a, b = xml.splitlines(), want.splitlines()
                k = next((i for i in range(min(len(a), len(b))) if a[i] != b[i]), min(len(a), len(b)))
                status += f"  xml DIFF at line {k + 1}:\n   ours: {a[k] if k < len(a) else '<eof>'}\n   bob:  {b[k] if k < len(b) else '<eof>'}"
                ok = False
        print(f"{f}: {status}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
