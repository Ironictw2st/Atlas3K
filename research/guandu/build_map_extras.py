#!/usr/bin/env python3
"""The per-map files vanilla ships in campaign_maps/<map>/ besides map_data/pathfinding/trade routes/borders, made
without BOB (its camera-heightmap action crashes on this map).

Every vanilla image is proportional to the hex grid (px = k * hexes, k per image), so each is cropped to the Guandu
window (COL0..COL1, ROW0..ROW1 of the vanilla hex grid; image rows are north-up) and resized to k * our hex size.

 camera_heightmap.png            16-bit, 2 px/hex, from vanilla's (our terrain heights are vanilla's cropped+scaled)
 3k_overlay_map.dds, 3k_main_minimap.png, three_kingdoms_china_map.png, campaign_map_multiplayer.png,
 campaign_map_records.png, custom_battle_map.png            visual images, cropped from vanilla
 3k_main_lookup.tga/.dds, 3k_main_lookup_minimap.tga        region lookup: copies of the CAIME->BOB outputs
                                                            (3k_guandu_start_pos_lookup*), renamed to what our
                                                            campaign_map_playable_areas row references
 display/area_of_interest_spline.dds, display/borders/textures/*   vanilla textures, unchanged
 display/trees/trees.campaign_tree_list                     ours, from the compiled root

Output: research/guandu/map_extras/campaign_maps/3k_guandu_map/
"""
import os, shutil
import numpy as np
from PIL import Image
import crop_scale_map_hex as C

Image.MAX_IMAGE_PIXELS = None
HERE = os.path.dirname(os.path.abspath(__file__))
VAN = os.path.join(HERE, "vanilla_mapfiles", "campaign_maps", "3k_dlc07_main_map")
WORK = r"C:/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/assembly_kit/working_data/campaign_maps/3k_guandu_map"
TREES = os.path.join(HERE, "compiled", "Map", "campaign_maps", "3k_guandu_map", "display", "trees", "trees.campaign_tree_list")
OUT = os.path.join(HERE, "map_extras", "campaign_maps", "3k_guandu_map")
NW, NH = C.NW, C.NH


def crop(im, Wv, Hv, resample=Image.BICUBIC):
    kx, ky = im.size[0] / Wv, im.size[1] / Hv
    box = (C.COL0 * kx, (Hv - C.ROW1) * ky, C.COL1 * kx, (Hv - C.ROW0) * ky)
    return im.resize((round(NW * kx), round(NH * ky)), resample, box=box)


def save_dds_rgba(im, path):
    """Uncompressed 32-bit BGRA DDS, no mips (the game reads it; vanilla's BC7 is only a size optimisation)."""
    im = im.convert("RGBA"); w, h = im.size
    a = np.array(im)[..., [2, 1, 0, 3]].tobytes()
    hdr = bytearray(128)
    hdr[0:4] = b"DDS "
    import struct
    struct.pack_into("<7I", hdr, 4, 124, 0x1 | 0x2 | 0x4 | 0x1000 | 0x8, h, w, w * 4, 0, 1)
    struct.pack_into("<2I4s5I", hdr, 76, 32, 0x41, b"\0\0\0\0", 32, 0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000)
    struct.pack_into("<I", hdr, 108, 0x1000)
    open(path, "wb").write(bytes(hdr) + a)


def main():
    src = open(C.VANILLA, "rb").read(); _, Wv, Hv = C.locate_dims(src)
    os.makedirs(OUT, exist_ok=True)
    # camera heightmap, 16-bit
    v = np.array(Image.open(os.path.join(VAN, "camera_heightmap.png"))).astype(np.int32)
    a = np.array(crop(Image.fromarray(v).convert("I"), Wv, Hv))
    Image.fromarray(np.clip(a, 0, 65535).astype(np.uint16)).save(os.path.join(OUT, "camera_heightmap.png"))
    # visual images
    for n in ("3k_main_minimap.png", "three_kingdoms_china_map.png", "campaign_map_multiplayer.png",
              "campaign_map_records.png", "custom_battle_map.png"):
        im = Image.open(os.path.join(VAN, n)); crop(im, Wv, Hv).save(os.path.join(OUT, n))
    save_dds_rgba(crop(Image.open(os.path.join(VAN, "3k_overlay_map.dds")).convert("RGBA"), Wv, Hv),
                  os.path.join(OUT, "3k_overlay_map.dds"))
    # region lookup (CAIME bmp -> BOB tga/dds), renamed
    for s, d in (("3k_guandu_start_pos_lookup.tga", "3k_main_lookup.tga"), ("3k_guandu_start_pos_lookup.dds", "3k_main_lookup.dds"),
                 ("3k_guandu_start_pos_lookup_minimap.tga", "3k_main_lookup_minimap.tga")):
        shutil.copy2(os.path.join(WORK, s), os.path.join(OUT, d))
    # display textures + our tree list
    for rel in ("display/area_of_interest_spline.dds", "display/borders/textures/border_diffuse.dds",
                "display/borders/textures/border_dotted_diffuse.dds", "display/borders/textures/border_internal_diffuse.dds"):
        os.makedirs(os.path.dirname(os.path.join(OUT, rel)), exist_ok=True)
        shutil.copy2(os.path.join(VAN, rel), os.path.join(OUT, rel))
    os.makedirs(os.path.join(OUT, "display", "trees"), exist_ok=True)
    shutil.copy2(TREES, os.path.join(OUT, "display", "trees", "trees.campaign_tree_list"))
    for root, _, fs in os.walk(OUT):
        for f in fs:
            p = os.path.join(root, f); print(os.path.relpath(p, OUT), os.path.getsize(p))


if __name__ == "__main__":
    main()
