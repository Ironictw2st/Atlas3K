"""Terry component fields from the Ghidra decompiles of the component constructors (qttoolutility QTU::EC*).

Every component builds its fields in its default constructor as UTILITYDLL property objects
(PROPERTY_BOOL / PROPERTY_RANGED_INT / PropertyEnum ...) named with a display string ("Flag Facing Direction"), then
registers them with EntityComponent::add_property in the order Terry writes them. Terry writes the attribute as the
display name in lower case with spaces turned into underscores ("flag_facing_direction"); this is checked against
the kit corpus in check_corpus.py.

This parses the decompiled C (one file per constructor, see DecompileMatching.java) with a few regexes, reads float
constants (DAT_...) and enum value names (enum_reflections.py) from the DLL, and writes one JSON record per component.

usage: ctor_fields.py <decompile dir> [--out fields.json]
"""
import argparse, json, re, struct
from pathlib import Path
import capstone
from qmeta_extract import Image, DEFAULT_DLL
import enum_reflections

HEADER = re.compile(r"^// (?P<cls>[\w:]+)::(?P<name>\w+) @ (?P<addr>[0-9a-f]+)", re.M)
STR_LIT = re.compile(r"\w+(?:::\w+)*\(\s*(?:\(\w+ \*\))?&?(?P<var>\w+)\s*,\s*\"(?P<lit>[^\"]*)\"\s*\)")
REFL = re.compile(r"\(IEnumReflection \*\)(?:(?P<fn>FUN_[0-9a-f]+)\(\)|&(?P<ptr>\w+))")
PROP = re.compile(r"(?:UTILITYDLL::)?(?P<kind>PROPERTY_[A-Z_0-9]+|PropertyEnumFlags|PropertyEnum)::(?P=kind)\s*\((?P<args>[^;]*?)\)\s*;", re.S)
STORE = re.compile(r"\*\(\w+ \*\*\)\(this \+ (?P<off>0x[0-9a-f]+)\) = \w+;")
SETADD = re.compile(r"PROPERTY_SET::add_property\s*\([^,]*,\s*\*\(PROPERTY \*\*\)\(this \+ (?P<off>0x[0-9a-f]+)\)")
ADD = re.compile(r"tr\([^;]*?\"(?P<name>[^\"]*)\"\s*,\s*0\);\s*(?:[^;]*;\s*){0,2}?[\w:]*EntityComponent::add_property", re.S)
ATTR = re.compile(r"add_attribute\s*\((?P<args>[^;]*?)\)\s*;", re.S)
FASSIGN = re.compile(r"(?P<var>[fd]Var\d+) = (?:\(float\))?(?P<val>_?DAT_[0-9a-f]+|-?[0-9.]+(?:e-?\d+)?);")
PLOAD = re.compile(r"(?P<var>\w+) = \*\(\w+ \*\*\)\(this \+ (?P<off>0x[0-9a-f]+)\);")


def split_args(s):
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch == "(": depth += 1
        elif ch == ")": depth -= 1
        if ch == "," and depth == 0: out.append(cur.strip()); cur = ""
        else: cur += ch
    if cur.strip(): out.append(cur.strip())
    return out


def var_of(arg):
    return re.sub(r"\([^)]*\)", "", arg).replace("&", "").replace("*", "").strip()


class Constants:
    def __init__(self, img):
        self.img = img
        self.locals = {}   # fVarN -> the DAT_ / literal last assigned to it (reset per file)

    def number(self, tok, as_float):
        tok = tok.strip()
        tok = self.locals.get(tok, tok)
        m = re.fullmatch(r"(?:_)?DAT_([0-9a-f]+)", tok)
        if m:
            va = int(m.group(1), 16)
            return round(struct.unpack("<f", self.img.raw(va, 4))[0], 6) if as_float else self.img.i32(va)
        try:
            if tok in ("true", "false"): return tok == "true"
            v = int(tok, 0) if not re.search(r"[.eE]", tok) or tok.startswith("0x") else float(tok)
            if as_float and isinstance(v, int) and abs(v) > 0xFFFF:   # float passed as raw bits
                return round(struct.unpack("<f", struct.pack("<I", v & 0xFFFFFFFF))[0], 6)
            return float(v) if as_float else v
        except ValueError:
            return tok


def parse_file(text, consts, refl_cache, img, cs):
    h = HEADER.search(text)
    events = []
    for rx, kind in ((STR_LIT, "str"), (REFL, "refl"), (PROP, "prop"), (ADD, "add"), (ATTR, "attr"), (STORE, "store"),
                     (SETADD, "setadd"), (PLOAD, "pload"), (FASSIGN, "fassign")):
        for m in rx.finditer(text): events.append((m.start(), kind, m))
    events.sort(key=lambda e: e[0])
    strs, last_refl, props, adds, last_lit, loads = {}, None, [], [], None, {}
    for _, kind, m in events:
        if kind == "str":
            strs[m["var"]] = m["lit"]; last_lit = m["lit"]
        elif kind == "refl":
            last_refl = m["fn"] or m["ptr"]
        elif kind == "prop":
            a = split_args(m["args"])
            name = strs.get(var_of(a[1])) if len(a) > 1 else None
            p = {"kind": m["kind"], "display": name, "raw_args": a[2:]}
            k = m["kind"]
            if k in ("PropertyEnum", "PropertyEnumFlags"):
                p["default_raw"] = a[2] if len(a) > 2 else None
                p["reflection"] = last_refl
                if last_refl and (last_refl.startswith("FUN_") or last_refl.startswith("PTR_PTR_")):
                    if last_refl not in refl_cache:
                        refl_cache[last_refl] = (enum_reflections.resolve(img, cs, int(last_refl[4:], 16))
                                                 if last_refl.startswith("FUN_") else
                                                 enum_reflections.resolve_object(img, cs, int(last_refl[8:], 16)))
                    r = refl_cache[last_refl]
                    p["values"] = r.get("slots", {}).get(2)
                    disp = r.get("slots", {}).get(3) or []
                    p["enum_type"] = disp[1] if len(disp) > 1 else None
                    p["value_labels"] = disp[0::2] if disp else None
                if p.get("values") and k == "PropertyEnum":
                    d = consts.number(a[2], False) if len(a) > 2 else 0
                    p["default"] = p["values"][d] if isinstance(d, int) and 0 <= d < len(p["values"]) else d
            elif k == "PROPERTY_BOOL":
                p["default"] = consts.number(a[2], False) if len(a) > 2 else None
            elif k in ("PROPERTY_INT",):
                p["default"] = consts.number(a[2], False)
            elif k == "PROPERTY_RANGED_INT":
                p["default"], p["min"], p["max"] = (consts.number(x, False) for x in a[2:5])
            elif k == "PROPERTY_FLOAT":
                p["default"] = consts.number(a[2], True)
            elif k == "PROPERTY_RANGED_FLOAT":
                p["default"], p["min"], p["max"] = (consts.number(x, True) for x in a[2:5])
            elif k in ("PROPERTY_STRING", "PROPERTY_FILENAME"):
                p["default"] = strs.get(var_of(a[2]), "") if len(a) > 2 else ""
            props.append(p)
        elif kind == "store":
            if props and "offset" not in props[-1]: props[-1]["offset"] = m["off"]
        elif kind == "add":
            adds.append(m["name"])
        elif kind == "setadd":
            p = next((q for q in props if q.get("offset") == m["off"]), None)
            if p is not None and p["display"]: adds.append(p["display"])
        elif kind == "fassign":
            consts.locals[m["var"]] = m["val"]
        elif kind == "pload":
            loads[m["var"]] = m["off"]
        elif kind == "attr":
            # add_attribute(prop, key, value) on a property loaded from this+off: CUSTOM_TYPE_ATTRIBUTE -> the type
            # name Terry uses for the value list (a DB table or an enum), "suffix" -> a unit, ...
            a = split_args(m["args"])
            if len(a) < 3: continue
            p = next((q for q in props if q.get("offset") == loads.get(var_of(a[0]))), None)
            key_m = re.search(r"(\w+?)_exref", a[1])
            key = key_m.group(1) if key_m else strs.get(var_of(a[1]), a[1])
            val = strs.get(var_of(a[2]))
            if p is not None and val is not None and "override_property_attribute" not in a[1]:
                p.setdefault("attributes", {})[key] = val
    # tie the add_property names to the constructed properties: same display name, else construction order
    fields, unused = [], [p for p in props]
    for n in adds:
        p = next((q for q in unused if q["display"] == n), None) or next((q for q in unused if q["display"] is None), None)
        if p is None: fields.append({"display": n, "kind": "?"}); continue
        unused.remove(p)
        fields.append(dict(p, display=n))
    for f in fields:
        f["attribute"] = f["display"].lower().replace(" ", "_")
    return {"class": h["cls"] if h else None, "address": h["addr"] if h else None, "fields": fields,
            "unregistered": [p for p in unused]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--out")
    a = ap.parse_args()
    img = Image(DEFAULT_DLL)
    cs = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); cs.detail = True
    consts, refl_cache, out = Constants(img), {}, {}
    for f in sorted(Path(a.dir).glob("*.c")):
        text = f.read_text(encoding="utf-8", errors="replace")
        if "(void) __ptr64" not in text.split("\n", 4)[2] + text.split("\n", 6)[3]:   # default constructors only
            continue
        consts.locals = {}
        r = parse_file(text, consts, refl_cache, img, cs)
        comp = r["class"].split("::")[-1]
        out[comp] = r
    text = json.dumps(out, indent=1, default=str)
    if a.out: Path(a.out).write_text(text, encoding="utf-8")
    else: print(text)


if __name__ == "__main__":
    main()
