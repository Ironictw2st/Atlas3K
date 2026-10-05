"""Dump the Qt meta-object (Q_PROPERTY / Q_ENUM) tables of Terry's entity components from qttoolutility.

Terry's components (QTU::EC*) are QObjects; Terry writes and reads a component's properties through its
QMetaObject, so the property table is the field list. The staticMetaObject symbols are not exported, but every
class exports metaObject(), which returns &staticMetaObject: this script disassembles that function, takes the
RIP-relative address it loads, and decodes the Qt 5 QMetaObject (string table, data array, properties, enums).

It also scans the module's data sections for every other QMetaObject, so enums declared on another class or on a
namespace (Q_ENUM_NS) can be resolved by name.

usage: qmeta_extract.py [--dll <path>] [--out <json>] [--filter EC]   -> JSON on stdout or --out
"""
import argparse, json, struct, sys
import capstone, pefile

DEFAULT_DLL = (r"C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\assembly_kit\binaries"
               r"\qttoolutility.modder.x64.dll")

QT_TYPES = {1: "bool", 2: "int", 3: "uint", 4: "qlonglong", 5: "qulonglong", 6: "double", 7: "QChar", 8: "QVariantMap",
            9: "QVariantList", 10: "QString", 11: "QStringList", 12: "QByteArray", 13: "QBitArray", 14: "QDate",
            15: "QTime", 16: "QDateTime", 17: "QUrl", 18: "QLocale", 19: "QRect", 20: "QRectF", 21: "QSize",
            22: "QSizeF", 23: "QLine", 24: "QLineF", 25: "QPoint", 26: "QPointF", 27: "QRegExp", 28: "QVariantHash",
            31: "void*", 32: "long", 33: "short", 34: "char", 35: "ulong", 36: "ushort", 37: "uchar", 38: "float",
            39: "QObject*", 41: "QVariant", 43: "QUuid", 64: "QFont", 65: "QPixmap", 66: "QBrush", 67: "QColor",
            68: "QPalette", 69: "QIcon", 70: "QImage", 71: "QPolygon", 72: "QRegion", 73: "QBitmap", 74: "QCursor",
            75: "QKeySequence", 76: "QPen", 77: "QTextLength", 78: "QTextFormat", 79: "QMatrix", 80: "QTransform",
            81: "QMatrix4x4", 82: "QVector2D", 83: "QVector3D", 84: "QVector4D", 85: "QQuaternion",
            86: "QPolygonF", 43 + 1000: "?"}
PROP_FLAGS = {0x1: "read", 0x2: "write", 0x4: "reset", 0x8: "enum_or_flag", 0x400: "constant", 0x800: "final",
              0x1000: "designable", 0x4000: "scriptable", 0x10000: "stored", 0x40000: "editable", 0x100000: "user",
              0x400000: "notify", 0x800000: "revisioned"}


class Image:
    def __init__(self, path):
        self.pe = pefile.PE(path, fast_load=True)
        self.pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXPORT"]])
        self.base = self.pe.OPTIONAL_HEADER.ImageBase
        self.data = self.pe.get_memory_mapped_image()
        self.size = len(self.data)

    def ok(self, va):
        return self.base <= va < self.base + self.size

    def u32(self, va): return struct.unpack_from("<I", self.data, va - self.base)[0]
    def i32(self, va): return struct.unpack_from("<i", self.data, va - self.base)[0]
    def u64(self, va): return struct.unpack_from("<Q", self.data, va - self.base)[0]
    def raw(self, va, n): return self.data[va - self.base:va - self.base + n]

    def exports(self):
        for e in self.pe.DIRECTORY_ENTRY_EXPORT.symbols:
            if e.name: yield e.name.decode("latin1"), self.base + e.address


def demangle_class(sym):
    """'?metaObject@ECWall@QTU@@UEBA...' -> 'QTU::ECWall'."""
    parts = sym[1:].split("@@")[0].split("@")[1:]
    return "::".join(reversed(parts))


class MetaObject:
    def __init__(self, img, va):
        self.va = va
        self.superdata, self.stringdata, self.d = (img.u64(va), img.u64(va + 8), img.u64(va + 16))
        self.img = img
        if not (img.ok(self.stringdata) and img.ok(self.d)): raise ValueError("not a meta-object")
        h = [img.u32(self.d + 4 * i) for i in range(14)]
        self.revision = h[0]
        if self.revision not in (7, 8): raise ValueError(f"revision {self.revision}")
        self.h = h

    def s(self, idx):
        e = self.stringdata + 24 * idx
        size, off = self.img.i32(e + 4), struct.unpack_from("<q", self.img.data, e + 16 - self.img.base)[0]
        if not (0 <= size < 4096): raise ValueError("bad string")
        return self.img.raw(e + off, size).decode("latin1")

    def u(self, i): return self.img.u32(self.d + 4 * i)

    def decode(self):
        h = self.h
        out = {"class": self.s(h[1]), "revision": self.revision, "va": hex(self.va)}
        out["classinfo"] = {self.s(self.u(h[3] + 2 * i)): self.s(self.u(h[3] + 2 * i + 1)) for i in range(h[2])}
        props = []
        for i in range(h[6]):
            name, typ, flags = (self.u(h[7] + 3 * i + k) for k in range(3))
            tname = self.s(typ & 0x7FFFFFFF) if typ & 0x80000000 else QT_TYPES.get(typ, f"metatype_{typ}")
            props.append({"name": self.s(name), "type": tname,
                          "flags": [v for k, v in PROP_FLAGS.items() if flags & k], "flags_raw": hex(flags)})
        out["properties"] = props
        enums = []
        stride = 5 if self.revision >= 8 else 4
        for i in range(h[8]):
            base = h[9] + stride * i
            name = self.s(self.u(base))
            flags, count, data = (self.u(base + 2), self.u(base + 3), self.u(base + 4)) if stride == 5 \
                else (self.u(base + 1), self.u(base + 2), self.u(base + 3))
            keys = [(self.s(self.u(data + 2 * k)), self.i32_at(data + 2 * k + 1)) for k in range(count)]
            enums.append({"name": name, "is_flag": bool(flags & 1), "values": dict(keys)})
        out["enums"] = enums
        methods = []
        for i in range(h[4]):   # name, argc, parameters, tag, flags
            name, argc, params, tag, flags = (self.u(h[5] + 5 * i + k) for k in range(5))
            methods.append({"name": self.s(name), "argc": argc, "kind": ["method", "signal", "slot", "constructor"][(flags >> 2) & 3]})
        out["methods"] = methods
        return out

    def i32_at(self, i): return self.img.i32(self.d + 4 * i)


def metaobject_from_function(img, cs, va):
    """The last RIP-relative LEA in metaObject() is &staticMetaObject."""
    target = None
    for ins in cs.disasm(img.raw(va, 96), va):
        if ins.mnemonic == "lea" and "rip" in ins.op_str:
            target = ins.address + ins.size + ins.operands[1].mem.disp
        if ins.mnemonic in ("ret", "jmp") and target is not None: break
    return target


def scan_all(img):
    """Every QMetaObject in the writable/read-only data sections (stringdata + data both inside the image)."""
    found = {}
    for sec in img.pe.sections:
        name = sec.Name.rstrip(b"\0").decode()
        if name not in (".data", ".rdata"): continue
        start = img.base + sec.VirtualAddress
        for va in range(start, start + sec.Misc_VirtualSize - 48, 8):
            sd, d = img.u64(va + 8), img.u64(va + 16)
            if not (img.ok(sd) and img.ok(d)): continue
            try:
                if img.u32(d) not in (7, 8): continue
                mo = MetaObject(img, va)
                found[va] = mo.decode()
            except Exception:
                continue
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dll", default=DEFAULT_DLL)
    ap.add_argument("--out")
    ap.add_argument("--filter", default="EC")
    a = ap.parse_args()
    img = Image(a.dll)
    cs = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); cs.detail = True
    all_mo = scan_all(img)
    by_va = {int(v["va"], 16): v for v in all_mo.values()}
    classes = {}
    for sym, va in img.exports():
        if not sym.startswith("?metaObject@"): continue
        cls = demangle_class(sym)
        if a.filter and a.filter not in cls: continue
        mo_va = metaobject_from_function(img, cs, va)
        if mo_va is None: continue
        d = by_va.get(mo_va)
        if d is None:
            try: d = MetaObject(img, mo_va).decode()
            except Exception as ex: d = {"error": str(ex), "va": hex(mo_va)}
        sup = img.u64(mo_va) if img.ok(mo_va) else 0
        d = dict(d, export=cls, super=by_va.get(sup, {}).get("class") if sup else None)
        classes[cls] = d
    enums = {}
    for mo in all_mo.values():
        for e in mo.get("enums", []):
            enums.setdefault(f'{mo["class"]}::{e["name"]}', e)
    result = {"dll": a.dll, "metaobjects_in_image": len(all_mo), "classes": classes, "enums": enums}
    text = json.dumps(result, indent=1)
    if a.out: open(a.out, "w", encoding="utf-8").write(text)
    else: sys.stdout.write(text)


if __name__ == "__main__":
    main()
