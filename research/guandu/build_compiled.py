#!/usr/bin/env python3
"""Compiled-data root for 3k_guandu_map so TerryClone can open it (--map 3k_guandu_map --root <this root>).

  terrain/campaigns/3k_guandu_map/lf_height_map.*, lf_sea_height_map.*, climate_map.cm  <- TerryClone.Cli compile-map
  terrain/campaigns/3k_guandu_map/global_map/global_blend.dds   vanilla blend, nearest crop/scale (same mapping)
  terrain/campaigns/3k_guandu_map/global_map/texture_arrays.xml vanilla copy (same texture groups)
  campaign_maps/3k_guandu_map/display/trees/trees.campaign_tree_list  trees mapped into the new world, outside dropped
"""
import os, sys, shutil, struct, subprocess, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from crop_scale_terrain import src_coords, resample_nearest, NW, NH, NWW, NWH, OW, OH, FULL
from build_ak_project import mx, mz, inside, NAME

VAN = r"Z:/Claude/TerryClone/Vanilla/Map"
ROOT = os.path.join(HERE, "compiled", "Map")
TDIR = os.path.join(ROOT, "terrain", "campaigns", NAME)
CDIR = os.path.join(ROOT, "campaign_maps", NAME, "display", "trees")

def blend():
    src = f"{VAN}/terrain/campaigns/3k_dlc07_main_map/global_map/global_blend.dds"
    b = open(src, "rb").read(); hdr = bytearray(b[:128]); h, w = struct.unpack_from("<II", hdr, 12)
    a = np.frombuffer(b[128:128 + w * h * 2], np.uint8).reshape(h, w, 2)
    W, H = FULL
    out = resample_nearest(a, src_coords(W, NWW, OW, w, "x"), src_coords(H, NWH, OH, h, "z"))
    struct.pack_into("<II", hdr, 12, H, W)
    if struct.unpack_from("<I", hdr, 20)[0]: struct.pack_into("<I", hdr, 20, W * 2)
    os.makedirs(os.path.join(TDIR, "global_map"), exist_ok=True)
    open(os.path.join(TDIR, "global_map", "global_blend.dds"), "wb").write(bytes(hdr) + np.ascontiguousarray(out).tobytes())
    shutil.copy2(f"{VAN}/terrain/campaigns/3k_dlc07_main_map/global_map/texture_arrays.xml", os.path.join(TDIR, "global_map"))

def trees():
    d = open(f"{VAN}/campaign_maps/3k_dlc07_main_map/display/trees/trees.campaign_tree_list", "rb").read()
    ver, a, b, ww, wh, n = struct.unpack_from("<IIIffI", d, 0); p = 24
    out = [struct.pack("<IIIffI", ver, a, b, NWW, NWH, n)]; kept = total = 0
    for _ in range(n):
        ln = struct.unpack_from("<H", d, p)[0]; name = d[p + 2:p + 2 + ln]; p += 2 + ln
        cnt = struct.unpack_from("<I", d, p)[0]; p += 4
        insts = []
        for _ in range(cnt):
            x, y, z, flag, var, sc = struct.unpack_from("<fffBBI", d, p); q = p + 18 + 4 * sc
            total += 1
            nx, nz = mx(x), mz(z)
            if inside(nx, nz): insts.append(struct.pack("<fffBB", nx, y, nz, flag, var) + d[p + 14:q]); kept += 1
            p = q
        out.append(struct.pack("<H", ln) + name + struct.pack("<I", len(insts)) + b"".join(insts))
    assert p == len(d)
    os.makedirs(CDIR, exist_ok=True)
    open(os.path.join(CDIR, "trees.campaign_tree_list"), "wb").write(b"".join(out))
    print(f"trees: kept {kept:,} of {total:,}")


def vanilla_ranges():
    """compile-map normalises each map to its own min-max (as BOB does; the .compressed_map header carries the range).
    TerryClone reads the .dds values directly, so rewrite the two .dds in VANILLA's ranges instead
    (land 0..65535 = identity, sea source 0..44217), which keeps land/sea comparable exactly as on the vanilla map."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    for dds, tif, hi in (("lf_height_map.dds", "lf_heights.tif", 65535), ("lf_sea_height_map.dds", "lf_sea_heights.tif", 44217)):
        path = os.path.join(TDIR, dds); hdr = open(path, "rb").read(128)
        src = np.array(Image.open(os.path.join(HERE, "terrain", tif))).astype(np.float32)
        v = np.clip(np.trunc(src / np.float32(hi) * np.float32(65535)), 0, 65535).astype("<u2")
        assert struct.unpack_from("<II", hdr, 12) == v.shape
        open(path, "wb").write(hdr + v.tobytes())
        print(f"{dds}: vanilla range 0..{hi}, source {int(src.min())}..{int(src.max())}")


if __name__ == "__main__":
    blend(); trees()
    cli = r"Z:/Claude/TerryClone/src/TerryClone.Cli/bin/Debug/net9.0/TerryClone.Cli.exe"
    subprocess.run([cli, "--map", NAME, "compile-map", "--out", ROOT], check=True)
    vanilla_ranges()
