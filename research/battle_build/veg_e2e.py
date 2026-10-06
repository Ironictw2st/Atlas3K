"""End to end from sources only (vegetation XMLs + the tile project's .terry, blend and height TIFs, layers): compile,
generate, tree list; checked against a Frida dump's instances and BOB's tree list files.
usage: veg_e2e.py <corpus project dir> <veg xml folder> [frida label]"""
import glob, math, os, re, sys
import numpy as np
import tifffile
import veg_compile as C
import veg_proc_proto as P
import veg_treelist as T

F = np.float32


def blend_floats(path):
    """TerrainMap Blend8 composite: channels 1..7 = u8 * (1/255); channel 0 = c0 + (1 - sum of all eight) summed in
    float in channel order (the remainder goes to the base channel)."""
    b = tifffile.imread(path)
    m = (b.astype(F) * F(1 / 255)).astype(F)
    acc = np.zeros(b.shape[:2], F)
    for c in range(8):
        acc = (acc + m[..., c]).astype(F)
    out = m.copy()
    out[..., 0] = (m[..., 0] + (F(1) - acc).astype(F)).astype(F)
    return out


def tree_items(insts, objs):
    items = []
    for oi, x, z, sc, rot in insts:
        o = objs[oi]
        if o.type == 1 and o.model:
            key = ("BattleTerrain/vegetation/" + o.model + ".rigid_model_v2").replace("\\", "/")
            items.append((key, x, F(0.0), z, sc, T.rot_byte(rot), False))
    return items


def hand_placed(src_tile):
    items = []
    for layer in glob.glob(os.path.join(src_tile, "*.layer")):
        t = open(layer, encoding="utf-8").read()
        for m in re.finditer(r'<ECVegetation key="([^"]+)"/>\s*<ECTransform position="([^"]+)" rotation="([^"]+)" '
                             r'scale="([^"]+)"', t):
            x, y, z = (F(v) for v in m.group(2).split())
            ry = F(m.group(3).split()[1])
            sc = F(m.group(4).split()[0])
            items.append(("BattleTerrain/vegetation/" + m.group(1) + ".rigid_model_v2", x, y, z, sc,
                          T.rot_byte(float(ry) * math.pi / 180), False))
    return items


if __name__ == "__main__":
    proj, folder = sys.argv[1:3]
    label = sys.argv[3] if len(sys.argv) > 3 else None
    src = os.path.join(proj, "src", "tile")
    terry = glob.glob(os.path.join(src, "*.terry"))[0]
    tex, climates, seed = C.terry_info(terry)
    gp = C.load(folder)
    height = tifffile.imread(glob.glob(os.path.join(src, "*.height.*.tif"))[0]).astype(F)
    blend = blend_floats(glob.glob(os.path.join(src, "*.blend.*.tif"))[0])
    calls = None
    if label:
        from veg_dump import dump
        calls = dump(label)
    order = [c for c in C.CLIMATE_ORDER if c in climates]
    for k, climate in enumerate(order):
        hdr, groups, objects, objs = C.compile_tile(gp, climate, tex)
        comp = P.Compiled.__new__(P.Compiled)
        for key, v in hdr.items():
            setattr(comp, key, v)
        comp.set_tables(groups, objects, [(o.size_low, o.size_range) for o in objs])
        if calls is not None:
            d = calls[k]
            print(climate, "height", np.array_equal(height, d["height"]), "blend", np.array_equal(blend, d["blend"]))
        g = P.Gen(None, compiled=comp, height=height, blend=blend, seed=seed)
        passes = g.run()
        if calls is not None:
            for p, out in enumerate(passes):
                P.compare(out, calls[k]["instances"][p], f"{climate} pass {p}")
        items = [it for out in passes for it in tree_items(out, objs)] + hand_placed(src)
        lst = T.build(items)
        ref = os.path.join(proj, "bob_run1", "tile", f"{climate}.tree_list")
        if os.path.exists(ref + ".bin"):
            print(climate, "tree_list.bin", T.to_bin(lst) == open(ref + ".bin", "rb").read(),
                  "xml", T.to_xml(lst) == open(ref + ".xml", encoding="utf-8", newline="").read())
        else:
            print(climate, "no BOB tree list;", len(items), "trees")
