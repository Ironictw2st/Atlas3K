"""Exact parser for Total War: Three Kingdoms compiled campaign tile database (FASTBIN0).

Files:
  terrain/tiles/campaign/_tile_database/_settings.bin   -> TILE_DATABASE (render/conversion params,
                                                           climates, tile sets)
  terrain/tiles/campaign/_tile_database/tiles/*.bin     -> one TILE_DATABASE_TILE each

Layout recovered from warscape.modder.x64.dll serializers (see TILEDB_FORMAT.md).
FASTBIN0 = "FASTBIN0" magic + raw little-endian values, no field names / no type tags
(names + type codes are only present in the SAFEBIN variant).  Every struct starts with a
u16 serialise_version; every array is u32 "size" followed by the elements; strings are
u16 byte length + chars (no terminator).

Primitive types (FUN_1802c7fa0 type code -> reader):
  1 bool  (u8)        FUN_1802cdba0
  2 byte  (u8)        FUN_1803f81e0      (colour channels in newer versions)
  5 u16               FUN_1802cd9b0      (serialise_version)
  6 u32               FUN_1802cda50      (sizes, counts, width/height)
  7 i32               FUN_1802cda00      (link x/y, may be -1)
  8 f32               FUN_1802cdaa0 / FUN_1802b5280
  9 string            FUN_1802cdaf0
"""
import os
import struct
import sys
from collections import Counter

MAGIC = b"FASTBIN0"


class ParseError(Exception):
    pass


class Reader:
    def __init__(self, data, path=""):
        self.d = data
        self.p = 0
        self.path = path
        if data[:8] != MAGIC:
            raise ParseError("%s: bad magic %r" % (path, data[:8]))
        self.p = 8
        self.odd_bools = []

    # --- primitives -------------------------------------------------------
    def _take(self, n):
        if self.p + n > len(self.d):
            raise ParseError("%s: read past EOF at 0x%x (+%d)" % (self.path, self.p, n))
        b = self.d[self.p:self.p + n]
        self.p += n
        return b

    def bool(self):
        # The engine copies the raw byte (FUN_1802b4f40) and tests it as != 0.  Some files carry
        # garbage (uninitialised) bytes in bool slots, so non-0/1 values are recorded, not rejected.
        v = self._take(1)[0]
        if v not in (0, 1):
            self.odd_bools.append((self.p - 1, v))
        return v != 0

    def u8(self):
        return self._take(1)[0]

    def u16(self):
        return struct.unpack("<H", self._take(2))[0]

    def u32(self):
        return struct.unpack("<I", self._take(4))[0]

    def i32(self):
        return struct.unpack("<i", self._take(4))[0]

    def f32(self):
        return struct.unpack("<f", self._take(4))[0]

    def str(self):
        n = self.u16()
        return self._take(n).decode("latin-1")

    def vec3(self):
        return (self.f32(), self.f32(), self.f32())

    def version(self, max_supported):
        v = self.u16()
        if v > max_supported:
            raise ParseError("%s: serialise_version %d > supported %d at 0x%x"
                             % (self.path, v, max_supported, self.p - 2))
        return v

    def array(self, fn):
        n = self.u32()
        return [fn() for _ in range(n)]

    def at_end(self):
        return self.p == len(self.d)


def _rgb_versioned(r, v, float_below):
    """Colour: 3 f32 (red, green, blue) when v < float_below, else 3 bytes."""
    if v < float_below:
        rf, gf, bf = r.f32(), r.f32(), r.f32()
        return (int(rf) & 0xFF, int(gf) & 0xFF, int(bf) & 0xFF)
    return (r.u8(), r.u8(), r.u8())


# ===========================================================================
# _settings.bin  (TILE_DATABASE, FUN_1803c2070)
# ===========================================================================

def _fog_of_war_params(r):  # FUN_1803c4b50, max version 6
    v = r.version(6)
    o = {"serialise_version": v,
         "fog_of_war_brightness": r.f32(),
         "fog_of_war_saturation": r.f32()}
    if v > 1:
        o["shroud_cel_steps"] = r.u32()
        for k in ("shroud_cel_offset", "shroud_cel_strength", "shroud_cel_blend",
                  "shroud_edge_depth_bias", "shroud_edge_depth_scale", "shroud_edge_normal_bias",
                  "shroud_edge_normal_scale", "shroud_edge_pillow", "shroud_edge_blend",
                  "discovered_shroud_brightness", "discovered_shroud_saturation",
                  "undiscovered_shroud_brightness", "undiscovered_shroud_saturation",
                  "shroud_edge_noise_uv_scale", "shroud_edge_noise_strength",
                  "shroud_edge_brightness", "shroud_edge_ink_uv_scale", "shroud_lerp_time",
                  "shroud_terrain_detail_factor"):
            o[k] = r.f32()
    if v > 2:
        o["shroud_edge_kernel_size"] = r.f32()
        o["shroud_ssao_strength"] = r.f32()
    if v > 3:
        o["discovered_shroud_border_brightness"] = r.f32()
        o["discovered_shroud_border_saturation"] = r.f32()
    if v > 4:
        o["discovered_shroud_border_alpha"] = r.f32()
    if v > 5:
        o["shroud_fade_in_out_alpha"] = r.f32()
    return o


def _render_params(r):  # FUN_1803c4fe0, max version 13
    v = r.version(13)
    o = {"serialise_version": v, "lf_height": r.f32()}
    if v > 6:
        o["alt_lf_height"] = r.f32()
    for k in ("hf_height", "blend_pixel_scale", "unit_scale", "mid_distance_detail_scale",
              "mid_distance_detail_strength", "mid_distance_normal_strength",
              "mid_distance_detail_near"):
        o[k] = r.f32()
    if v < 11:
        o["mid_distance_detail_far"] = r.f32()  # read and discarded by the engine
    for k in ("mid_distance_detail_slope_low", "mid_distance_detail_slope_high",
              "vertical_offset", "normal_lf_scale", "normal_tile_scale", "normal_terrain_scale"):
        o[k] = r.f32()
    if v > 2:
        o["blend_contrast"] = r.f32()
        for i in range(4):
            o["layer_exempt_%d" % i] = r.str()
    if v > 3:
        o["campaign_sea_transparency_scale"] = r.f32()
        o["campaign_sea_uv_scale"] = r.f32()
    if v > 5:
        for k in ("near_distance_detail_distance", "near_distance_detail_scale",
                  "near_distance_detail_strength", "mid_distance_detail_near_lq"):
            o[k] = r.f32()
    if v > 7:
        o["grass_normal_scale"] = r.f32()
    if v > 8:
        for k in ("near_distance_normal_strength", "near_distance_detail_slope_low",
                  "near_distance_detail_slope_high"):
            o[k] = r.f32()
    if v > 9:
        o["fog_of_war_params"] = _fog_of_war_params(r)
    if v > 11:
        for k in ("far_terrain_mid_distance_colour_strength",
                  "far_terrain_mid_distance_normal_strength",
                  "far_terrain_mid_distance_material_strength"):
            o[k] = r.f32()
    if v > 12:
        o["lf_terrain_z_scale_factor"] = r.f32()
    return o


def _conversion_params(r):  # FUN_1803c48d0, max version 4
    v = r.version(4)
    o = {"serialise_version": v}
    if v > 1:
        o["use_placement_groups"] = r.bool()
    o["triangle_density"] = r.u32()
    o["max_lf_heights_per_pixel"] = r.u32()
    if v > 1:
        o["shadow_mesh_angle"] = r.f32()
    o["triangle_decimation_size_factors"] = [r.f32() for _ in range(6)]
    o["triangle_decimation_angle_factors"] = [r.f32() for _ in range(6)]
    if v > 2:
        o["land_colour"] = r.vec3()
        o["sea_colour"] = r.vec3()
        o["nogo_colour"] = r.vec3()
    return o


def _climate_texture(r):  # FUN_1803c46d0, max version 9 (fails for v <= 5)
    v = r.version(9)
    if v <= 5:
        raise ParseError("climate TEXTURE version %d <= 5 is rejected by the engine" % v)
    o = {"serialise_version": v, "name": r.str()}
    if 3 <= v <= 6:
        o["mid_distance_strength"] = r.f32()
    if v >= 7:
        o["mid_distance_colour_strength"] = r.f32()
        o["mid_distance_normal_strength"] = r.f32()
    o["blend_pixel_scale"] = r.f32()
    if v >= 2:
        o["outfield_blend_pixel_scale"] = r.f32()
    if v >= 6:
        o["near_distance_strength"] = r.f32()
    if v >= 8:
        o["mid_distance_colour_saturation"] = r.f32()
    if v >= 9:
        o["mid_distance_material_map_strength"] = r.f32()
    return o


def _climate(r):  # FUN_1803c43c0, max version 8
    v = r.version(8)
    o = {"serialise_version": v, "name": r.str()}
    if v < 6:
        o["texture_set"] = r.str()
    o["rgb"] = _rgb_versioned(r, v, 8)
    o["textures"] = r.array(lambda: _climate_texture(r))  # TEXTURES / TEXTURE, FUN_1803d51a0
    if 2 <= v <= 3:
        o["grass_alpha_add"] = r.f32()
        o["grass_alpha_mul"] = r.f32()
    if 3 <= v <= 4:
        o["destruction_climate"] = r.str()
    if v > 4:
        o["vampire_creep_climate"] = r.str()
        o["chaos_creep_climate"] = r.str()
    if v > 6:
        o["grass_mid_distance_colour_saturation"] = r.f32()
    return o


def _tile_set(r):  # FUN_1803c5a50, max version 3
    v = r.version(3)
    o = {"serialise_version": v, "name": r.str(), "linking_tile": r.str(),
         "shared_geometry": r.str(), "also_place_tile_set": r.str(), "link_as_set": r.str()}
    o["rgb"] = _rgb_versioned(r, v, 3)
    o["exclude_from_global_mesh"] = r.bool() if v > 1 else False
    return o


def load_settings(path):
    """Parse _settings.bin.  Returns dict with version, render_params, conversion_params,
    climates (list, index order) and tile_sets (list, index order; 'id' = index)."""
    data = open(path, "rb").read()
    r = Reader(data, path)
    v = r.version(1)                        # TILE_DATABASE serialise_version
    out = {"serialise_version": v,
           "render_params": _render_params(r),        # RENDER_PARAMS
           "conversion_params": _conversion_params(r)}  # CONVERSION_PARAMS
    climates = r.array(lambda: _climate(r))          # CLIMATES / CLIMATE (FUN_1803d97c0)
    for i, c in enumerate(climates):
        c["id"] = i
    tile_sets = r.array(lambda: _tile_set(r))        # TILE_SETS / TILE_SET (FUN_1803d9e00)
    for i, t in enumerate(tile_sets):
        t["id"] = i
    out["climates"] = climates
    out["tile_sets"] = tile_sets
    # TILES (FUN_1803db390) are not stored here: the engine enumerates tiles/*.bin.
    if not r.at_end():
        raise ParseError("%s: %d leftover bytes at 0x%x" % (path, len(data) - r.p, r.p))
    assert r.p == len(data)
    return out


# ===========================================================================
# tiles/*.bin  (TILE_DATABASE_TILE, FUN_1803c5550)
# ===========================================================================

def _texture_set(r):  # FUN_1803c1690, max version 2
    v = r.version(2)
    o = {"serialise_version": v}
    if v > 1:
        o["faction_key"] = r.str()
    for k in ("red0", "green0", "blue0", "alpha0", "red1", "green1", "blue1", "alpha1"):
        o[k] = r.str()
    return o


def _variation(r):  # FUN_1803c5c70, max version 10
    v = r.version(10)
    o = {"serialise_version": v}
    if v < 5:
        if v > 1:
            o["TEXTURE_GROUP"] = {"red": r.str(), "green": r.str(), "blue": r.str(),
                                  "alpha": r.str()}
        o["location"] = r.str()
        if v > 2:
            o["name"] = r.str()
        o["min_height"] = r.f32()
        o["scale"] = r.f32()
        o["normal_strength"] = r.f32()
        o["overlap_border_size"] = r.f32()
        o["raw_data_tri_density"] = r.u32()
        o["blend_common"] = r.str()
        o["index_common"] = r.str()
        o["normal_common"] = r.str()
        o["rgb"] = _rgb_versioned(r, 0, 1)
        if v > 3:
            o["requires_sea_in_infield"] = r.bool()
        return o
    o["texture_set"] = _texture_set(r)
    o["location"] = r.str()
    o["name"] = r.str()
    o["min_height"] = r.f32()
    o["scale"] = r.f32()
    o["normal_strength"] = r.f32()
    o["overlap_border_size"] = r.f32()
    o["raw_data_tri_density"] = r.u32()
    o["blend_common"] = r.str()
    o["index_common"] = r.str()
    o["normal_common"] = r.str()
    o["rgb"] = _rgb_versioned(r, v, 10)
    o["requires_sea_in_infield"] = r.bool()
    if v > 5:
        o["shadow_camera_depth"] = r.f32()
    if v > 6:
        o["enable_sea_water_plane"] = r.bool()
    if v > 7:
        o["is_subterranean"] = r.bool()
    if v > 8:
        o["fog_mask"] = r.str()
    return o


def _link_target(r):  # TILE_LINK_TARGET, inline in FUN_1803d81b0, version 1
    v = r.version(1)
    return {"serialise_version": v, "tile_set": r.str(), "x": r.i32(), "y": r.i32()}


def _link(r):  # TILE_LINK, FUN_1803c24c0, version 1
    v = r.version(1)
    o = {"serialise_version": v,
         "link_set": r.str(),
         "x": r.i32(), "y": r.i32(),
         "base_x": r.i32(), "base_y": r.i32(),
         "is_entry": r.bool()}
    # blend_quad / point array: FUN_1803d9020 -> FUN_1803d4ee0 (x, y, z f32)
    o["blend_quad"] = r.array(lambda: (r.f32(), r.f32(), r.f32()))
    o["blend_size"] = r.u32()
    o["no_offline_blend"] = r.bool()
    o["test"] = r.str()  # enum via TILE_DATABASE_TILE_LINK::string_to_enum (TLT_*)
    return o


def load_tile(path):
    """Parse one tiles/*.bin TILE_DATABASE_TILE (FUN_1803c5550, max serialise_version 7)."""
    data = open(path, "rb").read()
    r = Reader(data, path)
    v = r.version(7)
    o = {"serialise_version": v, "file": os.path.basename(path)}
    if v < 2:
        o["location"] = r.str()
    if v > 1:
        o["name"] = r.str()
    o["tile_set"] = r.str()          # FUN_1803da770 -> TILE_DATABASE::string_to_tile_set
    o["mask"] = r.str()              # FUN_1803dab50 -> TILE_DATABASE_TILE::string_to_mask
    if v > 5:
        o["nogo"] = r.str()          # second mask (same mask_to_string / string_to_mask)
    o["width"] = r.u32()
    o["height"] = r.u32()
    o["rgb"] = _rgb_versioned(r, v, 7)
    o["requires_infield_lodding"] = r.bool()
    o["random_rotatable"] = r.bool()
    o["custom_alpha_blend_texture"] = r.str()
    # "scalable" is a 1-byte bool slot, but 178 vanilla files hold non-0/1 garbage here
    # (uninitialised in the writer).  Engine semantics = raw byte != 0; raw kept for reference.
    o["scalable_raw"] = r.u8()
    o["scalable"] = o["scalable_raw"] != 0
    o["encampable"] = r.bool()
    o["custom_blend_tile"] = r.str()
    if v < 4:
        o["TEXTURE_GROUP"] = {"red": r.str(), "green": r.str(), "blue": r.str(),
                              "alpha": r.str()}
    o["variations"] = r.array(lambda: _variation(r))        # VARIATIONS / VARIATION
    o["link_targets"] = r.array(lambda: _link_target(r))    # TILE_LINK_TARGETS / TILE_LINK_TARGET
    o["links"] = r.array(lambda: _link(r))                  # TILE_LINKS / TILE_LINK
    if v > 2:
        o["barbarian"] = r.bool()
    if v > 4:
        o["use_alt_lf"] = r.bool()
    if not r.at_end():
        raise ParseError("%s: %d leftover bytes at 0x%x" % (path, len(data) - r.p, r.p))
    assert r.p == len(data)
    o["key"] = o["tile_set"] + "_" + o.get("name", "")   # == file stem for every vanilla tile
    o["mask_grid"] = mask_grid(o)
    if r.odd_bools:
        o["_odd_bool_bytes"] = r.odd_bools  # [(file offset, raw byte)]
    return o


def mask_grid(tile):
    """Mask string -> list of rows (mask_grid[y][x] -> bool), or None when unmasked.
    The mask string is '0'/'1' chars, length width*height, row-major: index = width*y + x
    (TILE_DATABASE_TILE::subtile_masked_valid).  Empty mask = every subtile valid."""
    m, w, h = tile["mask"], tile["width"], tile["height"]
    if not m:
        return None
    if len(m) != w * h:
        raise ParseError("%s: mask length %d != %dx%d" % (tile.get("file"), len(m), w, h))
    return [[m[y * w + x] == "1" for x in range(w)] for y in range(h)]


def load_all(dir):
    """dir = .../_tile_database.  Returns (settings, {tile file stem: tile})."""
    settings = load_settings(os.path.join(dir, "_settings.bin"))
    tdir = os.path.join(dir, "tiles")
    tiles = {}
    for fn in sorted(os.listdir(tdir)):
        if fn.lower().endswith(".bin"):
            tiles[fn[:-4]] = load_tile(os.path.join(tdir, fn))
    return settings, tiles


DEFAULT_DIR = r"Z:\Claude\TerryClone\Vanilla\terrain\tiles\campaign\_tile_database"


def main(argv):
    d = argv[1] if len(argv) > 1 else DEFAULT_DIR
    s, tiles = load_all(d)
    print("settings: TILE_DATABASE v%d, RENDER_PARAMS v%d, CONVERSION_PARAMS v%d"
          % (s["serialise_version"], s["render_params"]["serialise_version"],
             s["conversion_params"]["serialise_version"]))
    print("climates (%d):" % len(s["climates"]))
    for c in s["climates"]:
        print("  %d %-14s rgb=%s v%d textures=%d" % (c["id"], c["name"], c["rgb"],
                                                   c["serialise_version"], len(c["textures"])))
    print("tile sets (%d):" % len(s["tile_sets"]))
    for t in s["tile_sets"]:
        extra = []
        for k in ("linking_tile", "shared_geometry", "also_place_tile_set", "link_as_set"):
            if t[k]:
                extra.append("%s=%s" % (k, t[k]))
        if t["exclude_from_global_mesh"]:
            extra.append("exclude_from_global_mesh")
        print("  %2d %-28s rgb=%-16s %s" % (t["id"], t["name"], t["rgb"], " ".join(extra)))

    print("\ntiles parsed: %d (all to exact EOF)" % len(tiles))
    print("tile versions:", dict(Counter(t["serialise_version"] for t in tiles.values())))
    ts_names = {t["name"] for t in s["tile_sets"]}
    per = Counter(t["tile_set"] for t in tiles.values())
    print("tiles per tile set:")
    for k, n in sorted(per.items(), key=lambda kv: -kv[1]):
        print("  %-28s %d%s" % (k, n, "" if k in ts_names else "  (NOT IN SETTINGS)"))
    T = list(tiles.values())

    def cnt(pred):
        return sum(1 for t in T if pred(t))
    print("tiles with links: %d (total links %d)" % (cnt(lambda t: t["links"]),
                                                     sum(len(t["links"]) for t in T)))
    print("tiles with link targets: %d (total %d)" % (cnt(lambda t: t["link_targets"]),
                                                      sum(len(t["link_targets"]) for t in T)))
    print("tiles with mask: %d (all '0'/'1' strings of length width*height)" % cnt(lambda t: t["mask"]))
    print("tiles with nogo mask: %d  values=%s" % (cnt(lambda t: t.get("nogo")),
                                                   dict(Counter(t["nogo"] for t in T if t.get("nogo")))))
    also = {t["name"]: t["also_place_tile_set"] for t in s["tile_sets"] if t["also_place_tile_set"]}
    print("tiles whose tile set has also_place_tile_set: %d" % cnt(lambda t: t["tile_set"] in also))
    for k in ("requires_infield_lodding", "random_rotatable", "scalable", "encampable",
              "barbarian", "use_alt_lf"):
        print("  %-26s true on %d" % (k, cnt(lambda t, k=k: t.get(k))))
    print("  custom_blend_tile set on %d: %s" % (cnt(lambda t: t["custom_blend_tile"]),
          dict(Counter(t["custom_blend_tile"] for t in T if t["custom_blend_tile"]))))
    print("  custom_alpha_blend_texture set on %d" % cnt(lambda t: t["custom_alpha_blend_texture"]))
    print("sizes (w x h):", dict(Counter("%dx%d" % (t["width"], t["height"]) for t in T)))
    vs = [v for t in T for v in t["variations"]]
    print("variations: %d total; per tile %s" % (len(vs), dict(Counter(len(t["variations"]) for t in T))))
    print("  variation versions:", dict(Counter(v["serialise_version"] for v in vs)))
    print("  texture_set red0 (key) values:", dict(Counter(v["texture_set"]["red0"] for v in vs)))
    print("  texture_set layer values:", dict(Counter(v["texture_set"][k] for v in vs
          for k in ("red0", "green0", "blue0", "alpha0", "red1", "green1", "blue1", "alpha1"))))
    print("  variation rgb:", dict(Counter(v["rgb"] for v in vs)))
    print("tiles with non-0/1 bytes in other bool slots: %d" % cnt(lambda t: t.get("_odd_bool_bytes")))
    print("scalable raw byte: 0 -> %d, 1 -> %d, other (garbage) -> %d"
          % (cnt(lambda t: t["scalable_raw"] == 0), cnt(lambda t: t["scalable_raw"] == 1),
             cnt(lambda t: t["scalable_raw"] > 1)))
    print("tile key (tile_set + '_' + name) == file stem: %s" % all(k == t["key"] for k, t in tiles.items()))
    print("  requires_sea_in_infield true:", sum(1 for v in vs if v["requires_sea_in_infield"]))
    links = [l for t in T for l in t["links"]]
    print("link test enum strings:", dict(Counter(l["test"] for l in links)))
    print("link sets:", dict(Counter(l["link_set"] for l in links)))
    print("link is_entry true: %d; blend_size values %s; no_offline_blend true %d; blend_quad lens %s"
          % (sum(l["is_entry"] for l in links), dict(Counter(l["blend_size"] for l in links)),
             sum(l["no_offline_blend"] for l in links), dict(Counter(len(l["blend_quad"]) for l in links))))
    lts = [l for t in T for l in t["link_targets"]]
    print("link target tile sets:", dict(Counter(l["tile_set"] for l in lts)))


if __name__ == "__main__":
    main(sys.argv)
