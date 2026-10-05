"""Resolve the enum value names behind Terry's PropertyEnum fields (qttoolutility IEnumReflection objects).

A component constructor builds an enum field as PropertyEnum(name, default, reflection) where reflection comes from a
small getter (FUN_1800ec3d0 ...) that returns a static object whose first qword is a vftable. The vftable's slots
include an index -> name function that fills a static QString table with QString::fromAscii_helper("CLIT_MAJOR", n)
calls; this script disassembles every slot and collects those literals in call order.

usage: enum_reflections.py <getter VA hex> [...]   -> JSON {getter: {vftable, slots: {slot: [strings]}}}
"""
import json, sys
import capstone
from qmeta_extract import Image, DEFAULT_DLL


def cstring(img, va, limit=128):
    if not img.ok(va): return None
    b = img.raw(va, limit)
    end = b.find(b"\0")
    if end <= 0: return None
    s = b[:end]
    if not all(32 <= c < 127 for c in s): return None
    return s.decode("ascii")


def rip_targets(img, cs, va, max_bytes=0x600, through_ret=False):
    """(address, target) for every RIP-relative operand until the first ret."""
    out = []
    for ins in cs.disasm(img.raw(va, max_bytes), va):
        for op in ins.operands:
            if op.type == capstone.x86.X86_OP_MEM and op.mem.base == capstone.x86.X86_REG_RIP:
                out.append((ins, ins.address + ins.size + op.mem.disp))
        if ins.mnemonic == "int3" or (ins.mnemonic == "ret" and not through_ret): break
    return out


def calls(img, cs, va, max_bytes=0x600):
    out = []
    for ins in cs.disasm(img.raw(va, max_bytes), va):
        if ins.mnemonic == "call" and ins.operands[0].type == capstone.x86.X86_OP_IMM: out.append(ins.operands[0].imm)
        if ins.mnemonic in ("ret", "int3"): break
    return out


def strings_in(img, cs, va):
    res = []
    for ins, t in rip_targets(img, cs, va, 0x1000, through_ret=True):
        if ins.mnemonic == "lea":
            s = cstring(img, t)
            if s: res.append(s)
    return res


def resolve(img, cs, getter):
    vft = None
    for ins, t in rip_targets(img, cs, getter, 0x80, through_ret=True):
        if ins.mnemonic == "lea" and img.ok(t) and img.ok(img.u64(t)) and img.ok(img.u64(t + 8)):
            vft = t   # the static object's vftable (first LEA that points at a table of code pointers)
            break
    if vft is None: return {"error": "no vftable"}
    return from_vftable(img, cs, vft)


def resolve_object(img, cs, obj):
    """A reflection that is a static object (PropertyEnum(..., &PTR_PTR_x)): its first qword is the vftable."""
    return from_vftable(img, cs, img.u64(obj))


def from_vftable(img, cs, vft):
    slots = {}
    text = next(s for s in img.pe.sections if s.Name.startswith(b".text"))
    t0, t1 = img.base + text.VirtualAddress, img.base + text.VirtualAddress + text.Misc_VirtualSize
    for i in range(12):
        fn = img.u64(vft + 8 * i)
        if not (t0 <= fn < t1): break
        ss = strings_in(img, cs, fn)
        if not ss:   # the names may sit one call deeper (a static-table initialiser)
            for c in calls(img, cs, fn)[:6]:
                if t0 <= c < t1: ss += strings_in(img, cs, c)
        if ss: slots[i] = ss
    return {"vftable": hex(vft), "slots": slots}


def main():
    img = Image(DEFAULT_DLL)
    cs = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); cs.detail = True
    print(json.dumps({g: resolve(img, cs, int(g, 16)) for g in sys.argv[1:]}, indent=1))


if __name__ == "__main__":
    main()
