#!/usr/bin/env python3
"""Assemble the 3k_guandu_map assembly-kit terrain project from the vanilla AK project + the cropped/scaled rasters.

World mapping (same as the hex/raster crop):  new = (old - origin) * scale, per axis,
  x: origin = COL0*0.668, scale = NW/CW      z: origin = ROW0*0.772, scale = NH/CH
- ECTransform positions are absolute -> mapped; entities landing outside the new world are dropped.
- Prop/decal/VFX sizes, point clouds (relative offsets) and light radii are kept: objects stay life-size.
- River splines (relative points) are scaled per axis, width scaled, then clipped to the longest run inside the world.
- Polylines (absolute points, entity at origin) are mapped; kept only if their centroid is inside.
- BOB-generated river meshes (model_path terrain/campaigns/<map>/models/...) are dropped; BOB rebuilds them.
- Logical associations lose references to dropped entities.
"""
import os, re, shutil, sys, glob
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from crop_scale_map_hex import COL0, COL1, ROW0, ROW1
from crop_scale_terrain import NW, NH, NWW, NWH, CW, CH, FULL, HALF, QUARTER

SRC_DIR, SRC_NAME = r"C:/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/assembly_kit/raw_data/terrain/campaigns/3k_dlc07_main_map", "3k_dlc07_main_map"  # the project Terry loads
RAST = os.path.join(HERE, "terrain")
NAME = "3k_guandu_map"
OUT = os.path.join(HERE, "ak", NAME)
OX, SX = COL0 * 0.668, NW / CW
OZ, SZ = ROW0 * 0.772, NH / CH

def mx(x): return (x - OX) * SX
def mz(z): return (z - OZ) * SZ
def inside(x, z): return 0 <= x <= NWW and 0 <= z <= NWH
def f(v): return repr(float(f"{v:.7g}")).removesuffix(".0") if abs(v) >= 1e-9 else "0"

ENT = re.compile(r"(\s*)<entity id=\"([0-9a-f]+)\".*?</entity>", re.S)
POS = re.compile(r'(<ECTransform position=")([^"]*)(")')

def do_river(e):
    m = POS.search(e); px, py, pz = map(float, m.group(2).split())
    pts = list(re.finditer(r'<point position="([^"]*)" tangent_in="([^"]*)" tangent_out="([^"]*)" width="([^"]*)"', e))
    absn = []
    for p in pts:
        rx, ry, rz = map(float, p.group(1).split(","))
        absn.append((mx(px + rx), py + ry, mz(pz + rz)))
    runs, cur = [], []
    for i, (x, y, z) in enumerate(absn):
        if inside(x, z): cur.append(i)
        elif cur: runs.append(cur); cur = []
    if cur: runs.append(cur)
    if not runs: return None
    keep = max(runs, key=len)
    if len(keep) < 2: return None
    ox, oy, oz = absn[keep[0]]
    wscale = (SX + SZ) / 2
    lines = e.split("\n"); out = []; idx = 0
    for line in lines:
        pm = re.search(r'<point position="([^"]*)" tangent_in="([^"]*)" tangent_out="([^"]*)" width="([^"]*)"', line)
        if pm:
            i = idx; idx += 1
            if i not in keep: continue
            x, y, z = absn[i]
            def tg(v):
                a, b, c = map(float, v.split(",")); return f"{f(a*SX)},{f(b)},{f(c*SZ)}"
            line = line.replace(pm.group(0), f'<point position="{f(x-ox)},{f(y-oy)},{f(z-oz)}" tangent_in="{tg(pm.group(2))}" '
                                f'tangent_out="{tg(pm.group(3))}" width="{f(float(pm.group(4))*wscale)}"')
        out.append(line)
    e = "\n".join(out)
    return POS.sub(lambda m: f'{m.group(1)}{f(ox)} {f(oy)} {f(oz)}{m.group(3)}', e, count=1)

def do_entity(e, stats):
    if "<ECTransform" not in e: return e                       # sub-layers etc.
    if re.search(r'model_path="terrain/campaigns/[^"]*/models/', e, re.I): stats["bob_mesh"] += 1; return None
    if "<ECRiverSpline" in e:
        r = do_river(e); stats["river" if r else "river_dropped"] += 1; return r
    if "<ECPolyline" in e:
        pts = [(float(a), float(b)) for a, b in re.findall(r'<point x="([^"]*)" y="([^"]*)"/>', e)]
        cx, cz = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
        if not inside(mx(cx), mz(cz)): stats["dropped"] += 1; return None
        stats["kept"] += 1
        return re.sub(r'<point x="([^"]*)" y="([^"]*)"/>', lambda m: f'<point x="{f(mx(float(m.group(1))))}" y="{f(mz(float(m.group(2))))}"/>', e)
    m = POS.search(e); x, y, z = m.group(2).split()
    nx, nz = mx(float(x)), mz(float(z))
    if not inside(nx, nz): stats["dropped"] += 1; return None
    stats["kept"] += 1
    return POS.sub(lambda m: f'{m.group(1)}{f(nx)} {y} {f(nz)}{m.group(3)}', e, count=1)

def do_layer(text, stats):
    dropped = set()
    def rep(m):
        r = do_entity(m.group(0), stats)
        if r is None: dropped.add(m.group(2)); return ""
        return r
    text = ENT.sub(rep, text)
    text = re.sub(r'\s*<to id="([0-9a-f]+)"/>', lambda m: "" if m.group(1) in dropped else m.group(0), text)
    text = re.sub(r'\s*<from id="[0-9a-f]+">\s*</from>', "", text)
    return text

def read_caime_tilemap(path):
    """CAIME's 'Baseline Tilemap image' is written as an uncompressed colour-mapped TGA (256 x 32-bit BGRA palette)
    whatever the file extension; decode it to RGBA."""
    import numpy as np, struct
    d = open(path, "rb").read()
    idlen, cmtype, imtype, cmfirst, cmlen, cmbits, _, _, w, h, depth, desc = struct.unpack_from("<BBBHHBHHHHBB", d, 0)
    assert (cmtype, imtype, cmbits, depth) == (1, 1, 32, 8), "unexpected TGA layout"
    p = 18 + idlen
    pal = np.frombuffer(d, np.uint8, cmlen * 4, p).reshape(cmlen, 4)[:, [2, 1, 0, 3]]   # BGRA -> RGBA
    idx = np.frombuffer(d, np.uint8, w * h, p + cmlen * 4).reshape(h, w)
    if not desc & 0x20: idx = idx[::-1]                                                  # bottom-left origin
    return Image.fromarray(pal[idx - cmfirst], "RGBA")


def main():
    if os.path.exists(OUT): shutil.rmtree(OUT)
    os.makedirs(OUT)
    stats = {k: 0 for k in ("kept", "dropped", "river", "river_dropped", "bob_mesh")}
    layers = glob.glob(os.path.join(SRC_DIR, f"{SRC_NAME}.*.layer"))
    for p in layers:
        t = open(p, encoding="utf-8").read()
        open(os.path.join(OUT, os.path.basename(p).replace(SRC_NAME, NAME)), "w", encoding="utf-8", newline="").write(do_layer(t, stats))
    # rasters (AK file names re-prefixed)
    for fn in os.listdir(RAST):
        shutil.copy2(os.path.join(RAST, fn), os.path.join(OUT, fn.replace(SRC_NAME, NAME)))
    # climate naming mirrors the vanilla folder's current state (climate_map.png full-res, climate_map_g.png quarter)
    full_is_main = Image.open(os.path.join(SRC_DIR, "climate_map.png")).size[0] == 7136
    if full_is_main:
        a, b = os.path.join(OUT, "climate_map.png"), os.path.join(OUT, "climate_map_g.png")
        os.replace(a, a + ".tmp"); os.replace(b, a); os.replace(a + ".tmp", b)
    shutil.copy2(os.path.join(SRC_DIR, "climate_change.py"), OUT)
    # tile map: CAIME's Tools > Export > Baseline Tilemap of the guandu map.hex (RGBA like vanilla's);
    # falls back to a nearest crop/scale of vanilla's if it has not been exported yet
    rebuilt_tm = os.path.join(HERE, "tile_map_rebuilt.png")     # build_tilemap.py: from the vanilla tile map
    caime_tm = os.path.join(HERE, "tile_map_caime.png")
    if os.path.exists(rebuilt_tm):
        tm = Image.open(rebuilt_tm); assert tm.size == QUARTER, (tm.size, QUARTER)
        tm.save(os.path.join(OUT, "tile_map.png"))
    elif os.path.exists(caime_tm):
        tm = read_caime_tilemap(caime_tm)
        assert tm.size == QUARTER, (tm.size, QUARTER)
        tm.save(os.path.join(OUT, "tile_map.png"))
    else:
        from crop_scale_terrain import src_coords, resample_nearest
        import numpy as np
        tm = Image.open(os.path.join(SRC_DIR, "tile_map.png")); w, h = tm.size
        arr = resample_nearest(np.array(tm), src_coords(QUARTER[0], NWW, 595.0999755859375, w, "x"), src_coords(QUARTER[1], NWH, 541.7861938476562, h, "z"))
        Image.fromarray(arr, tm.mode).save(os.path.join(OUT, "tile_map.png"))
        print("tile_map.png: placeholder (no CAIME export found)")
    # project file
    t = open(os.path.join(SRC_DIR, f"{SRC_NAME}.terry"), encoding="utf-8").read()
    t = t.replace(f"terrain/campaigns/{SRC_NAME}/", f"terrain/campaigns/{NAME}/")
    sizes = {"BlendCampaign": FULL, "LowFrequencyHeight": FULL, "LowFrequencyHeightSea": HALF, "CampaignTree": QUARTER}
    for typ, (w, h) in sizes.items():
        t, n = re.subn(rf'(type="{typ}" size=")\d+x\d+(")', rf"\g<1>{w}x{h}\g<2>", t); assert n == 1, typ
    open(os.path.join(OUT, f"{NAME}.terry"), "w", encoding="utf-8", newline="").write(t)
    # sanity: every raster matches its declared size
    for typ, (w, h) in sizes.items():
        lid = re.search(rf'type="{typ}" size="[^"]*" id="[0-9a-f]+"/>\s*<pc type="QTU::TerrainMapLayer">\s*<data id="([0-9a-f]+)"', t).group(1)
        fn = [x for x in os.listdir(OUT) if lid in x][0]
        assert Image.open(os.path.join(OUT, fn)).size == (w, h), (fn, Image.open(os.path.join(OUT, fn)).size, (w, h))
    print(f"{len(layers)} layers -> {OUT}\n{stats}")

if __name__ == "__main__":
    main()
