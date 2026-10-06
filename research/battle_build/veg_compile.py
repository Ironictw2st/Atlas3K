"""Python port of BOB's procedural vegetation parameters: QTU::Procedural::GenerationParameters (parse of
battleterrain/vegetation/*tree_parameters.xml, generation_categories.xml, per_climate_densities.xml) and
QTU::ProceduralTerrainContent::ParametersCompiled (FUN_1800855c0: groups FUN_1800d7660, objects FUN_1800c64d0).
Compared with a frida_veg_procedural.js dump: veg_compile.py <label> <veg xml folder> <.terry> [k]"""
import math, os, re, struct, sys
import xml.etree.ElementTree as ET
import numpy as np

F = np.float32
PI = F(3.1415927410125732)
INV180 = F(0.0055555556900799274)
PROB_EPS = F(0.0010000000474974513)   # DAT_1805f5848
CLIMATE_ORDER = ["arid", "arid_fertile", "cold", "subtropical", "temperate", "tropical"]  # BOB's climate loop order
TYPES = {"tree": 1, "prop": 2, "decal": 4, "vfx": 8, "prefab": 0x10, "building": 0x20}


def parse_xml(path):
    """CA's XML reader is lenient about comments: a comment runs to the first "-->" (the shipped sbt_grass0 file
    nests one), so strip them before a strict parser sees the text."""
    text = open(path, "rb").read().decode("utf-8-sig", errors="replace")
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    return ET.fromstring(text.encode("utf-8"))


def f32(text):
    """calibs CA::UniString::parse(float&) as UTILITYDLL::XML_VALUE::as_float32 uses it: digits accumulated in float
    (v*10 + d, fraction d * 0.1f^k), optional exponent applied as repeated *10 / *0.1f; the whole text must parse,
    otherwise 0.0."""
    s = text
    i, n = 0, len(s)
    neg = n > 0 and s[0] == "-"
    if neg:
        i = 1
    v = F(0.0)
    while i < n and "0" <= s[i] <= "9":
        v = F(F(v * F(10.0)) + F(ord(s[i]) - 48))
        i += 1
    tenth = F(0.10000000149011612)
    if i < n and s[i] == ".":
        i += 1
        f = F(1.0)
        while i < n and "0" <= s[i] <= "9":
            f = F(f * tenth)
            v = F(F(F(ord(s[i]) - 48) * f) + v)
            i += 1
    if i < n and s[i] in "Ee":
        sign = s[i + 1] if i + 1 < n else ""
        j = i + 2 if sign in ("-", "+") else i + 1
        e = 0
        while j < n and "0" <= s[j] <= "9":
            e = e * 10 + ord(s[j]) - 48
            j += 1
        if j != n:
            return F(0.0)
        for _ in range(e):
            v = F(v * (tenth if sign == "-" else F(10.0)))
        i = j
    if i != n:
        return F(0.0)
    return F(-v) if neg else v


def normalise(lo, hi, fall):
    """FUN_1800723d0: (low, high, falloff) -> the inner range and the falloff width."""
    f2 = F(fall * F(0.5))
    f1 = F(F(hi - lo) * F(0.5))
    f3 = F(F(hi + lo) * F(0.5))
    if f1 < f2:
        return lo, hi, F(0.0)
    return F(f3 - f2), F(f2 + f3), F(f1 - f2)


class Group:
    pass


class Obj:
    pass


class GenerationParameters:
    def __init__(self, files, categories, densities):
        self.categories = categories                  # names, index = order in generation_categories.xml
        self.max_trees = densities                    # name -> max_trees_per_metre_squared (float32)
        self.groups = {}                              # name -> Group (first wins)
        self.objects = {}                             # "group/model" key -> Obj (first wins)
        self.by_category = {}                         # category index -> {key: Obj}
        self.by_group = {}                            # group name -> {key: Obj} (all groups of that name)
        self.errors = []
        for path in files:
            root = parse_xml(path)
            for g in root:
                if g.tag == "group":
                    self.parse_group(g)

    def child(self, e, name):
        c = e.find(name)
        return None if c is None else (c.text or "")

    def parse_group(self, e):
        name = e.get("group_name")
        if name is None:
            return False
        g = Group()
        g.name = name
        req = ["group_channel_range_low", "group_channel_range_high", "group_channel_range_falloff"]
        if any(self.child(e, r) is None for r in req):
            return False
        g.range = normalise(*(f32(self.child(e, r)) for r in req))
        g.slope_min = F(F(f32(self.child(e, "slope_min")) * PI) * INV180) if self.child(e, "slope_min") is not None else F(0)
        g.slope_max = (F(F(f32(self.child(e, "slope_max")) * PI) * INV180) if self.child(e, "slope_max") is not None
                       else F(1.5707963705062866))
        req = ["height_range_low", "height_range_high", "height_range_falloff"]
        if any(self.child(e, r) is None for r in req):
            return False
        g.height = normalise(*(f32(self.child(e, r)) for r in req))
        if self.child(e, "probability") is None or self.child(e, "texture") is None:
            return False
        g.prob = f32(self.child(e, "probability"))
        g.texture = self.child(e, "texture")
        tfp = self.child(e, "texture_for_probability")
        g.probs = tfp.split(",")[:8] if tfp is not None else [g.texture]
        g.gprob = f32(self.child(e, "grouping_probability")) if self.child(e, "grouping_probability") is not None else F(0)
        g.gradius = f32(self.child(e, "grouping_radius")) if self.child(e, "grouping_radius") is not None else F(0)
        if name in self.groups:
            self.errors.append(f"group {name} used multiple times")
        else:
            self.groups[name] = g
        for c in e:
            if c.tag in TYPES and not self.parse_object(c, name, TYPES[c.tag]):
                return False
        self.normalise_probabilities(name)
        return True

    def normalise_probabilities(self, name):
        """FUN_180072430 at the end of every group parse: scale the group's objects (all groups of that name so far)
        so the most probable has probability 1."""
        objs = list(self.by_group.setdefault(name, {}).values())
        if not objs:
            return
        mx = objs[0]
        for o in objs[1:]:
            if not (o.prob <= mx.prob):
                mx = o
        if PROB_EPS <= mx.prob:
            k = F(F(1.0) / mx.prob)
            for o in objs:
                o.prob = F(k * o.prob)

    def parse_object(self, e, group, typ):
        o = Obj()
        o.group, o.type = group, typ
        o.model = self.child(e, "model")
        if o.model is None:
            return False
        for r in ("size_low", "size_high", "blendmap_range_low", "blendmap_range_high", "blendmap_range_falloff",
                  "height_low", "height_high", "height_falloff", "probability"):
            if self.child(e, r) is None:
                return False
        o.size_low = f32(self.child(e, "size_low"))
        o.size_high = f32(self.child(e, "size_high"))
        o.size_range = F(o.size_high - o.size_low)
        o.blend = normalise(*(f32(self.child(e, r)) for r in ("blendmap_range_low", "blendmap_range_high",
                                                              "blendmap_range_falloff")))
        o.height = normalise(*(f32(self.child(e, r)) for r in ("height_low", "height_high", "height_falloff")))
        o.prob = f32(self.child(e, "probability"))
        ms = self.child(e, "minimum_seperation")
        o.minsep = f32(ms) if ms is not None else F(0)
        o.small = e.find("small_object") is not None
        o.outfield = e.find("include_in_outfield") is not None
        o.upright = e.find("keep_upright") is not None
        o.parallax = f32(self.child(e, "parallax")) if self.child(e, "parallax") is not None else F(1.0)
        df = e.find("decal_flags")
        o.decal = (True, False, True, False)
        if df is not None:
            b = lambda k, d: (df.get(k, "true" if d else "false").strip().lower() == "true")
            o.decal = (b("apply_to_terrain", True), b("apply_to_objects", False), b("blend_normals", True),
                       b("render_above_snow", False))
        hum = e.find("humidities")
        cats = e.find("categories")
        if hum is None or cats is None:
            return False
        cat_names = [c.text.strip() for c in cats if c.tag == "category"]
        if not cat_names or any(c.tag != "category" for c in cats):
            return False
        key = group + "/" + o.model
        if key not in self.objects:
            self.objects[key] = o
        o = self.objects[key]
        self.by_group.setdefault(group, {}).setdefault(key, o)
        for cn in cat_names:
            if cn in self.categories:
                self.by_category.setdefault(self.categories.index(cn), {}).setdefault(key, o)
        return True


def load(folder):
    cats = [c.text.strip() for c in ET.parse(os.path.join(folder, "generation_categories.xml")).getroot()]
    dens = {}
    for c in ET.parse(os.path.join(folder, "per_climate_densities.xml")).getroot():
        dens[c.find("name").text.strip()] = f32(c.find("max_trees_per_metre_squared").text)
    files = sorted((os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith("tree_parameters.xml")),
                   key=lambda p: os.path.basename(p).lower())
    return GenerationParameters(files, cats, dens)


def clamp01(v):
    return F(0) if not (v >= 0) else (F(1) if F(1) <= v else v)


def clamp_h(v):
    lo, hi = F(-5000.0), F(5000.0)
    if not (lo <= v):
        return lo
    return hi if hi <= v else v


def u8(v):
    return int(v) & 0xFF


def u16(v):
    return int(v) & 0xFFFF


def str_less_key(s):
    return s.encode("latin1")


def compile_tile(gp, climate, textures, tiles=(8, 8), density=128, unit=2.0):
    """ParametersCompiled for one climate: (header dict, groups bytes (n,20), objects bytes (n,12), object list)."""
    cat = gp.categories.index(climate)
    objs = list(gp.by_category.get(cat, {}).values())
    objs.sort(key=lambda o: (str_less_key(o.group), str_less_key(o.model)))
    tex_index = {t: i for i, t in enumerate(textures)}
    used = {o.group for o in objs}
    pairs = []
    for name, g in gp.groups.items():
        if name in used and g.texture in tex_index:
            pairs.append((tex_index[g.texture], name))
    pairs.sort(key=lambda p: (p[0], str_less_key(p[1])))
    ends = []
    for ch in range(len(textures)):
        ends.append(sum(1 for c, _ in pairs if c <= ch))
    ends += [0] * (8 - len(ends))
    k255, k65535 = F(255.0), F(6.553500175476074)
    groups = []
    layout = list(objs)       # FUN_1800855c0 then copies each compiled group's run, in group order, to the front
    pos = 0
    for ch, name in pairs:
        g = gp.groups[name]
        start = next((i for i, o in enumerate(objs) if o.group == name), len(objs))
        count = sum(1 for o in objs if o.group == name)
        layout[pos:pos + count] = objs[start:start + count]
        first = pos
        pos += count
        mask = 0
        for t in g.probs:
            if t and t in tex_index:
                mask |= 1 << tex_index[t]
        p = g.prob if g.prob >= 0 else F(0)
        p = F(10.0) if F(10.0) <= p else p
        b = bytearray(20)
        struct.pack_into("<HHBBB", b, 0, u16(F(p * F(6553.5))), first, count & 0xFF, mask & 0xFF, ch & 0xFF)
        b[7], b[8], b[9] = (u8(F(clamp01(v) * k255)) for v in g.range)
        struct.pack_into("<3H", b, 10, *(u16(F(F(clamp_h(v) - F(-5000.0)) * k65535)) for v in g.height))
        b[16] = u8(F(clamp01(F(math.cos(g.slope_min))) * k255))
        b[17] = u8(F(clamp01(F(math.cos(g.slope_max))) * k255))
        b[18] = u8(F(clamp01(g.gprob) * k255))
        gr = g.gradius if g.gradius >= 0 else F(0)
        b[19] = u8(F(255.0) if F(255.0) <= gr else gr)
        groups.append(bytes(b))
    objs = layout
    objects = []
    for o in objs:
        b = bytearray(12)
        b[0] = u8(F(clamp01(o.prob) * k255))
        ms = o.minsep if o.minsep >= 0 else F(0)
        b[1] = u8(F(255.0) if F(255.0) <= ms else ms)
        b[2] = ((0x40 if not o.model else 0) | (0x80 if o.small else 0) | (o.type & 0x3F)) & 0xFF
        b[3], b[4], b[5] = (u8(F(clamp01(v) * k255)) for v in o.blend)
        struct.pack_into("<3H", b, 6, *(u16(F(F(clamp_h(v) - F(-5000.0)) * k65535)) for v in o.height))
        objects.append(bytes(b))
    s = F(F(1.0) / np.sqrt(gp.max_trees[climate]))
    cell = F(density * unit)
    W, H = F(tiles[0] * cell), F(tiles[1] * cell)
    nx = int(math.floor(F(F(F(1.0) / s) * W)))
    ny = int(math.floor(F(F(F(1.0) / s) * H)))
    hdr = dict(ends=ends, aw=W, ah=H, nx=nx, ny=ny, pix=F(cell * F(F(1.0) / F(density))), offx=F(density),
               offy=F(density), ox=F(F(W - F(F(nx - 1) * s)) * F(0.5)), oz=F(F(H - F(F(ny - 1) * s)) * F(0.5)), s=s,
               tw=tiles[0], th=tiles[1], cell=cell, inv_unit=F(F(1.0) / F(unit)))
    return hdr, np.frombuffer(b"".join(groups), np.uint8).reshape(-1, 20), \
        np.frombuffer(b"".join(objects), np.uint8).reshape(-1, 12), objs


def terry_info(path):
    t = open(path, encoding="utf-8").read()
    tex = [re.search(f'texture_channel_{i}="([^"]*)"', t).group(1) for i in range(8)]
    climates = re.search(r'climate_mask="([^"]*)"', t).group(1).split(",")
    seed = int(re.search(r'vegetation_seed="(\d+)"', t).group(1))
    return tex, [c.strip() for c in climates if c.strip()], seed


if __name__ == "__main__":
    from veg_dump import dump
    label, folder, terry = sys.argv[1:4]
    calls = dump(label)
    gp = load(folder)
    tex, climates, seed = terry_info(terry)
    order = [c for c in CLIMATE_ORDER if c in climates]
    for k, d in sorted(calls.items()):
        climate = order[k]
        hdr, groups, objects, objs = compile_tile(gp, climate, tex)
        names = [p["name"] for p in d["object_params"]]
        mine = [o.model for o in objs]
        print(f"call {k} ({climate}): objects {len(mine)} vs {len(names)}, order {'ok' if mine == names else 'DIFFERS'}")
        if mine != names:
            for i, (a, b) in enumerate(zip(mine, names)):
                if a != b:
                    print("  first", i, a, b, objs[i].group, d["object_params"][i].get("group"))
                    break
        print(f"  groups {groups.shape} vs {d['groups'].shape}: {np.array_equal(groups, d['groups'])}")
        if groups.shape == d["groups"].shape and not np.array_equal(groups, d["groups"]):
            for i in range(len(groups)):
                if not np.array_equal(groups[i], d["groups"][i]):
                    print("  group", i, groups[i].tolist(), d["groups"][i].tolist())
        print(f"  objects {objects.shape} vs {d['objects'].shape}: {np.array_equal(objects, d['objects'])}")
        sc_ok = all((o.size_low, o.size_range, o.type) == (F(struct.unpack_from("<f", p["raw"], 0x1C)[0]),
                    F(struct.unpack_from("<f", p["raw"], 0x24)[0]), p["raw"][0xB5]) for o, p in zip(objs, d["object_params"]))
        print(f"  scale/type fields: {sc_ok}")
        if objects.shape == d["objects"].shape and not np.array_equal(objects, d["objects"]):
            bad = [i for i in range(len(objects)) if not np.array_equal(objects[i], d["objects"][i])]
            print("  objects differ:", len(bad), [(i, objects[i].tolist(), d["objects"][i].tolist()) for i in bad[:3]])
        h = d["compiled_header"]
        print("  ends", hdr["ends"], struct.unpack("<8h", h[:16]))
        ref = struct.unpack("<2f2i6f2if", h[0x58:0x8c])
        print("  header", [hdr[k] for k in ("aw", "ah", "nx", "ny", "pix", "offx", "offy", "ox", "oz", "s", "tw", "th",
                                            "cell")], ref)
        print("  seed", seed, struct.unpack_from("<I", d["input_raw"], 0x40)[0])
