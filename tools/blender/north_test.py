"""Blender 4.4 headless: the North polish test scene + one custom mountain-range prop exported as RMV2 v7.

Run:  blender.exe -b --python tools/blender/north_test.py -- <research/main190 dir>
Needs the io_scene_rmv2 extension (installed in Blender 4.4 user_default) and korea_ref/north_test_data.npz
(north_test_prep.py) + vanilla models extracted to korea_ref/models (model_radius.py step).

Writes (korea_ref/):
  north_test.blend                      the scene: terrain patch (biome-coloured), tree placeholders, the custom ridge
                                        at its site, a vanilla cold_peak_2 beside it for scale
  custom/north_range_test.rigid_model_v2 the custom prop (vanilla cold_peak_2's material / textures, our DEM ridge mesh)
Axes: game (x east, y up, z north) -> Blender (-x, -z, y), as io_scene_rmv2 converts."""
import math, os, sys
import bpy
import numpy as np

ROOT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else r"Z:/Claude/TerryClone/research/main190"
KR = os.path.join(ROOT, "korea_ref")
MODELS = os.path.join(KR, "models")
PEAK_DIR = os.path.join(MODELS, "rigidmodels", "campaign", "mountains", "cold")
OUT = os.path.join(KR, "custom"); os.makedirs(OUT, exist_ok=True)
EXAG = 2.2          # the DEM ridge is gentle at map scale: exaggerate like CA's mountain props
NAME = "north_range_test"


def g2b(x, y, z): return (-x, -z, y)


def enable_addon():
    for mod in ("bl_ext.user_default.io_scene_rmv2", "io_scene_rmv2"):
        try:
            bpy.ops.preferences.addon_enable(module=mod); return mod
        except Exception: pass
    raise SystemExit("io_scene_rmv2 not available")


def import_peak(name="cold_peak_2.rigid_model_v2"):
    before = set(bpy.data.collections.keys())
    bpy.ops.import_scene.rmv2(directory=PEAK_DIR + os.sep, files=[{"name": name}], import_all_lods=False,
                              build_materials=True, texture_root=MODELS)
    new = [bpy.data.collections[k] for k in bpy.data.collections.keys() if k not in before]
    root = next(c for c in new if c.rmv2.is_rmv2_root)
    return root


def lod0_meshes(root):
    lod = next((c for c in root.children if c.name.endswith("_lod0")), root)
    return lod, [o for o in lod.objects if o.type == "MESH"]


def grid_mesh(name, xs, zs, ys, uv_scale=None, cols=None, keep=None):
    """Mesh from a (rows, cols) grid of game-space points; keep: (rows, cols) bool, faces need one kept corner."""
    R, C = ys.shape
    verts = [g2b(float(xs[r, c]), float(ys[r, c]), float(zs[r, c])) for r in range(R) for c in range(C)]
    faces = [(r * C + c, r * C + c + 1, (r + 1) * C + c + 1, (r + 1) * C + c) for r in range(R - 1) for c in range(C - 1)
             if keep is None or keep[r, c] or keep[r, c + 1] or keep[r + 1, c] or keep[r + 1, c + 1]]
    me = bpy.data.meshes.new(name); me.from_pydata(verts, [], faces)
    if keep is not None:                                            # drop the unused grid vertices
        import bmesh
        bm = bmesh.new(); bm.from_mesh(me)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
        bm.to_mesh(me); bm.free()
    me.update()
    if uv_scale:
        uv = me.uv_layers.new(name="UVMap")
        for poly in me.polygons:
            for li in poly.loop_indices:
                v = me.vertices[me.loops[li].vertex_index].co
                uv.data[li].uv = (v.x * uv_scale, v.y * uv_scale)
    if cols is not None:
        ca = me.color_attributes.new("biome", "BYTE_COLOR", "POINT")
        flat = cols.reshape(-1, 3)
        for i, c in enumerate(flat): ca.data[i].color = (c[0] / 255, c[1] / 255, c[2] / 255, 1.0)
    return me


def main():
    D = np.load(os.path.join(KR, "north_test_data.npz"))
    hx, hz = float(D["hx"]), float(D["hz"])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    enable_addon()
    sx, sz, sy = (float(v) for v in D["site"])

    # ---- 1. the custom prop: vanilla cold_peak_2 imported for its material, its mesh replaced by our DEM ridge
    root = import_peak(); root.name = NAME
    lod, meshes = lod0_meshes(root)
    keep = max(meshes, key=lambda o: len(o.data.vertices))
    for o in meshes:
        if o is not keep: bpy.data.objects.remove(o, do_unlink=True)
    ridge = D["ridge"].astype(float); ox, oz = (float(v) for v in D["ridge_origin"])
    R, C = ridge.shape
    rr, cc = np.mgrid[0:R, 0:C]
    gx = ox + cc * hx; gz = oz + rr * hz + ((cc + int(round(ox / hx))) & 1) * hz / 2
    lx, lz = gx - sx, gz - sz
    base = np.percentile(ridge, 20)
    rad = np.hypot(lx, lz); rmax = rad.max() * 0.7
    fall = np.clip(1 - (rad / rmax) ** 2, 0, 1) ** 1.5                 # meets the ground at the rim
    ly = np.maximum(ridge - base, 0) * EXAG * fall
    ly = ly - 0.15 * (fall == 0)                                    # the rim tucks just under the ground
    me = grid_mesh(NAME, lx, lz, ly, uv_scale=0.08, keep=fall > 0)
    old = keep.data
    for mat in old.materials: me.materials.append(mat)           # keep cold_peak_2's material / textures
    keep.data = me; keep.name = NAME
    if old.users == 0: bpy.data.meshes.remove(old)
    keep.location = (0, 0, 0)
    keep.rmv2.model_name = NAME[:31]
    # export the root collection
    lc = bpy.context.view_layer.layer_collection
    def find(lc_, col):
        if lc_.collection == col: return lc_
        for ch in lc_.children:
            r = find(ch, col)
            if r: return r
    bpy.context.view_layer.active_layer_collection = find(lc, root)
    out = os.path.join(OUT, NAME + ".rigid_model_v2")
    bpy.ops.export_scene.rmv2(filepath=out, source="COLLECTION", version="7", auto_lods=True, auto_lod_count=4,
                              apply_modifiers=True, high_precision=True, write_attach_points=False)
    print("exported", out, os.path.getsize(out) if os.path.exists(out) else "MISSING")
    # place it at its map site for the scene
    keep.location = g2b(sx, sy, sz)

    # ---- 2. the terrain patch + biome colours + tree placeholders
    T = D["terr"].astype(float); step = int(D["terr_step"]); tx, tz = (float(v) for v in D["terr_origin"])
    Rt, Ct = T.shape
    rr, cc = np.mgrid[0:Rt, 0:Ct]
    gx = tx + cc * step * hx; gz = tz + rr * step * hz
    pal = {0: (150, 145, 130), 1: (40, 92, 56), 2: (30, 74, 66), 3: (84, 140, 70), 4: (196, 196, 120)}
    B = D["biome"]; W = D["water"]
    cols = np.array([[pal[int(B[r, c])] if not W[r, c] else (70, 100, 150) for c in range(Ct)] for r in range(Rt)], float)
    terrain = bpy.data.objects.new("terrain_goguryeo", grid_mesh("terrain_goguryeo", gx, gz, np.where(W, -0.2, T), cols=cols))
    bpy.context.scene.collection.objects.link(terrain)
    # trees: a cone per forested sample (every 2nd terrain vertex in highland / taiga / mixed)
    rng = np.random.default_rng(4)
    tv, tf = [], []
    dens = {1: 0.8, 2: 0.75, 3: 0.5, 4: 0.05}
    for r in range(0, Rt):
        for c in range(0, Ct):
            b = int(B[r, c])
            if W[r, c] or b == 0 or rng.random() > dens.get(b, 0): continue
            x, z, y = gx[r, c] + rng.uniform(-0.5, 0.5), gz[r, c] + rng.uniform(-0.5, 0.5), T[r, c]
            hgt = 0.9 if b in (1, 2) else 0.7
            k = len(tv)
            for a in range(5):
                ang = a * 2 * math.pi / 5
                tv.append(g2b(x + 0.25 * math.cos(ang), y, z + 0.25 * math.sin(ang)))
            tv.append(g2b(x, y + hgt, z))
            for a in range(5): tf.append((k + a, k + (a + 1) % 5, k + 5))
    tm = bpy.data.meshes.new("tree_placeholders"); tm.from_pydata(tv, [], tf); tm.update()
    trees = bpy.data.objects.new("tree_placeholders", tm); bpy.context.scene.collection.objects.link(trees)

    # ---- 3. a vanilla cold_peak_2 beside the custom ridge, at the plan's scale (0.16), for comparison
    ref = import_peak(); ref.name = "vanilla_cold_peak_2_reference"
    _, rm = lod0_meshes(ref)
    for o in rm:
        o.scale = (0.16, 0.16, 0.16); o.location = g2b(sx + 22, sy, sz)
    # camera + light so the .blend opens on something sensible
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); bpy.context.scene.collection.objects.link(cam)
    cam.location = (-(sx), -(sz) - 70, sy + 55); cam.rotation_euler = (math.radians(55), 0, 0)
    bpy.context.scene.camera = cam
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); bpy.context.scene.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(40), 0, math.radians(30))
    blend = os.path.join(KR, "north_test.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    print("saved", blend, "trees", len(tf) // 5, "terrain", T.shape)


if __name__ == "__main__":
    main()
