"""Round-2 corpus projects: COPIES of corpus battle tile projects under new GUIDs, with painted procedural vegetation,
a changed climate/vista, hand-placed trees, extra rivers and settlement (walls / gate / siege AI) prefabs.

usage: make_round2_project.py <spec name> <kit root> install|remove [--atlas <Atlas3K.Cli.exe>]
  install: writes the tile project into <kit>/raw_data/terrain/tiles/battle/_assembly_kit/<guid>, then produces the
           Terry-save inputs (raw map folder, working_data rules.bob, the tile database entry) with Atlas3K's
           `build-battle --only terry_save` (byte-identical to Terry's save on the round-1 corpus) and copies them into
           the kit. Also writes the project's sources into the corpus (<corpus>/<guid>/src).
  remove:  deletes everything install created (raw + working + tile database entry).
The user's own projects are never touched: sources come from the corpus snapshots (<corpus>/<id>/src).
"""
import glob, os, re, shutil, subprocess, sys
import numpy as np
import tifffile

CORPUS = r"Z:/Claude/BattleMaps/out/battle_parity"
ATLAS = r"Z:/Claude/TerryClone/src/Atlas3K.Cli/bin/Debug/net9.0/Atlas3K.Cli.exe"
PREFABS = "art/prefabs/battle"


def disc(cx, cy, r0, r1):
    """Weight 1 inside r0, linear falloff to 0 at r1 (blend-map pixels, 1280 x 1280; 1 px = 1.6 m)."""
    y, x = np.mgrid[0:1280, 0:1280]
    d = np.hypot(x - cx, y - cy)
    return np.clip((r1 - d) / max(r1 - r0, 1e-6), 0, 1)


def rect(x0, y0, x1, y1, feather=0):
    y, x = np.mgrid[0:1280, 0:1280]
    dx = np.minimum(x - x0, x1 - x); dy = np.minimum(y - y0, y1 - y)
    d = np.minimum(dx, dy).astype(float)
    return np.clip(d / feather if feather else (d >= 0), 0, 1)


def stripe(x0, x1):
    return rect(x0, 0, x1, 1280, 12)


# Painting: list of (channel index, weight field 0..1). Applied in order: the channel gets w*255, every other channel
# is scaled by (1-w), so each pixel keeps summing to 255.
SPECS = {
    # temperate, forest everywhere procedural vegetation is defined for temperate: forest0, forest1, grass1, dirt1, mud
    "r2_tmp_forest": dict(
        gid="5a2e0001_7c1d_4e6b_9a10_000000000001", src="dfe064a6_ea23_4253_af6f_8e4494c116bb",
        vista=None, climate=None,
        paint=[(4, lambda: disc(420, 420, 150, 260)),          # forest0: dense core, falloff ring
               (4, lambda: rect(150, 800, 520, 1100, 40)),
               (1, lambda: disc(900, 380, 110, 200)),           # grass1
               (3, lambda: stripe(700, 760)),                   # dirt1 stripe
               (6, lambda: rect(820, 900, 1000, 1080, 20))],    # mud0
        trees=[("trees/willow/willow_c", 1010, 1000), ("trees/pine_huangshan/huangshan_pine_k", 1040, 1010),
               ("trees/willow/willow_c", 1070, 1030)],
        rivers=1, prefabs=[], inline=[]),
    # cold climate + cold vista, siege layout: walls/gate/towers as prefab references, one wall and the siege AI node
    # templates inlined so ECWall / ECSiegeAI* land in the tile's own bmd; capture point + deployment from round 1
    "r2_cld_siege": dict(
        gid="5a2e0002_7c1d_4e6b_9a10_000000000002", src="df46bdbc_51c3_4e1d_ad45_0b859048fa83",
        vista="terrain/vistas/cold_1", climate="cold",
        paint=[(1, lambda: disc(300, 300, 120, 220)),           # grass1 (cld_grass1)
               (2, lambda: rect(900, 150, 1150, 400, 30)),      # dirt0
               (3, lambda: stripe(600, 650)),                   # dirt1
               (6, lambda: disc(250, 1000, 80, 150)),           # mud0
               (4, lambda: disc(1000, 1000, 100, 180))],        # forest0 (cold only has the river variant)
        trees=[], rivers=0,
        prefabs=[("main/settlement/walls/3k_main_han_city_wall_straight_01", "3k_main_han_city_wall_straight_01", 960, 800, 0),
                 ("main/settlement/walls/3k_main_han_city_wall_gate_01", "3k_main_han_city_wall_gate_01", 1024, 800, 0),
                 ("main/settlement/walls/3k_main_han_city_wall_straight_02", "3k_main_han_city_wall_straight_02", 1088, 800, 0),
                 ("main/settlement/walls/3k_main_han_city_wall_tower_01", "3k_main_han_city_wall_tower_01", 900, 800, 0),
                 ("main/settlement/walls/3k_main_han_city_wall_corner_ext_01", "3k_main_han_city_wall_corner_ext_01", 1150, 800, 0)],
        inline=[("main/settlement/walls/3k_main_han_city_wall_straight_01", (1024.0, 1250.0)),
                ("design/settlements/ai/siege_ai_node_template_entry", (1024.0, 760.0)),
                ("design/settlements/ai/siege_ai_node_template_area", (1024.0, 700.0)),
                ("design/settlements/ai/siege_ai_node_template_intersection", (980.0, 700.0))]),
    # several climates at once (subtropical vista), two extra rivers
    "r2_multi_climate": dict(
        gid="5a2e0003_7c1d_4e6b_9a10_000000000003", src="dfe064a6_ea23_4253_af6f_8e4494c116bb",
        vista="terrain/vistas/subtropical_1", climate="subtropical,temperate,arid,tropical",
        paint=[(4, lambda: disc(400, 900, 160, 260)),           # forest0
               (1, lambda: disc(950, 950, 120, 200)),           # grass1
               (5, lambda: rect(850, 200, 1100, 420, 30)),      # stones1 (sbt_stones1)
               (2, lambda: stripe(620, 690))],                  # dirt0
        trees=[], rivers=2, prefabs=[], inline=[]),
}


def paint_blend(path, paint):
    a = tifffile.imread(path).astype(np.float64)
    for ch, field in paint:
        w = field()[..., None]
        other = a * (1 - w)
        other[..., ch] = 0
        a = other
        a[..., ch] += w[..., 0] * 255
    out = np.rint(a).astype(np.int64)
    # keep the per-pixel sum at exactly 255 (put the rounding error on the largest channel)
    err = 255 - out.sum(-1)
    idx = out.argmax(-1)
    np.put_along_axis(out, idx[..., None], np.take_along_axis(out, idx[..., None], -1) + err[..., None], -1)
    out = np.clip(out, 0, 255).astype(np.uint8)
    write_blend_tiff(path, out)


def write_blend_tiff(path, a):
    """The same baseline TIFF Terry saves for a Blend8 map: little endian, 8 x uint8 contiguous samples,
    photometric MinIsBlack, LZW, one strip per row, SampleFormat uint, no ExtraSamples tag."""
    import struct
    import imagecodecs
    h, w, n = a.shape
    strips = [imagecodecs.lzw_encode(a[y].tobytes()) for y in range(h)]
    body = bytearray(b"II*\x00\x00\x00\x00\x00")
    offsets = []
    for s in strips:
        offsets.append(len(body)); body += s
        if len(body) % 2: body += b"\x00"
    def arr(fmt, vals):
        o = len(body); body.extend(struct.pack("<" + fmt * len(vals), *vals)); return o
    bps = arr("H", [8] * n)
    sfmt = arr("H", [1] * n)
    soff = arr("I", offsets)
    scnt = arr("I", [len(s) for s in strips])
    if len(body) % 2: body += b"\x00"
    tags = [(256, 4, 1, w), (257, 4, 1, h), (258, 3, n, bps), (259, 3, 1, 5), (262, 3, 1, 1), (273, 4, h, soff),
            (277, 3, 1, n), (278, 4, 1, 1), (279, 4, h, scnt), (284, 3, 1, 1), (339, 3, n, sfmt)]
    ifd = len(body)
    body += struct.pack("<H", len(tags))
    for code, typ, cnt, val in tags:
        if cnt == 1 and typ == 3:
            body += struct.pack("<HHIHH", code, typ, cnt, val, 0)
        else:
            body += struct.pack("<HHII", code, typ, cnt, val)
    body += struct.pack("<I", 0)
    struct.pack_into("<I", body, 4, ifd)
    open(path, "wb").write(bytes(body))
    back = tifffile.imread(path)
    assert back.shape == a.shape and np.array_equal(back, a), "blend TIFF did not read back"


def entity_id(n):
    return f"5a2e{n:011x}"


def prefab_ref(i, key, x, z, yaw):
    return f"""    <entity id="{entity_id(i)}">
      <ECPrefab key="{key}" turn_buildings_into_props="false"/>
      <ECMeshRenderSettings inherit_from_parent="false" cast_shadow="true" alpha="1" tint_colour="255 255 255 255" set_tint_colour_from_colour_overlay="false" faction_colour="255 255 255 255"/>
      <ECTransform position="{x} 0 {z}" rotation="0 {yaw} 0" scale="1 1 1" pivot="0 0 0"/>
      <ECTerrainClamp active="true" clamp_to_sea_level="false" terrain_oriented="false"/>
    </entity>
"""


def tree(i, key, x, z):
    return f"""    <entity id="{entity_id(i)}">
      <ECVegetation key="{key}"/>
      <ECTransform position="{x} 0 {z}" rotation="0 {(i * 37) % 360} 0" scale="1 1 1" pivot="0 0 0"/>
      <ECTerrainClamp active="true" clamp_to_sea_level="false" terrain_oriented="false"/>
    </entity>
"""


def add_entities(text, body, logical=""):
    text = text.replace("  </entities>", body + "  </entities>", 1)
    if logical.strip():
        if "<Logical/>" in text:
            text = text.replace("<Logical/>", "<Logical>" + logical + "</Logical>", 1)
        else:
            text = text.replace("</Logical>", logical.strip("\n") + "\n    </Logical>", 1)
    return text


def inline_prefab(ak, rel, offset, text, salt):
    pl = glob.glob(os.path.join(ak, "raw_data", PREFABS, rel + ".*.layer"))[0]
    s = open(pl, encoding="utf-8").read()
    body = s.split("<entities>", 1)[1].split("</entities>", 1)[0]
    # fresh ids (prefab ids could collide with the tile's or with another inlined copy)
    ids = re.findall(r'<entity id="([0-9a-f]+)"', body)
    remap = {old: f"5a2f{salt:03x}{k:08x}" for k, old in enumerate(ids)}
    for old, new in remap.items():
        body = body.replace(f'"{old}"', f'"{new}"')
    def moved(m):
        x, y, z = (float(v) for v in m.group(2).split())
        return f'{m.group(1)}position="{x + offset[0]:g} {y:g} {z + offset[1]:g}"'
    body = re.sub(r'(<ECTransform )position="([^"]+)"', moved, body)
    logical = re.search(r"<Logical>(.*?)</Logical>", s, re.S)
    lg = logical.group(1) if logical else ""
    for old, new in remap.items():
        lg = lg.replace(f'"{old}"', f'"{new}"')
    return add_entities(text, body.strip("\n") + "\n", lg)


def extra_rivers(text, n):
    m = re.search(r'    <entity id="([0-9a-f]+)">\s*<ECRiver/>.*?</entity>\n', text, re.S)
    if not m:
        return text
    body = ""
    for k in range(n):
        e = m.group(0).replace(m.group(1), entity_id(0x900 + k))
        def moved(mm):
            x, y, z = (float(v) for v in mm.group(1).split())
            return f'<ECTransform position="{x - 500 - 300 * k:g} {y:g} {z + 450 + 150 * k:g}"'
        body += re.sub(r'<ECTransform position="([^"]+)"', moved, e, count=1)
    return add_entities(text, body)


def install(name, ak, atlas):
    sp = SPECS[name]
    gid, src = sp["gid"], os.path.join(CORPUS, sp["src"], "src", "tile")
    raw_tile = os.path.join(ak, "raw_data/terrain/tiles/battle/_assembly_kit", gid)
    if os.path.exists(raw_tile):
        sys.exit(f"{raw_tile} exists already")
    shutil.copytree(src, raw_tile)
    terry = glob.glob(os.path.join(raw_tile, "*.terry"))[0]
    t = open(terry, encoding="utf-8").read()
    if sp["vista"]:
        t = re.sub(r'vista="[^"]+"', f'vista="{sp["vista"]}"', t, count=1)
    if sp["climate"]:
        t = re.sub(r'climate_mask="[^"]*"', f'climate_mask="{sp["climate"]}"', t, count=1)
    open(terry, "w", encoding="utf-8", newline="").write(t)
    paint_blend(glob.glob(os.path.join(raw_tile, "*.blend.*.tif"))[0], sp["paint"])
    layer = [f for f in glob.glob(os.path.join(raw_tile, "*.layer")) if not f.endswith("output.layer")][0]
    text = open(layer, encoding="utf-8").read()
    body = "".join(tree(0x100 + k, key, x, z) for k, (key, x, z) in enumerate(sp["trees"]))
    body += "".join(prefab_ref(0x200 + k, key, x, z, yaw) for k, (_, key, x, z, yaw) in enumerate(sp["prefabs"]))
    if body:
        text = add_entities(text, body)
    for k, (rel, off) in enumerate(sp["inline"]):
        text = inline_prefab(ak, rel, off, text, k + 1)
    text = extra_rivers(text, sp["rivers"])
    open(layer, "w", encoding="utf-8", newline="").write(text)

    # Terry-save inputs, produced natively (byte-identical to Terry on round 1), then copied into the kit
    tmp = os.path.join(CORPUS, "_round2", "terry_save", gid)
    shutil.rmtree(tmp, ignore_errors=True)
    r = subprocess.run([atlas, "build-battle", ak, gid, "--out", tmp, "--only", "terry_save"], capture_output=True, text=True)
    print(r.stdout[-2000:], r.stderr[-2000:])
    ts = os.path.join(tmp, "terry_save")
    if not os.path.isdir(ts):
        sys.exit("terry_save step produced nothing")
    for tree_name in ("raw_data", "working_data"):
        s = os.path.join(ts, tree_name)
        for root, _, files in os.walk(s):
            for f in files:
                d = os.path.join(ak, tree_name, os.path.relpath(os.path.join(root, f), s))
                if os.path.exists(d):
                    sys.exit(f"refusing to overwrite {d}")
                os.makedirs(os.path.dirname(d), exist_ok=True)
                shutil.copy2(os.path.join(root, f), d)
    print(f"installed {name} = {gid} from {sp['src']}")


def remove(name, ak):
    gid = SPECS[name]["gid"]
    for rel in ("raw_data/terrain/tiles/battle/_assembly_kit", "raw_data/terrain/battles",
                "working_data/terrain/tiles/battle/_assembly_kit", "working_data/terrain/battles"):
        shutil.rmtree(os.path.join(ak, rel, gid), ignore_errors=True)
    for f in glob.glob(os.path.join(ak, "working_data/terrain/tiles/battle/_tile_database/TILES", f"_assembly_kit_{gid}.*")):
        os.remove(f)
    print("removed", name, gid)


if __name__ == "__main__":
    name, ak, what = sys.argv[1:4]
    atlas = sys.argv[sys.argv.index("--atlas") + 1] if "--atlas" in sys.argv else ATLAS
    install(name, ak, atlas) if what == "install" else remove(name, ak)
