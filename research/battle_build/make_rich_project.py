"""Create the corpus' 'rich' battle project: a COPY of a kit battle tile project under a new GUID, with the map-level
raw folder Terry writes on save (vista copy + explicit_tiles.txt), the Terry-written working_data inputs (rules.bob,
tile database entry) and extra ECPrefab entities (capture-point tower, default deployment zones).

usage: make_rich_project.py <src corpus project dir> <kit root> <new guid> [--remove]
  src corpus project dir: e.g. Z:/Claude/BattleMaps/out/battle_parity/dfe064a6_..., using its src/tile and bob_run1/tile_db
  --remove: delete the project from the kit again (raw + working + tile db entry).
The user's own projects are never touched.
"""
import glob, os, re, shutil, sys

SRC, AK, GID = sys.argv[1:4]
raw_tile = os.path.join(AK, "raw_data/terrain/tiles/battle/_assembly_kit", GID)
raw_map = os.path.join(AK, "raw_data/terrain/battles", GID)
wk_tile = os.path.join(AK, "working_data/terrain/tiles/battle/_assembly_kit", GID)
wk_map = os.path.join(AK, "working_data/terrain/battles", GID)
tdb = os.path.join(AK, "working_data/terrain/tiles/battle/_tile_database/TILES")
if "--remove" in sys.argv:
    for d in (raw_tile, raw_map, wk_tile, wk_map):
        shutil.rmtree(d, ignore_errors=True)
    for f in glob.glob(os.path.join(tdb, f"_assembly_kit_{GID}.*")):
        os.remove(f)
    print("removed", GID); sys.exit()
for d in (raw_tile, raw_map, wk_tile, wk_map):
    if os.path.exists(d):
        sys.exit(f"{d} exists already")
old = os.path.basename(SRC.rstrip("/\\"))
shutil.copytree(os.path.join(SRC, "src", "tile"), raw_tile)
terry = glob.glob(os.path.join(raw_tile, "*.terry"))[0]
vista = re.search(r'vista="([^"]+)"', open(terry, encoding="utf-8").read()).group(1)

# extra prefabs, appended to the tile's layer
EXTRA = [("1991ffff0000101", "3k_main_han_tower_freestanding_and_capture_point_01", "900 0 1100"),
         ("1991ffff0000102", "deploy_land_normal_1024x1024_north", "1024 0 1024")]
layer = glob.glob(os.path.join(raw_tile, "*.layer"))[0]
text = open(layer, encoding="utf-8").read()
ents = "".join(f"""    <entity id="{i}">
      <ECPrefab key="{k}" turn_buildings_into_props="false"/>
      <ECMeshRenderSettings inherit_from_parent="false" cast_shadow="true" alpha="1" tint_colour="255 255 255 255" set_tint_colour_from_colour_overlay="false" faction_colour="255 255 255 255"/>
      <ECTransform position="{p}" rotation="0 0 0" scale="1 1 1" pivot="0 0 0"/>
      <ECTerrainClamp active="true" clamp_to_sea_level="false" terrain_oriented="false"/>
    </entity>
""" for i, k, p in EXTRA)
text = text.replace("  </entities>", ents + "  </entities>", 1)

# the same two prefabs also INLINED (their entities + Logical associations copied into the layer, moved by OFFSET),
# so capture locations and deployment zones land in the tile's own bmd_data rather than behind a prefab reference
INLINE = ["art/prefabs/battle/main/settlement/towers/3k_main_han_tower_freestanding_and_capture_point_01.15d18a232c3aea4.layer",
          "art/prefabs/battle/logic/default_deployment/deploy_land_normal_1024x1024_north.150f6c42c43bf29.layer"]
OFFSET = (1024.0, 1024.0)


def moved(m):
    x, y, z = (float(v) for v in m.group(1).split())
    return f'position="{x + OFFSET[0]:g} {y:g} {z + OFFSET[1]:g}"'


for rel in INLINE:
    pl = open(os.path.join(AK, "raw_data", rel.replace("/", os.sep)), encoding="utf-8").read()
    body = pl.split("<entities>", 1)[1].split("</entities>", 1)[0]
    body = re.sub(r'(<ECTransform )position="([^"]+)"', lambda m: m.group(1) + moved(re.match(r"(.*)", m.group(2))), body)
    logical = re.search(r"<Logical>(.*?)</Logical>", pl, re.S)
    text = text.replace("  </entities>", body.strip("\n") + "\n  </entities>", 1)
    if logical and logical.group(1).strip():
        if "<Logical/>" in text:
            text = text.replace("<Logical/>", "<Logical>" + logical.group(1) + "</Logical>", 1)
        else:
            text = text.replace("</Logical>", logical.group(1).strip("\n") + "\n    </Logical>", 1)
open(layer, "w", encoding="utf-8", newline="").write(text)

# map-level raw folder: what Terry writes on save for a user map (vista copy + explicit tile in the middle)
vdir = os.path.join(AK, "raw_data", vista.replace("/", os.sep))
os.makedirs(raw_map)
for f in ("tile_map.png", "climate_map.png", "lf_heights.tif", "lf_sea_heights.tif"):
    shutil.copy2(os.path.join(vdir, f), raw_map)
with open(os.path.join(raw_map, "explicit_tiles.txt"), "w", newline="\r\n") as f:
    f.write(f"28,28,terrain/tiles/battle/_assembly_kit/{GID},0\n")

# Terry-written working_data inputs
rules = f"[Pack]\n\tBasePath = /\n\tPackFile = <retail>/data/test_map_{GID}.pack\n\tPackType = mod"
for d in (wk_tile, wk_map):
    os.makedirs(d)
    open(os.path.join(d, "rules.bob"), "w", newline="").write(rules.replace("\n", "\r\n"))
for f in glob.glob(os.path.join(SRC, "bob_run1", "tile_db", "*")):
    data = open(f, "rb").read().replace(old.encode(), GID.encode())
    open(os.path.join(tdb, os.path.basename(f).replace(old, GID)), "wb").write(data)
print(f"created {GID} from {old}: vista {vista}, +{len(EXTRA)} prefabs")
