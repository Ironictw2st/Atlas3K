"""terry-mcp: stdio MCP server for Atlas3K's native campaign-map build (the BOB replacement).

Every tool shells out to the Atlas3K CLI (src/Atlas3K.Cli), which rebuilds BOB's campaign outputs straight
from the assembly-kit sources, reading intermediate files from disk -- no BOB, no pack import between steps.

Steps (in BOB's order): rasters, tile_list, global_map, global_mesh, rivers, global_props, camera_heightmap, trees, lookup.
Steps whose algorithm is not reverse-engineered yet report status "blocked" with "not native yet"; run
`diagnose` to see which. Run `validate_tilemap` before any Tilemap run (BOB or native) to catch tile-map problems
up front; diagnose also lists its errors under tile_list. The bob MCP server is still available to produce reference output for those.

Prop editing (the *_prop* tools) works on the assembly kit's Terry layers, raw_data/terrain/campaigns/<map>/
<map>.<id>.layer, one layer per region. Edits change only the touched entities (the rest of each layer stays
byte-identical) and every batch can be undone.
- Coordinates are campaign world units: x west->east, z south->north, y up. Rotations are in degrees.
- NEVER GUESS a model path; take it from list_prop_models (or from an existing prop via list_props / get_prop).
- Season variants of one tree or rock are separate props at the same spot. Pass group=True to move, rotate, scale,
  tag, duplicate or delete them together.
- Mountain relief is made of props, and trees often stand on them. When moving, snap="relative" keeps an object's
  height above the terrain; snap="terrain" puts it on the ground.
- Recommended order: prop_checkpoint -> edits -> preview_props (look at it) -> rebuild_props. global_props.bin only
  changes when rebuild_props runs; prop_rollback undoes everything since a checkpoint.

Tile-map editing (the *_tiles* / tile_* tools) paints the kit's campaign tile_map.png hex by hex. Hexes are
[col, row], row 0 = south; tile sets are names from list_tile_sets (or "#rrggbb"). Each batch is validated on the
changed hexes: an edit that introduces a blocking issue is NOT written (allow_warnings / force override).
- Recommended order: tile_checkpoint -> paint/erase/draw/fill (dry_run first if unsure) -> preview_tiles ->
  simulate_tiles (BOB tile matching, ~2 min: holes in the edits?) -> build_step tile_list ->
  check_tile_holes -> build_step global_map, global_mesh.
- Recorded edits can be replayed with replay_tiles after a builder (caime_tilemap.py) regenerates the tile map.

Entity editing (the *entit* / *_layer* tools) is generic Terry editing: any entity type (Prop, Decal, VFX, PointLight,
SoundMarker, CompositeScene, River, Building, ...), any component and any field, in any Terry project -- the campaign
map by default, or any .terry via `project` (battle prefabs live under raw_data/art/prefabs/**.terry).
- Types and fields come from Terry's own entity_configuration.xml plus every .layer/.terry in the kit; call
  describe_entity_type before creating or setting fields. NEVER GUESS a field name or an asset path.
- Fields are addressed "ECComponent.field" (e.g. "ECMesh.model_path", "ECPointLight.radius"). Values are checked
  against the field's type; unknown fields are refused (Terry would drop them).
- Hierarchy: file layers (one .layer each) hold entities; inside a file, folder layers and tag layers (members export
  with the layer's meta tags) group them. Visibility/lock/active layer are per-user (.terry.user), as in Terry.
- For the campaign map, entity edits share one undo history with the prop tools (prop_undo == entity_undo there).

Prefabs (the *prefab* tools): a Prefab entity's ECPrefab.key names a prefab project (<key>.terry) in the database's
library -- raw_data/art/prefabs/battle (1300 kit prefabs) or raw_data/art/campaign/prefabs (empty in the kit; make_prefab
creates it). NEVER GUESS a key; take it from list_prefabs. Instances expand with overrides and nested prefabs; the
native campaign build (rebuild_props / global_props) flattens campaign prefab instances into global_props.bin, since the
game has no campaign prefab files for them to reference.

Game assets (the *asset* tools) are read from the vanilla packs, plus optional mod packs / loose folders: models
(.wsmodel -> .rigid_model_v2 + .material per part/LOD -> .dds), materials and textures. preview_asset renders a model
so you can SEE a prop before placing it; check_project_assets lists models a project uses that do not load.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile

from mcp.server.fastmcp import FastMCP, Image

PROJECT = os.environ.get("ATLAS3K_ROOT") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CLI_PROJECT = os.path.join(PROJECT, "src", "Atlas3K.Cli", "Atlas3K.Cli.csproj")
CLI_EXE = os.path.join(PROJECT, "src", "Atlas3K.Cli", "bin", "Release", "net9.0", "Atlas3K.Cli.exe")
KIT = r"C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\assembly_kit"

mcp = FastMCP("terry")


def _run(args: list[str], timeout: int = 3600) -> dict:
    if not os.path.exists(CLI_EXE):
        built = _build_cli()
        if built["exit_code"] != 0:
            return {"error": "Atlas3K CLI does not build", **built}
    proc = subprocess.run([CLI_EXE, *args], cwd=PROJECT, capture_output=True, text=True, timeout=timeout)
    result: dict = {"exit_code": proc.returncode}
    try:
        result["result"] = json.loads(proc.stdout)
    except json.JSONDecodeError:
        result["stdout"] = proc.stdout[-8000:]
    if proc.stderr.strip():
        result["log"] = proc.stderr[-8000:]
    return result


def _build_cli() -> dict:
    proc = subprocess.run(["dotnet", "build", CLI_PROJECT, "-c", "Release", "-v", "q", "-nologo"],
                          cwd=PROJECT, capture_output=True, text=True, timeout=900)
    return {"exit_code": proc.returncode, "output": proc.stdout[-6000:] + proc.stderr[-2000:]}


def _common(map_name: str | None, ak_root: str | None) -> list[str]:
    args = []
    if map_name:
        args += ["--map", map_name]
    if ak_root:
        args += ["--ak", ak_root]
    return args


def _target(out_dir: str | None, to_working_data: bool) -> list[str]:
    if to_working_data:
        return ["--out", os.path.join(KIT, "working_data")]
    return ["--out", out_dir] if out_dir else []


@mcp.tool()
def build_campaign(map_name: str = "3k_dlc07_main_map", steps: list[str] | None = None, out_dir: str | None = None,
                   to_working_data: bool = False, ak_root: str | None = None) -> dict:
    """Build a campaign map's compiled terrain natively (replaces BOB's campaign actions).

    map_name: assembly-kit map folder (raw_data/terrain/campaigns/<map>).
    steps: subset to run, e.g. ["rasters", "global_map"]; default = every native step. Selected steps run in
           dependency order, independent ones in parallel.
    out_dir: target root laid out like working_data (terrain/campaigns/<map>, campaign_maps/<map>);
             default output/compiled/<map>.
    to_working_data: write straight into the assembly kit's working_data (overwrites BOB's files there).
    Returns per-step status (ok / blocked / failed / skipped), timings, notes and the files written.
    """
    args = ["build-campaign", "--json", *_common(map_name, ak_root), *_target(out_dir, to_working_data)]
    if steps:
        args += ["--steps", ",".join(steps)]
    return _run(args)


@mcp.tool()
def build_step(step: str, map_name: str = "3k_dlc07_main_map", out_dir: str | None = None,
               to_working_data: bool = False, ak_root: str | None = None) -> dict:
    """Run one native build step (rasters, tile_list, global_map, global_mesh, rivers, global_props, camera_heightmap, trees, lookup)."""
    return build_campaign(map_name, [step], out_dir, to_working_data, ak_root)


@mcp.tool()
def build_project(project: str, segments: list[str] | None = None, steps: list[str] | None = None,
                  custom_steps: list[str] | None = None, out_dir: str | None = None, pack_output: str | None = None) -> dict:
    """Run an Atlas3K project's build (.atlas3k), exactly as the app's Build window does.

    project: path to the .atlas3k file (e.g. research/main190/main190.atlas3k).
    segments: subset of validate, compile, custom, pack, install; default = the project's enabled segments
              (pack / install only when the profile enables them).
    steps: native compile steps to run instead of the profile's.
    custom_steps: only these custom steps (by name), instead of every enabled one.
    out_dir / pack_output: override the profile's compile output folder / pack file (e.g. a scratch test).
    Returns the build report: per item (validate, compile:<step>, custom:<name>, pack, install) status
    (ok / warning / failed / blocked / skipped / cancelled), seconds, problems, notes; plus the log file path.
    """
    args = ["build", "--project", os.path.abspath(project), "--json"]
    if segments:
        args += ["--segments", ",".join(segments)]
    if steps:
        args += ["--steps", ",".join(steps)]
    if custom_steps:
        args += ["--custom", ",".join(custom_steps)]
    if out_dir:
        args += ["--out", out_dir]
    if pack_output:
        args += ["--pack-output", pack_output]
    return _run(args)


@mcp.tool()
def diagnose(map_name: str = "3k_dlc07_main_map", out_dir: str | None = None, to_working_data: bool = False,
             ak_root: str | None = None) -> dict:
    """Per-step readiness: which BOB action each step replaces, whether it is native yet, and missing inputs."""
    return _run(["diagnose-campaign", "--json", *_common(map_name, ak_root), *_target(out_dir, to_working_data)])


@mcp.tool()
def validate_tilemap(map_name: str = "3k_dlc07_main_map", tile_map: str | None = None, climate_dir: str | None = None,
                     simulate: bool = False, overlay: str | None = None, tilemap_only: bool = False,
                     ak_root: str | None = None) -> dict:
    """Pre-flight check of a campaign tile map BEFORE BOB's Terrain / Tilemap (or the native tile_list step).

    Checks: real PNG (not TGA), 2W x (2H+1) layout and black filler, hex width a multiple of 4, every colour a 3K
    tile set / tile / variation colour (CAIME's Attila colours flagged), tile sets CA never paints, climate map size and
    colours, .terry / lf TIF sizes, stale working_data lf maps, EmpireDesignData extents, rules.bob, one-hex-wide
    lines, coast ring, cliff ends, river starts / mouths, crossing layouts and 7-hex neighbourhoods CA's map never uses.
    tile_map: check a candidate file instead of <kit>/raw_data/terrain/campaigns/<map>/tile_map.png.
    simulate: also run the BOB tile-matching simulation and list the points that would get no tile.
    overlay: write a PNG of the tile map with error hexes red, warnings yellow, info cyan (look at it).
    tilemap_only: skip the kit checks (rules.bob, sizes, extents, lf maps).
    Findings carry severity (error / warning / info), a count and up to 200 [col, row] hexes (row 0 = south).
    exit_code 1 = errors.
    """
    args = ["validate-tilemap", "--json", *_common(map_name, ak_root)]
    if tile_map:
        args += ["--tilemap", tile_map]
    if climate_dir:
        args += ["--climate-dir", climate_dir]
    if overlay:
        args += ["--overlay", overlay]
    if simulate:
        args.append("--simulate")
    if tilemap_only:
        args.append("--tilemap-only")
    return _run(args)


@mcp.tool()
def parity_check(built_dir: str, reference_dir: str, mask_junk: bool = True, only_differences: bool = True) -> dict:
    """Byte-compare a native build against a reference tree (vanilla, or a BOB build) file by file.

    Paths are matched relative to each root, so pass matching levels, e.g.
    built_dir=<out>/terrain, reference_dir=Z:/Claude/TerryClone/Vanilla/Map/terrain.
    mask_junk ignores the .rigid_model_v2 header bytes BOB fills from uninitialised memory.
    """
    args = ["parity", built_dir, reference_dir, "--json"] + (["--mask-junk"] if mask_junk else [])
    result = _run(args)
    files = result.get("result")
    if isinstance(files, list):
        counts: dict[str, int] = {}
        for f in files:
            counts[f["status"]] = counts.get(f["status"], 0) + 1
        result["summary"] = counts
        if only_differences:
            result["result"] = [f for f in files if f["status"] != "identical"]
    return result


@mcp.tool()
def list_outputs(map_name: str = "3k_dlc07_main_map", out_dir: str | None = None, to_working_data: bool = False) -> dict:
    """List the files currently in a build target for a map, with sizes and modification times."""
    root = os.path.join(KIT, "working_data") if to_working_data else (
        out_dir or os.path.join(PROJECT, "output", "compiled", map_name))
    files = []
    for sub in (os.path.join("terrain", "campaigns", map_name), os.path.join("campaign_maps", map_name)):
        base = os.path.join(root, sub)
        for dirpath, _, names in os.walk(base):
            for n in names:
                p = os.path.join(dirpath, n)
                st = os.stat(p)
                files.append({"path": os.path.relpath(p, root), "bytes": st.st_size, "mtime": int(st.st_mtime)})
    return {"root": root, "count": len(files), "files": sorted(files, key=lambda f: f["path"])}


@mcp.tool()
def rebuild_tool() -> dict:
    """Recompile the Atlas3K CLI (Release) after source changes."""
    return _build_cli()



# ---------------------------------------------------------------- props (AK Terry layers)

def _props(command: str, map_name: str | None, ak_root: str | None, *args: str):
    result = _run([command, *_common(map_name, ak_root), *args], timeout=900)
    payload = result.get("result")
    if isinstance(payload, dict) and "error" in payload:
        return {"error": payload["error"], **({"log": result["log"]} if "log" in result else {})}
    return payload if payload is not None else result


def _csv(values) -> str:
    return ",".join(str(v) for v in values)


@mcp.tool()
def list_prop_layers(name_filter: str | None = None, map_name: str = "3k_dlc07_main_map", ak_root: str | None = None) -> dict:
    """List the map's region layers, with object counts per kind and the objects' world bounds [x0, z0, x1, z1].

    name_filter keeps only layers whose name contains it (e.g. "luoyang").
    """
    result = _props("props-layers", map_name, ak_root)
    if name_filter and isinstance(result.get("layers"), list):
        result["layers"] = [l for l in result["layers"] if name_filter.lower() in l["name"].lower()]
    return result


@mcp.tool()
def list_props(layer: str | None = None, kinds: list[str] | None = None, asset: str | None = None, tag: str | None = None,
               rect: list[float] | None = None, near: list[float] | None = None, limit: int = 200,
               map_name: str = "3k_dlc07_main_map", ak_root: str | None = None) -> dict:
    """Find objects in the layers. Returns id, layer, kind, asset, position, rotation, scale, tags and seasons.

    layer: a region/layer name or id (default: every layer).
    kinds: any of prop, decal, vfx, light, scene, sound, probe, poly, river (default: everything but tag layers).
    asset: substring of the model path / VFX / scene / sound key.
    tag: one export tag the object must carry (e.g. building_level_3, night).
    rect: [x0, z0, x1, z1] world rectangle. near: [x, z, radius] (results come nearest first).
    """
    args = ["--limit", str(limit)]
    if layer: args += ["--layer", layer]
    if kinds: args += ["--kind", _csv(kinds)]
    if asset: args += ["--asset", asset]
    if tag: args += ["--tag", tag]
    if rect: args += ["--rect", _csv(rect)]
    if near: args += ["--near", _csv(near)]
    return _props("props-list", map_name, ak_root, *args)


@mcp.tool()
def get_prop(id: str, layer: str | None = None, map_name: str = "3k_dlc07_main_map", ak_root: str | None = None) -> dict:
    """One object in full: its parsed fields, the terrain height under it (ground_y), and its raw layer XML."""
    return _props("props-get", map_name, ak_root, id, *(["--layer", layer] if layer else []))


@mcp.tool()
def list_prop_models(filter: str | None = None, kinds: list[str] | None = None, limit: int = 100,
                     map_name: str = "3k_dlc07_main_map", ak_root: str | None = None) -> dict:
    """Assets already used on the map (model paths, VFX, composite scenes...), most used first, each with its use
    count, mean scale and an example layer. The source of valid paths for add_props / set_prop_properties."""
    args = ["--limit", str(limit)]
    if filter: args += ["--filter", filter]
    if kinds: args += ["--kind", _csv(kinds)]
    return _props("props-models", map_name, ak_root, *args)


@mcp.tool()
def ground_height(points: list[list[float]], map_name: str = "3k_dlc07_main_map", ak_root: str | None = None):
    """Terrain height (world y) at [x, z] points, from the kit's height map. For a single point it also names the
    region layer an added prop there would go to."""
    return _props("props-ground", map_name, ak_root, "--at", _csv(v for p in points for v in p[:2]))


@mcp.tool()
def edit_props(ops: list[dict], label: str | None = None, map_name: str = "3k_dlc07_main_map",
               ak_root: str | None = None) -> dict:
    """Apply a batch of prop edits as one undo step. Nothing is written if any op fails.

    Ops ("id" or "ids"; "layer" is optional and speeds things up; "group": true includes co-located variants):
      {"op":"add", "model":..., "position":[x, y|null, z], "rotation":[rx,ry,rz], "scale": s | [sx,sy,sz],
       "layer":..., "tags":"a,b", "seasons":"season_summer,...", "decal":false, ...visibility flags}
         y null = terrain height; layer defaults to the region whose objects are nearest.
      {"op":"move", "ids":[...], "position":[x, y|null, z] | "by":[dx,dy,dz], "snap":"terrain"|"relative"}
         null components are kept.
      {"op":"rotate", "ids":[...], "rotation":[rx,ry,rz] | "by":[drx,dry,drz]}   (degrees; y is the heading)
      {"op":"scale", "ids":[...], "scale":[sx,sy,sz] | "factor": k}
      {"op":"set", "ids":[...], "model":..., "seasons":..., "attributes":{"ECComponent.attribute": "value"}}
      {"op":"tags", "ids":[...], "tags":"building_level_3,building_level_4"}   ("" = untagged)
      {"op":"duplicate", "ids":[...], "by":[dx,dy,dz], "snap":...}   returns the new ids
      {"op":"delete", "ids":[...]}
    Returns the batch's undo seq and each object's new state.
    """
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(ops, f)
        path = f.name
    try:
        return _props("props-edit", map_name, ak_root, "--ops", path, *(["--label", label] if label else []))
    finally:
        os.unlink(path)


def _ids_op(op: str, ids: list[str], group: bool, layer: str | None, **fields) -> dict:
    o = {"op": op, "ids": ids, **{k: v for k, v in fields.items() if v is not None}}
    if group: o["group"] = True
    if layer: o["layer"] = layer
    return o


@mcp.tool()
def add_props(props: list[dict], map_name: str = "3k_dlc07_main_map", ak_root: str | None = None) -> dict:
    """Add props: each {"model", "position":[x, y|null, z], optional "rotation", "scale", "layer", "tags", "seasons",
    "decal"}. Model paths must come from list_prop_models. y null = terrain height."""
    return edit_props([{"op": "add", **p} for p in props], None, map_name, ak_root)


@mcp.tool()
def move_props(ids: list[str], position: list | None = None, by: list[float] | None = None, snap: str | None = None,
               group: bool = False, layer: str | None = None, map_name: str = "3k_dlc07_main_map",
               ak_root: str | None = None) -> dict:
    """Move objects to an absolute position [x, y|null, z] (null = keep) or by an offset [dx, dy, dz].
    snap: "terrain" (onto the ground) or "relative" (keep the height above ground). group: also move co-located variants."""
    return edit_props([_ids_op("move", ids, group, layer, position=position, by=by, snap=snap)], None, map_name, ak_root)


@mcp.tool()
def transform_props(ids: list[str], rotation: list | None = None, rotate_by: list[float] | None = None,
                    scale: list | None = None, scale_factor: float | None = None, group: bool = False,
                    layer: str | None = None, map_name: str = "3k_dlc07_main_map", ak_root: str | None = None) -> dict:
    """Rotate (absolute [rx, ry, rz] degrees, null = keep, or rotate_by) and/or scale ([sx, sy, sz] or scale_factor)."""
    ops = []
    if rotation is not None or rotate_by is not None:
        ops.append(_ids_op("rotate", ids, group, layer, rotation=rotation, by=rotate_by))
    if scale is not None or scale_factor is not None:
        ops.append(_ids_op("scale", ids, group, layer, scale=scale, factor=scale_factor))
    if not ops:
        return {"error": "pass rotation, rotate_by, scale or scale_factor"}
    return edit_props(ops, None, map_name, ak_root)


@mcp.tool()
def set_prop_properties(ids: list[str], model: str | None = None, seasons: str | None = None, tags: str | None = None,
                        attributes: dict[str, str] | None = None, group: bool = False, layer: str | None = None,
                        map_name: str = "3k_dlc07_main_map", ak_root: str | None = None) -> dict:
    """Swap the model, set the season mask ("" = all seasons), set the export tags ("" = untagged), or set raw component
    attributes such as {"ECCampaignProperties.visible_in_unseen_shroud": "true", "ECMeshRenderSettings.cast_shadow": "false"}."""
    ops = []
    if model is not None or seasons is not None or attributes:
        ops.append(_ids_op("set", ids, group, layer, model=model, seasons=seasons, attributes=attributes))
    if tags is not None:
        ops.append(_ids_op("tags", ids, group, layer, tags=tags))
    if not ops:
        return {"error": "nothing to set"}
    return edit_props(ops, None, map_name, ak_root)


@mcp.tool()
def duplicate_props(ids: list[str], by: list[float], snap: str | None = None, group: bool = False,
                    layer: str | None = None, map_name: str = "3k_dlc07_main_map", ak_root: str | None = None) -> dict:
    """Copy objects (with their tags) offset by [dx, dy, dz]; returns the new ids."""
    return edit_props([_ids_op("duplicate", ids, group, layer, by=by, snap=snap)], None, map_name, ak_root)


@mcp.tool()
def delete_props(ids: list[str], group: bool = False, layer: str | None = None, map_name: str = "3k_dlc07_main_map",
                 ak_root: str | None = None) -> dict:
    """Delete objects; tag layers left empty are removed too."""
    return edit_props([_ids_op("delete", ids, group, layer)], None, map_name, ak_root)


@mcp.tool()
def prop_checkpoint(label: str, map_name: str = "3k_dlc07_main_map", ak_root: str | None = None) -> dict:
    """Name the current edit state so prop_rollback(label) can return to it."""
    return _props("props-checkpoint", map_name, ak_root, label)


@mcp.tool()
def prop_rollback(label: str, force: bool = False, map_name: str = "3k_dlc07_main_map", ak_root: str | None = None) -> dict:
    """Undo every prop edit made since checkpoint `label`. It refuses if a layer was changed outside these tools since;
    force=True overwrites anyway."""
    return _props("props-rollback", map_name, ak_root, label, *(["--force"] if force else []))


@mcp.tool()
def prop_undo(steps: int = 1, force: bool = False, map_name: str = "3k_dlc07_main_map", ak_root: str | None = None) -> dict:
    """Undo the last `steps` edit batches."""
    return _props("props-undo", map_name, ak_root, "--steps", str(steps), *(["--force"] if force else []))


@mcp.tool()
def prop_history(map_name: str = "3k_dlc07_main_map", ak_root: str | None = None) -> dict:
    """Edit batches so far (seq, time, label, files) and the named checkpoints."""
    return _props("props-history", map_name, ak_root)


@mcp.tool()
def preview_props(rect: list[float] | None = None, center: list[float] | None = None, size: float = 20,
                  width: int = 1024, highlight: list[str] | None = None, layer: str | None = None,
                  map_name: str = "3k_dlc07_main_map", ak_root: str | None = None):
    """Top-down PNG of a world area: hillshaded terrain, a labelled x/z grid, and objects as dots coloured by kind.
    Highlighted ids get a red ring and their id. Pass rect [x0, z0, x1, z1], or center [x, z] with size.
    Returns the image and its file path (give users the path)."""
    args = ["--width", str(width)]
    if rect: args += ["--rect", _csv(rect)]
    elif center: args += ["--center", _csv(center), "--size", str(size)]
    else: return {"error": "pass rect or center"}
    if highlight: args += ["--highlight", _csv(highlight)]
    if layer: args += ["--layer", layer]
    result = _props("props-preview", map_name, ak_root, *args)
    if "png" not in result:
        return result
    return [json.dumps(result), Image(path=result["png"])]


@mcp.tool()
def rebuild_props(map_name: str = "3k_dlc07_main_map", out_dir: str | None = None, to_working_data: bool = False,
                  camera_heightmap: bool = True, ak_root: str | None = None) -> dict:
    """Recompile global_props.bin from the edited layers. camera_heightmap also redoes the camera height map, which
    includes props. Runs the rasters step first if the target has no lf_height_map yet."""
    root = os.path.join(KIT, "working_data") if to_working_data else (
        out_dir or os.path.join(PROJECT, "output", "compiled", map_name))
    steps = ["global_props"] + (["camera_heightmap"] if camera_heightmap else [])
    if not os.path.exists(os.path.join(root, "terrain", "campaigns", map_name, "lf_height_map.compressed_map")):
        steps.insert(0, "rasters")
    return build_campaign(map_name, steps, out_dir, to_working_data, ak_root)


# ---------------------------------------------------------------- tiles (campaign tile_map.png)

def _tiles(command: str, map_name: str | None, ak_root: str | None, tile_map: str | None, *args: str):
    extra = ["--tilemap", tile_map] if tile_map else []
    result = _run([command, *_common(map_name, ak_root), *extra, *args], timeout=900)
    payload = result.get("result")
    if isinstance(payload, dict) and "error" in payload:
        return {"error": payload["error"], **({"log": result["log"]} if "log" in result else {})}
    return payload if payload is not None else result


def _with_png(result):
    if isinstance(result, dict) and result.get("png") and os.path.exists(result["png"]):
        return [json.dumps(result), Image(path=result["png"])]
    return result


def _area(hexes, circle, rect, polygon) -> dict:
    if hexes: return {"hexes": hexes}
    if circle: return {"circle": circle}
    if rect: return {"rect": rect}
    if polygon: return {"polygon": polygon}
    raise ValueError("pass hexes, circle, rect or polygon")


@mcp.tool()
def list_tile_sets(map_name: str = "3k_dlc07_main_map", tile_map: str | None = None, ak_root: str | None = None) -> dict:
    """The tile sets you can paint (name, colour, area or line/coast kind, hexes on the map, tiles in the database),
    the hex grid size, and any colours on the map that are no tile set. tile_map: a copy instead of the kit's file."""
    return _tiles("tiles-info", map_name, ak_root, tile_map)


@mcp.tool()
def get_tiles(hexes: list[list[int]] | None = None, world: list[list[float]] | None = None, rect: list[int] | None = None,
              limit: int = 400, map_name: str = "3k_dlc07_main_map", tile_map: str | None = None,
              ak_root: str | None = None) -> dict:
    """Tile set, colour and world [x, z] of hexes: hexes [[col, row], ...], world [[x, z], ...] (campaign world units,
    converted to the hex under them) or rect [c0, r0, c1, r1]."""
    args = ["--limit", str(limit)]
    if hexes: args += ["--hexes", _csv(v for h in hexes for v in h[:2])]
    if world: args += ["--world", _csv(v for p in world for v in p[:2])]
    if rect: args += ["--rect", _csv(rect)]
    return _tiles("tiles-get", map_name, ak_root, tile_map, *args)


@mcp.tool()
def edit_tiles(ops: list[dict], label: str | None = None, dry_run: bool = False, allow_warnings: bool = False,
               force: bool = False, preview: bool = True, map_name: str = "3k_dlc07_main_map",
               tile_map: str | None = None, ak_root: str | None = None):
    """Apply a batch of tile-map edits as one undo step, validated first. Nothing is written if any op fails or the
    edit introduces a blocking issue (new errors, and new rule warnings such as thick lines, unseen coast/river
    patterns or bad river ends: likely holes). allow_warnings writes despite warnings; force writes regardless.

    Areas (any op): "hexes": [[c,r],...] | "circle": [c, r, radius] | "rect": [c0,r0,c1,r1] | "polygon": [[c,r],...]
    Ops:
      {"op":"paint", "set": "mountains_temperate", area}
      {"op":"erase", area, "to"?: set}        remove tiles: hexes go back to the surrounding land (or sea)
      {"op":"line", "set": "river", "points": [[c,r],...], "width"?: 1}   connected one-hex-wide path
      {"op":"fill", "set":..., "at": [c,r], "max"?: 20000}               flood fill of a same-colour area
      {"op":"replace", "from": set, "to": set, area | "all": true}
    Rivers need a river_start hex at the source and must end in the sea (river_mouth) or another river.
    Returns written, seq, changed hexes, their bounds, new_issues (with blocking flags) and a preview image of the
    edited area (white = changed, red = blocking issue, orange = warning).
    """
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(ops, f)
        path = f.name
    try:
        args = ["--ops", path]
        if label: args += ["--label", label]
        if dry_run: args.append("--dry-run")
        if allow_warnings: args.append("--allow-warnings")
        if force: args.append("--force")
        if preview: args.append("--preview")
        return _with_png(_tiles("tiles-edit", map_name, ak_root, tile_map, *args))
    finally:
        os.unlink(path)


@mcp.tool()
def paint_tiles(set: str, hexes: list[list[int]] | None = None, circle: list[int] | None = None,
                rect: list[int] | None = None, polygon: list[list[int]] | None = None, dry_run: bool = False,
                allow_warnings: bool = False, map_name: str = "3k_dlc07_main_map", tile_map: str | None = None,
                ak_root: str | None = None):
    """Add tiles: paint a tile set over hexes / a circle [c, r, radius] / a rect [c0, r0, c1, r1] / a polygon."""
    op = {"op": "paint", "set": set, **_area(hexes, circle, rect, polygon)}
    return edit_tiles([op], None, dry_run, allow_warnings, False, True, map_name, tile_map, ak_root)


@mcp.tool()
def erase_tiles(hexes: list[list[int]] | None = None, circle: list[int] | None = None, rect: list[int] | None = None,
                polygon: list[list[int]] | None = None, to: str | None = None, dry_run: bool = False,
                allow_warnings: bool = False, map_name: str = "3k_dlc07_main_map", tile_map: str | None = None,
                ak_root: str | None = None):
    """Remove tiles (a road, river, mountain patch...): the hexes take the most common surrounding area set (land,
    mountains...), or sea if they only touch sea. to: force one set instead."""
    op = {"op": "erase", **_area(hexes, circle, rect, polygon), **({"to": to} if to else {})}
    return edit_tiles([op], None, dry_run, allow_warnings, False, True, map_name, tile_map, ak_root)


@mcp.tool()
def draw_tile_line(set: str, points: list[list[int]], width: int = 1, dry_run: bool = False,
                   allow_warnings: bool = False, map_name: str = "3k_dlc07_main_map", tile_map: str | None = None,
                   ak_root: str | None = None):
    """Draw a connected one-hex-wide line (river, roads_tracks / roads_paved / roads_imperial, blockout_cliff, canal)
    through waypoints [[c, r], ...]."""
    op = {"op": "line", "set": set, "points": points, "width": width}
    return edit_tiles([op], None, dry_run, allow_warnings, False, True, map_name, tile_map, ak_root)


@mcp.tool()
def fill_tiles(set: str, at: list[int], max_hexes: int = 20000, dry_run: bool = False, allow_warnings: bool = False,
               map_name: str = "3k_dlc07_main_map", tile_map: str | None = None, ak_root: str | None = None):
    """Flood-fill the connected same-colour area containing hex at [c, r] with a tile set."""
    op = {"op": "fill", "set": set, "at": at, "max": max_hexes}
    return edit_tiles([op], None, dry_run, allow_warnings, False, True, map_name, tile_map, ak_root)


@mcp.tool()
def validate_tiles(rect: list[int] | None = None, map_name: str = "3k_dlc07_main_map", tile_map: str | None = None,
                   ak_root: str | None = None) -> dict:
    """Hex-rule check of the tile map (palette, line width, coast ring, cliff ends, river ends / crossings, unseen
    patterns) over rect [c0, r0, c1, r1] or the whole map. validate_tilemap also checks the kit files around it."""
    return _tiles("tiles-validate", map_name, ak_root, tile_map, *(["--rect", _csv(rect)] if rect else []))


@mcp.tool()
def tile_errors(map_name: str = "3k_dlc07_main_map", simulate: bool = False, codes: list[str] | None = None,
                rect: list[int] | None = None, limit: int = 200, fast: bool = False, tile_map: str | None = None,
                ak_root: str | None = None) -> dict:
    """Tile error mode: every tile-map error, one per hex, each with a recommended fix (the same engine as the app's
    Errors tab). Returns counts by code (count, fixable, advice), a list of errors (code, severity, hex [c, r], message,
    and either fix {summary, verified, score_before, score_after, ops} or advice), and whole-map problems (layout,
    climate, kit inputs). Every fix is checked with BOB's tile matching on a window around it (no new holes; rule-only
    fixes opened holes on main190); fast=True skips that (rules only, ~5x faster, NOT safe to apply blindly).
    simulate=True also lists existing holes (whole-map tile matching, 1-3 min). codes / rect narrow it.
    Fix ops are ordinary edit_tiles ops: apply one with edit_tiles, or all of them with fix_tiles."""
    args = ["--limit", str(limit)]
    if fast: args.append("--fast")
    if simulate: args.append("--simulate")
    if codes: args += ["--codes", ",".join(codes)]
    if rect: args += ["--rect", _csv(rect)]
    return _tiles("tiles-errors", map_name, ak_root, tile_map, *args)


@mcp.tool()
def fix_tiles(map_name: str = "3k_dlc07_main_map", codes: list[str] | None = None, verified_only: bool = True,
              dry_run: bool = False, simulate: bool = False, rect: list[int] | None = None,
              tile_map: str | None = None, ak_root: str | None = None) -> dict:
    """Apply the recommended fixes for tile errors as ONE journaled edit (undo with tile_undo). Run tile_checkpoint
    first. Each fix is checked with BOB's tile matching around it first; verified_only (default) applies only fixes that
    open no hole (False also applies rule-only fixes: risky). codes / rect limit which errors are fixed;
    dry_run reports without writing. Returns the edit result plus fixed / skipped counts and rule errors before → after.
    Re-run tile_errors(simulate=True) afterwards to confirm holes."""
    args = []
    if codes: args += ["--codes", ",".join(codes)]
    if not verified_only: args.append("--all")
    if dry_run: args.append("--dry-run")
    if simulate: args.append("--simulate")
    if rect: args += ["--rect", _csv(rect)]
    return _tiles("tiles-fix", map_name, ak_root, tile_map, *args)


@mcp.tool()
def preview_tiles(rect: list[int] | None = None, center: list[int] | None = None, size: int = 30, width: int = 1024,
                  show_edits: bool = True, show_issues: bool = True, map_name: str = "3k_dlc07_main_map",
                  tile_map: str | None = None, ak_root: str | None = None):
    """PNG of a hex area (rect [c0, r0, c1, r1], or center [c, r] with size): hexes in tile-set colours, a col/row
    grid and legend; show_edits outlines every journaled edit in white, show_issues rings rule problems (red error,
    orange warning). Returns the image and its path (give users the path)."""
    args = ["--width", str(width)]
    if rect: args += ["--rect", _csv(rect)]
    elif center: args += ["--center", _csv(center), "--size", str(size)]
    else: return {"error": "pass rect or center"}
    if show_edits: args.append("--edits")
    if show_issues: args.append("--issues")
    return _with_png(_tiles("tiles-preview", map_name, ak_root, tile_map, *args))


@mcp.tool()
def tile_checkpoint(label: str, map_name: str = "3k_dlc07_main_map", tile_map: str | None = None,
                    ak_root: str | None = None) -> dict:
    """Name the current tile-map edit state so tile_rollback(label) can return to it."""
    return _tiles("tiles-checkpoint", map_name, ak_root, tile_map, label)


@mcp.tool()
def tile_rollback(label: str, force: bool = False, map_name: str = "3k_dlc07_main_map", tile_map: str | None = None,
                  ak_root: str | None = None) -> dict:
    """Undo every tile edit since checkpoint `label` (byte-exact). Refuses if tile_map.png was changed outside these
    tools since (e.g. regenerated); force=True overwrites anyway."""
    return _tiles("tiles-rollback", map_name, ak_root, tile_map, label, *(["--force"] if force else []))


@mcp.tool()
def tile_undo(steps: int = 1, force: bool = False, map_name: str = "3k_dlc07_main_map", tile_map: str | None = None,
              ak_root: str | None = None) -> dict:
    """Undo the last `steps` tile edit batches."""
    return _tiles("tiles-undo", map_name, ak_root, tile_map, "--steps", str(steps), *(["--force"] if force else []))


@mcp.tool()
def tile_history(map_name: str = "3k_dlc07_main_map", tile_map: str | None = None, ak_root: str | None = None) -> dict:
    """Tile edit batches so far (seq, time, label, hexes, ops) and the named checkpoints."""
    return _tiles("tiles-history", map_name, ak_root, tile_map)


@mcp.tool()
def replay_tiles(from_seq: int = 1, to_seq: int | None = None, dry_run: bool = False, allow_warnings: bool = False,
                 force: bool = False, map_name: str = "3k_dlc07_main_map", tile_map: str | None = None,
                 ak_root: str | None = None):
    """Re-apply recorded tile edits (seq range, default all) to the current tile map as one new validated batch, e.g.
    after caime_tilemap.py regenerated it and wiped hand edits."""
    args = ["--from", str(from_seq), "--preview"]
    if to_seq is not None: args += ["--to", str(to_seq)]
    if dry_run: args.append("--dry-run")
    if allow_warnings: args.append("--allow-warnings")
    if force: args.append("--force")
    return _with_png(_tiles("tiles-replay", map_name, ak_root, tile_map, *args))


@mcp.tool()
def check_tile_holes(tile_list: str | None = None, since_seq: int = 0, limit: int = 40,
                     map_name: str = "3k_dlc07_main_map", tile_map: str | None = None, ak_root: str | None = None) -> dict:
    """After BOB Terrain / Tilemap: tile-map cells no tile_list.bin record covers (see-through holes), clustered,
    edge vs suspect, and which clusters lie in hexes edited since seq `since_seq`. tile_list defaults to the kit's
    working_data/terrain/campaigns/<map>/tile_list.bin."""
    args = ["--since", str(since_seq), "--limit", str(limit)]
    if tile_list: args += ["--tile-list", tile_list]
    return _tiles("tiles-holes", map_name, ak_root, tile_map, *args)


@mcp.tool()
def simulate_tiles(since_seq: int = 0, limit: int = 60, map_name: str = "3k_dlc07_main_map", tile_map: str | None = None,
                   ak_root: str | None = None) -> dict:
    """Simulate BOB's Terrain / Tilemap on the tile map (whole map, ~1-3 min) and list the hexes that would get no tile
    (see-through holes): those in hexes edited since seq `since_seq` first, then the rest. Use before a BOB run to
    check a batch of hand edits; check_tile_holes checks a real tile_list.bin afterwards."""
    return _tiles("tiles-simulate", map_name, ak_root, tile_map, "--since", str(since_seq), "--limit", str(limit))


# ---------------------------------------------------------------- generic Terry entities

def _entities(command: str, project: str | None, map_name: str | None, ak_root: str | None, *args: str):
    extra = ["--project", project] if project else []
    return _props(command, map_name, ak_root, *extra, *args)


@mcp.tool()
def list_entity_types(project: str | None = None, map_name: str = "3k_dlc07_main_map", ak_root: str | None = None) -> dict:
    """Every Terry entity type with its component layout, how often the kit uses it, and whether Terry allows it in the
    project (campaign tile_map, battle prefab, ...). project: a .terry path (default: the campaign map's)."""
    return _entities("entity-types", project, map_name, ak_root)


@mcp.tool()
def describe_entity_type(type: str, map_name: str = "3k_dlc07_main_map", ak_root: str | None = None) -> dict:
    """One entity type: its components and each component's fields (type, default, known values), conditional
    components ("when shape=polyline") and where Terry allows it. Use before create/set to get exact field names."""
    return _entities("entity-type", None, map_name, ak_root, type)


@mcp.tool()
def terry_project_info(project: str | None = None, map_name: str = "3k_dlc07_main_map", ak_root: str | None = None) -> dict:
    """Project type and database, layer count, active layer, terrain maps, and the undo history folder."""
    return _entities("entity-project", project, map_name, ak_root)


@mcp.tool()
def list_layers(nested: bool = False, name_filter: str | None = None, project: str | None = None,
                map_name: str = "3k_dlc07_main_map", ak_root: str | None = None) -> dict:
    """The layer tree: file layers with entity counts by type, export/visible/frozen/active state; nested=True also
    lists each file's folder and tag layers (with member counts)."""
    result = _entities("entity-layers", project, map_name, ak_root, *(["--all"] if nested else []))
    if name_filter and isinstance(result, dict) and "layers" in result:
        result["layers"] = [l for l in result["layers"] if name_filter.lower() in l["name"].lower()]
    return result


@mcp.tool()
def query_entities(types: list[str] | None = None, layer: str | None = None, where: list[str] | None = None,
                   name: str | None = None, rect: list[float] | None = None, parent: str | None = None,
                   full: bool = False, limit: int = 200, project: str | None = None,
                   map_name: str = "3k_dlc07_main_map", ak_root: str | None = None) -> dict:
    """Find entities. types: entity types ("Prop", "PointLight", "TagLayer"...; layers are excluded unless named);
    layer: a file layer name or id; where: field filters "ECMesh.model_path~tree" (contains), "ECX.f=value",
    "ECX.f!=value", or "ECComponent" (has it); name: name contains; rect: [x0, z0, x1, z1] on position; parent: a
    folder/tag layer id. full=True returns every component and field, else a summary (type, position, asset)."""
    args = ["--limit", str(limit)]
    if types: args += ["--type", _csv(types)]
    if layer: args += ["--layer", layer]
    for w in where or []: args += ["--where", w]
    if name: args += ["--name", name]
    if rect: args += ["--rect", _csv(rect)]
    if parent: args += ["--parent", parent]
    if full: args.append("--full")
    return _entities("entity-query", project, map_name, ak_root, *args)


@mcp.tool()
def get_entities(ids: list[str], project: str | None = None, map_name: str = "3k_dlc07_main_map",
                 ak_root: str | None = None):
    """Full entities: type, name, layer, parents, group, and every component with all its fields."""
    return _entities("entity-get", project, map_name, ak_root, *ids)


@mcp.tool()
def edit_entities(ops: list[dict], label: str | None = None, project: str | None = None,
                  map_name: str = "3k_dlc07_main_map", ak_root: str | None = None) -> dict:
    """Apply a batch of generic entity edits as one undo step. Nothing is written if any op fails.

    Targets: "id", "ids": [...], or "query": {types, layer, name, fields: [filters as in query_entities], rect, parent}
    (a query edits every match -- bulk find-and-replace).
      {"op":"set", <targets>, "fields":{"ECComponent.field": value}, "name": "..."}   values: str/number/bool/[vector]
      {"op":"add_component", <targets>, "component":"ECTerrainClamp", "fields":{...}}   (schema defaults otherwise)
      {"op":"remove_component", <targets>, "component":"..."}
      {"op":"create", "type":"PointLight", "layer":<file layer>, "parent":<folder/tag layer id>, "name":...,
       "position":[x,y,z], "fields":{"ECPointLight.radius": 12}, "components":[...optional override]}
      {"op":"delete", <targets>, "with_members": false}   (deleting a folder/tag layer moves its members up unless
       with_members)
      {"op":"move_to_layer", <targets>, "layer":<file layer>, "parent":...}   (ids are kept)
      {"op":"set_parent", <targets>, "parent": <layer id> | null}            (within the same file)
      {"op":"duplicate", <targets>, "by":[dx,dy,dz]}   (copies keep the original's layers/tags; returns the copies)
      {"op":"place_prefab", "key":..., "layer":..., "position":[x,y,z], "rotation":[rx,ry,rz], "scale": s|[sx,sy,sz]}
      {"op":"expand_prefab", <targets>, "recursive": true, "into_folder": true}
      {"op":"make_prefab", <targets>, "key":..., "folder":..., "replace": true}
      {"op":"create_layer", "name":..., "layer":<file layer, omit for a new file layer>, "tags":"a,b", "parent":...}
      {"op":"rename", "id":<entity, nested layer or file layer>, "name":...}
      {"op":"layer_state", "id":<layer>, "visible":bool, "frozen":bool, "export":bool, "active":true}
      {"op":"delete_layer", "id":<file layer>}   (removes the .layer file too; undo restores it)
    Returns the undo seq and each touched entity's new state (and warnings, e.g. enum values never seen in the kit).
    For the campaign map run rebuild_props afterwards to rebuild global_props.bin.
    """
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(ops, f)
        path = f.name
    try:
        return _entities("entity-edit", project, map_name, ak_root, "--ops", path, *(["--label", label] if label else []))
    finally:
        os.unlink(path)


@mcp.tool()
def set_entity_fields(ids: list[str], fields: dict, project: str | None = None, map_name: str = "3k_dlc07_main_map",
                      ak_root: str | None = None) -> dict:
    """Set fields on entities: fields = {"ECComponent.field": value}. Shortcut for edit_entities set."""
    return edit_entities([{"op": "set", "ids": ids, "fields": fields}], project=project, map_name=map_name, ak_root=ak_root)


@mcp.tool()
def bulk_set_entities(query: dict, fields: dict, label: str | None = None, project: str | None = None,
                      map_name: str = "3k_dlc07_main_map", ak_root: str | None = None) -> dict:
    """Find-and-replace: set fields on every entity a query matches. query = {types, layer, name, fields: [filters],
    rect, parent}; e.g. {"types":["Prop"], "fields":["ECMesh.model_path~old_tree"]} with
    {"ECMesh.model_path": "<new path>"}. Run query_entities with the same query first to check the matches."""
    return edit_entities([{"op": "set", "query": query, "fields": fields}], label=label, project=project,
                         map_name=map_name, ak_root=ak_root)


@mcp.tool()
def create_entity(type: str, layer: str, position: list[float] | None = None, fields: dict | None = None,
                  name: str | None = None, parent: str | None = None, project: str | None = None,
                  map_name: str = "3k_dlc07_main_map", ak_root: str | None = None) -> dict:
    """Create one entity of a Terry type in a file layer, with Terry's component layout and default values."""
    op = {"op": "create", "type": type, "layer": layer}
    if position: op["position"] = position
    if fields: op["fields"] = fields
    if name: op["name"] = name
    if parent: op["parent"] = parent
    return edit_entities([op], project=project, map_name=map_name, ak_root=ak_root)


@mcp.tool()
def delete_entities(ids: list[str], with_members: bool = False, project: str | None = None,
                    map_name: str = "3k_dlc07_main_map", ak_root: str | None = None) -> dict:
    """Delete entities (any type). A folder/tag layer's members move up a level unless with_members=True."""
    return edit_entities([{"op": "delete", "ids": ids, "with_members": with_members}], project=project,
                         map_name=map_name, ak_root=ak_root)


@mcp.tool()
def move_entities_to_layer(ids: list[str], layer: str, parent: str | None = None, project: str | None = None,
                           map_name: str = "3k_dlc07_main_map", ak_root: str | None = None) -> dict:
    """Move entities to another file layer (optionally into a folder/tag layer there). Ids are kept."""
    op = {"op": "move_to_layer", "ids": ids, "layer": layer}
    if parent: op["parent"] = parent
    return edit_entities([op], project=project, map_name=map_name, ak_root=ak_root)


@mcp.tool()
def create_layer(name: str, in_layer: str | None = None, tags: str | None = None, parent: str | None = None,
                 project: str | None = None, map_name: str = "3k_dlc07_main_map", ak_root: str | None = None) -> dict:
    """Create a layer: without in_layer, a new file layer in the project (its own .layer file); with in_layer, a
    folder layer inside that file, or a tag layer when tags is given (members export with those meta tags)."""
    op = {"op": "create_layer", "name": name}
    if in_layer: op["layer"] = in_layer
    if tags: op["tags"] = tags
    if parent: op["parent"] = parent
    return edit_entities([op], project=project, map_name=map_name, ak_root=ak_root)


@mcp.tool()
def set_layer_state(layer: str, visible: bool | None = None, frozen: bool | None = None, export: bool | None = None,
                    active: bool | None = None, project: str | None = None, map_name: str = "3k_dlc07_main_map",
                    ak_root: str | None = None) -> dict:
    """Show/hide, lock/unlock, export on/off, or make active a layer (file layer name/id or nested layer id)."""
    op = {"op": "layer_state", "id": layer}
    for k, v in (("visible", visible), ("frozen", frozen), ("export", export), ("active", active)):
        if v is not None: op[k] = v
    return edit_entities([op], project=project, map_name=map_name, ak_root=ak_root)


@mcp.tool()
def entity_checkpoint(label: str, project: str | None = None, map_name: str = "3k_dlc07_main_map",
                      ak_root: str | None = None) -> dict:
    """Name the current state so entity_rollback can return to it."""
    return _entities("entity-checkpoint", project, map_name, ak_root, label)


@mcp.tool()
def entity_rollback(label: str, force: bool = False, project: str | None = None, map_name: str = "3k_dlc07_main_map",
                    ak_root: str | None = None) -> dict:
    """Undo every entity edit made since a checkpoint."""
    return _entities("entity-rollback", project, map_name, ak_root, label, *(["--force"] if force else []))


@mcp.tool()
def entity_undo(steps: int = 1, force: bool = False, project: str | None = None, map_name: str = "3k_dlc07_main_map",
                ak_root: str | None = None) -> dict:
    """Undo the last entity edit batches (restores every file they touched, including created/deleted layer files)."""
    return _entities("entity-undo", project, map_name, ak_root, "--steps", str(steps), *(["--force"] if force else []))


@mcp.tool()
def entity_history(project: str | None = None, map_name: str = "3k_dlc07_main_map", ak_root: str | None = None) -> dict:
    """Edit batches (seq, time, label, files) and checkpoints."""
    return _entities("entity-history", project, map_name, ak_root)


@mcp.tool()
def list_prefabs(filter: str | None = None, limit: int = 300, project: str | None = None,
                 map_name: str = "3k_dlc07_main_map", ak_root: str | None = None) -> dict:
    """Prefab keys in the project database's library (battle or campaign), with their paths."""
    args = ["--limit", str(limit)]
    if filter: args += ["--filter", filter]
    return _entities("prefab-list", project, map_name, ak_root, *args)


@mcp.tool()
def describe_prefab(key: str, project: str | None = None, map_name: str = "3k_dlc07_main_map",
                    ak_root: str | None = None) -> dict:
    """What a prefab holds: entity count (and with nested prefabs expanded), types, x/z bounds, nested keys, assets."""
    return _entities("prefab-get", project, map_name, ak_root, key)


@mcp.tool()
def place_prefab(key: str, layer: str, position: list[float], rotation: list[float] | None = None,
                 scale: float | list[float] | None = None, parent: str | None = None, project: str | None = None,
                 map_name: str = "3k_dlc07_main_map", ak_root: str | None = None) -> dict:
    """Place a Prefab instance (key from list_prefabs) in a file layer. Rotation in degrees (y = heading)."""
    op = {"op": "place_prefab", "key": key, "layer": layer, "position": position}
    if rotation: op["rotation"] = rotation
    if scale is not None: op["scale"] = scale
    if parent: op["parent"] = parent
    return edit_entities([op], project=project, map_name=map_name, ak_root=ak_root)


@mcp.tool()
def expand_prefabs(ids: list[str], recursive: bool = True, into_folder: bool = True, project: str | None = None,
                   map_name: str = "3k_dlc07_main_map", ak_root: str | None = None) -> dict:
    """Break Prefab instances apart into their entities (transforms composed, overrides applied, nested prefabs
    expanded when recursive), in a folder layer named after the prefab unless into_folder=False."""
    return edit_entities([{"op": "expand_prefab", "ids": ids, "recursive": recursive, "into_folder": into_folder}],
                         project=project, map_name=map_name, ak_root=ak_root)


@mcp.tool()
def make_prefab(ids: list[str], key: str, folder: str | None = None, replace: bool = True, project: str | None = None,
                map_name: str = "3k_dlc07_main_map", ak_root: str | None = None) -> dict:
    """Save entities as a new prefab (<library>/<folder>/<key>.terry, centred on their x/z middle at the lowest y);
    with replace the originals become one instance of it. Undoable like any edit (the new files are removed)."""
    op = {"op": "make_prefab", "ids": ids, "key": key, "replace": replace}
    if folder: op["folder"] = folder
    return edit_entities([op], project=project, map_name=map_name, ak_root=ak_root)


def _assets(command: str, *args: str, mod_packs: list[str] | None = None, asset_roots: list[str] | None = None,
            project: str | None = None):
    extra = []
    for p in mod_packs or []: extra += ["--mod-pack", p]
    for r in asset_roots or []: extra += ["--asset-root", r]
    if project: extra += ["--project", project]
    result = _run([command, *args, *extra], timeout=900)
    payload = result.get("result")
    if isinstance(payload, dict) and "error" in payload:
        return {"error": payload["error"]}
    return payload if payload is not None else result


@mcp.tool()
def find_assets(filter: str, extensions: list[str] | None = None, limit: int = 100, mod_packs: list[str] | None = None,
                asset_roots: list[str] | None = None) -> dict:
    """Asset paths containing `filter` (default extensions .wsmodel and .rigid_model_v2; e.g. [".dds"], [".material"])."""
    args = [filter, "--limit", str(limit)]
    if extensions: args += ["--ext", ",".join(extensions)]
    return _assets("asset-find", *args, mod_packs=mod_packs, asset_roots=asset_roots)


@mcp.tool()
def inspect_asset(path: str, lod: int = 0, mod_packs: list[str] | None = None, asset_roots: list[str] | None = None) -> dict:
    """What a model / .material / .dds resolves to: source pack, geometry, LODs (vertices, triangles), per-mesh material,
    shader, colour texture and alpha test, bounds, and problems (missing materials/textures)."""
    return _assets("asset-info", path, "--lod", str(lod), mod_packs=mod_packs, asset_roots=asset_roots)


@mcp.tool()
def preview_asset(path: str, yaw: float = 35, pitch: float = 30, size: int = 384, lod: int = 0, textured: bool = True,
                  mod_packs: list[str] | None = None, asset_roots: list[str] | None = None):
    """Render a model (orthographic, textured, alpha-tested) and return the image. pitch 90 = straight down (decals)."""
    out = os.path.join(tempfile.gettempdir(), "terry_asset_preview.png")
    args = [path, "--out", out, "--yaw", str(yaw), "--pitch", str(pitch), "--size", str(size), "--lod", str(lod)]
    if not textured: args.append("--untextured")
    result = _assets("asset-preview", *args, mod_packs=mod_packs, asset_roots=asset_roots)
    if isinstance(result, dict) and "error" in result:
        return result
    return [Image(path=out), json.dumps(result)]


@mcp.tool()
def check_project_assets(project: str | None = None, map_name: str = "3k_dlc07_main_map", ak_root: str | None = None,
                         mod_packs: list[str] | None = None, asset_roots: list[str] | None = None) -> dict:
    """Load every model a project's entities use (ECMesh / ECDecal model_path) and report the ones that fail or miss
    materials/textures, with how many entities use each."""
    extra = _common(map_name, ak_root)
    return _assets("asset-check", *extra, mod_packs=mod_packs, asset_roots=asset_roots, project=project)

@mcp.tool()
def map_audit(map_name: str = "3k_dlc07_main_map", ak_root: str | None = None, project: str | None = None,
              packs: list[str] | None = None, checks: list[str] | None = None, out_dir: str | None = None) -> dict:
    """Audit a campaign map's project layers (hidden included) for defects, read-only. Checks: floating-mountain /
    buried-mountain (LF-offset mountains: stored y is an offset above the terrain), buried-prop, floating-prop (rocks),
    prop-in-sea, wrong-region (info), on-city-footprint (mountains/rocks/trees crowding map.hex towns), duplicate,
    asset, scale-outlier, city (map.hex settlement slots), road-river, city-dressing (info). Writes findings.csv,
    summary.json and fix_<check>.json (entity-edit ops: apply after review with edit_entities / entity-edit) to
    out_dir (default output/audit/<map>); returns the summary. Calibrated on vanilla dlc07: compare counts with it.
    Use packs for mod packs (e.g. the map's native .pack) so their models resolve."""
    args = ["map-audit", *_common(map_name, ak_root)]
    for p in packs or []: args += ["--pack", p]
    if project: args += ["--project", project]
    if checks: args += ["--checks", ",".join(checks)]
    if out_dir: args += ["--out", out_dir]
    result = _run(args, timeout=1800)
    return result.get("result", result)


# ---------------------------------------------------------------- collaboration
# Two ways to share map work:
# - change packages (.a3kpatch): patch_export -> send the file -> patch_import on the other side (three-way merged
#   with the importer's own edits; conflicts listed by conflicts / resolved by resolve_conflicts; patch_undo).
# - project repositories: the kit's map folder as a git repo (rasters in LFS, Atlas3K as merge driver), on GitHub
#   or any remote: collab_init / collab_clone, collab_status, collab_commit, collab_pull, collab_push, branches,
#   pull requests with map diffs (pr_*), issues pinned to map positions (map pins), and locks.
# Merges are per entity / per pixel: only the same attribute or pixel changed differently on both sides conflicts.


def _collab(command: str, *args: str, map_name: str | None = None, ak_root: str | None = None, timeout: int = 1800) -> dict:
    result = _run([command, *_common(map_name, ak_root), *args], timeout=timeout)
    return result.get("result", result)


@mcp.tool()
def patch_export(output: str, since: str | None = None, base_dir: str | None = None, label: str | None = None,
                 description: str | None = None, map_name: str | None = None, ak_root: str | None = None) -> dict:
    """Write a change package (.a3kpatch) of map edits to send to a collaborator: either every kit file the edit
    journals changed after `since` ("yyyy-MM-dd HH:mm"), or the map folder against `base_dir` (a copy of the map folder
    as it was). Rasters ship only their changed 64-pixel cells."""
    args = [output]
    if since: args += ["--since", since]
    if base_dir: args += ["--base", base_dir]
    if label: args += ["--label", label]
    if description: args += ["--description", description]
    return _collab("patch-export", *args, map_name=map_name, ak_root=ak_root)


@mcp.tool()
def patch_import(package: str, dry_run: bool = True, map_name: str | None = None, ak_root: str | None = None) -> dict:
    """Import a change package: files still at the package's base are replaced, the rest are three-way merged with local
    edits (per entity / per pixel). dry_run (default) only reports. One undo step (patch_undo)."""
    return _collab("patch-import", package, *(["--dry-run"] if dry_run else []), map_name=map_name, ak_root=ak_root)


@mcp.tool()
def patch_undo(map_name: str | None = None, ak_root: str | None = None) -> dict:
    """Undo the last change-package import."""
    return _collab("patch-undo", map_name=map_name, ak_root=ak_root)


@mcp.tool()
def conflicts(map_name: str | None = None, ak_root: str | None = None, from_import: bool = False) -> dict:
    """Open merge conflicts (the repository's after a pull/merge, else the last package import's; from_import forces
    the import's). Each has a kind (entity/attribute/header/pixels/size/binary), ours/theirs values and a location."""
    return _collab("conflicts", *(["--import"] if from_import else []), map_name=map_name, ak_root=ak_root)


@mcp.tool()
def resolve_conflicts(side: str, ids: list[int] | None = None, map_name: str | None = None, ak_root: str | None = None,
                      from_import: bool = False) -> dict:
    """Resolve conflicts to "ours" (keep the merged file as is) or "theirs" (take the other side's entity, attribute or
    pixels). ids = conflict indices (default all open ones). In a repository, collab_commit afterwards."""
    args = [side]
    if ids: args += ["--ids", ",".join(map(str, ids))]
    if from_import: args += ["--import"]
    return _collab("conflicts-resolve", *args, map_name=map_name, ak_root=ak_root)


@mcp.tool()
def collab_init(github: str | None = None, remote: str | None = None, public: bool = False,
                map_name: str | None = None, ak_root: str | None = None) -> dict:
    """Make the map folder a project repository (LFS rasters, Atlas3K merge driver, first commit). github="owner/name"
    creates that GitHub repository (private unless public) and pushes; remote=URL pushes to an existing remote.
    Assembly-kit data is CA's: keep GitHub repositories private."""
    args = []
    if github: args += ["--github", github]
    if remote: args += ["--remote", remote]
    if public: args += ["--public"]
    return _collab("collab-init", *args, map_name=map_name, ak_root=ak_root)


@mcp.tool()
def collab_clone(repository: str, ak_root: str | None = None) -> dict:
    """Clone a project repository (URL or GitHub owner/name) into the kit as the map it holds."""
    return _collab("collab-clone", repository, ak_root=ak_root)


@mcp.tool()
def collab_status(map_name: str | None = None, ak_root: str | None = None) -> dict:
    """Branch, ahead/behind, changed files, open conflicts, everyone's locks and a commit message suggested from the
    edit journals."""
    return _collab("collab-status", map_name=map_name, ak_root=ak_root)


@mcp.tool()
def collab_commit(message: str | None = None, force: bool = False, map_name: str | None = None, ak_root: str | None = None) -> dict:
    """Commit all map changes (default message from the edit journals). Refuses while conflicts are open unless force."""
    args = []
    if message: args += ["-m", message]
    if force: args += ["--force"]
    return _collab("collab-commit", *args, map_name=map_name, ak_root=ak_root)


@mcp.tool()
def collab_sync(action: str, target: str | None = None, map_name: str | None = None, ak_root: str | None = None) -> dict:
    """action: "pull" (merge others' work), "push", "merge" (target = branch, e.g. origin/main), "revert" (target =
    commit), "switch" (target = branch), "create_branch" (target = new branch). Merges go through Atlas3K's map merge."""
    commands = {"pull": ["collab-pull"], "push": ["collab-push"], "merge": ["collab-merge", target or ""],
                "revert": ["collab-revert", target or ""], "switch": ["collab-branch", target or ""],
                "create_branch": ["collab-branch", target or "", "--create"]}
    if action not in commands:
        return {"error": f"unknown action {action}"}
    return _collab(*commands[action], map_name=map_name, ak_root=ak_root)


@mcp.tool()
def collab_history(count: int = 30, map_name: str | None = None, ak_root: str | None = None) -> dict:
    """Recent commits with the files each changed."""
    return _collab("collab-log", "--count", str(count), map_name=map_name, ak_root=ak_root)


@mcp.tool()
def collab_diff(from_rev: str = "HEAD", to_rev: str | None = None, markdown: bool = False,
                map_name: str | None = None, ak_root: str | None = None) -> dict:
    """Map-aware diff between revisions (to_rev None = uncommitted work): entities added/removed/changed (with world
    positions and changed fields) per layer, changed pixels per raster."""
    args = [from_rev] + ([to_rev] if to_rev else []) + (["--markdown"] if markdown else [])
    return _collab("collab-diff", *args, map_name=map_name, ak_root=ak_root)


@mcp.tool()
def pull_request(action: str, number: int | None = None, title: str | None = None, body: str | None = None,
                 base: str | None = None, draft: bool = False, review: str | None = None, method: str = "merge",
                 state: str = "open", post: bool = False, map_name: str | None = None, ak_root: str | None = None) -> dict:
    """GitHub pull requests. action: "create" (title, body, base, draft; the description gets the map diff), "list"
    (state), "view", "diff" (map diff of PR `number`; post=True comments it), "checkout", "comment" (body), "review"
    (review = approve|request-changes|comment, body), "merge" (method merge|squash|rebase)."""
    n = str(number) if number is not None else ""
    if action == "create":
        args = ["pr-create", "--title", title or ""] + (["--body", body] if body else []) + (["--base", base] if base else []) + (["--draft"] if draft else [])
    elif action == "list":
        args = ["pr-list", "--state", state]
    elif action in ("view", "checkout"):
        args = [f"pr-{action}", n]
    elif action == "diff":
        args = ["pr-diff", n] + (["--post"] if post else [])
    elif action == "comment":
        args = ["pr-comment", n, "--body", body or ""]
    elif action == "review":
        args = ["pr-review", n, review or "comment"] + (["--body", body] if body else [])
    elif action == "merge":
        args = ["pr-merge", n, "--method", method]
    else:
        return {"error": f"unknown action {action}"}
    return _collab(*args, map_name=map_name, ak_root=ak_root)


@mcp.tool()
def map_pins(action: str = "list", number: int | None = None, title: str | None = None, body: str | None = None,
             x: float | None = None, z: float | None = None, layer: str | None = None, entity: str | None = None,
             assignee: str | None = None, state: str = "open", map_name: str | None = None, ak_root: str | None = None) -> dict:
    """Issues pinned to map positions (GitHub issues labelled map-pin; Atlas3K draws them on the map). action: "list"
    (state), "create" (title, x, z world coords, body, layer, entity, assignee), "comment" (number, body), "close"
    (number, body)."""
    if action == "list":
        args = ["pin-list", "--state", state]
    elif action == "create":
        args = ["pin-create", "--title", title or "", "--x", str(x), "--z", str(z)]
        for k, v in (("--body", body), ("--layer", layer), ("--entity", entity), ("--assignee", assignee)):
            if v: args += [k, v]
    elif action == "comment":
        args = ["pin-comment", str(number), "--body", body or ""]
    elif action == "close":
        args = ["pin-close", str(number)] + (["--body", body] if body else [])
    else:
        return {"error": f"unknown action {action}"}
    return _collab(*args, map_name=map_name, ak_root=ak_root)


@mcp.tool()
def locks(action: str = "list", file: str | None = None, layer: str | None = None, rect: list[float] | None = None,
          reason: str | None = None, ids: list[str] | None = None, force: bool = False,
          map_name: str | None = None, ak_root: str | None = None) -> dict:
    """Shared "I'm working on this" locks. action: "list", "acquire" (file = map-folder-relative path, or layer = file
    layer name -- editors then refuse to save it for anyone else -- or rect = [x0, z0, x1, z1] world region, advisory;
    reason), "release" (ids, default all mine; force breaks someone else's)."""
    if action == "list":
        return _collab("lock-list", map_name=map_name, ak_root=ak_root)
    if action == "acquire":
        args = ["lock-acquire"]
        if file: args += ["--file", file]
        if layer: args += ["--layer", layer]
        if rect: args += ["--rect", ",".join(map(str, rect))]
        if reason: args += ["--reason", reason]
        return _collab(*args, map_name=map_name, ak_root=ak_root)
    if action == "release":
        return _collab("lock-release", *([",".join(ids)] if ids else []), *(["--force"] if force else []),
                       map_name=map_name, ak_root=ak_root)
    return {"error": f"unknown action {action}"}


if __name__ == "__main__":
    mcp.run()
