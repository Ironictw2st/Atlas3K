#!/usr/bin/env python3
"""Per-map files for campaign_maps/3k_dlc07_main_map of the reworked 190E map (Guandu's build_map_extras.py
generalised to the warp). Output: research/main190/map_extras/campaign_maps/3k_dlc07_main_map/

 painted maps (190E's, 4.3 px/hex; minimap is a palette PNG): 3K_overlay_map.dds, 3k_main_minimap.png,
   three_kingdoms_china_map.png, campaign_map_multiplayer.png, campaign_map_records.png (+ vanilla's
   custom_battle_map.png): warped with the band warp to the new lookup size; the west/north padding is painted in
   the same parchment style (base colour sampled from 190E's own non-playable parchment, relief from our heights,
   mountains tinted like the painted ones, sea from the painted sea); borders of the new ironic_central / hexi /
   nomad regions are drawn in the painted border colour
 3k_main_lookup.{tga,dds}, 3k_main_lookup_minimap.tga: BOB's conversion of CAIME's lookup, renamed to the names
   campaign_map_playable_areas references
 camera_heightmap.png: Atlas3K build-campaign camera_heightmap (tile-map size, height_scale tEXt)
 display/trees/trees.campaign_tree_list: 190E's tree instances moved with the warp (heights unchanged: the
   terrain was warped the same way)
"""
import os, shutil, struct, sys
from pathlib import Path
import numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent, HERE.parent.parent / "output" / "pylibs"): sys.path.insert(0, str(p))
import tifffile
import crop_scale_map_hex as C, hexmap
from rebuild_hex import unpack
from hexgrid import nearest_hex
from warp import Warp, WarpMapping, current
from terrain_main import FULL, NWW, NWH, OW, OH
from build_map_extras import save_dds_rgba

SRC = HERE / "source" / "campaign_maps" / "3k_dlc07_main_map"
VAN = Path(r"Z:/Claude/TerryClone/Vanilla/Map/campaign_maps/3k_dlc07_main_map")
NEWMAP = "3k_190e_expanded_map"
WORK = Path(r"C:/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/assembly_kit_190E/working_data/campaign_maps") / NEWMAP
OUT = HERE / "map_extras" / "campaign_maps" / NEWMAP
W0, H0 = 892, 702
WARP = current(); MAP = WarpMapping(WARP)
BORDER = np.array([72, 60, 46], np.float32)
NEW_PREFIX = ("ironic_central_", "ironic_hexi_", "ironic_nomad_")
# round 6: regions whose shape changed (relocated 190E Hexi regions) get their borders / icons redrawn too
EXTRA_KEYS = set()


def is_new(key):
    return key.startswith(NEW_PREFIX) or key in EXTRA_KEYS


def src_maps(size, src_size, chunk=256):
    """Old-image pixel coordinates for every output pixel (any warp, 2-D) and the padding mask."""
    Wo, Ho = size; Ws, Hs = src_size
    xs = np.empty((Ho, Wo), np.float32); ys = np.empty((Ho, Wo), np.float32)
    hx = (np.arange(Wo) + 0.5) / Wo * WARP.W
    for r0 in range(0, Ho, chunk):
        r1 = min(Ho, r0 + chunk); hy = (1 - (np.arange(r0, r1) + 0.5) / Ho) * WARP.H
        X, Y = np.broadcast_arrays(hx[None, :], hy[:, None]); ox, oy = WARP.inverse(X, Y)
        xs[r0:r1] = ox / W0 * Ws - 0.5; ys[r0:r1] = (1 - oy / H0) * Hs - 0.5
    return xs, ys, (xs < -0.5) | (xs > Ws - 0.5) | (ys < -0.5) | (ys > Hs - 0.5)


_MAPS = {}


def bilinear(a, xs, ys, chunk=256):
    out = np.empty(xs.shape + a.shape[2:], np.float32); a = a.astype(np.float32)
    for r0 in range(0, xs.shape[0], chunk):
        x = xs[r0:r0 + chunk]; y = ys[r0:r0 + chunk]
        x0 = np.clip(np.floor(x).astype(int), 0, a.shape[1] - 2); y0 = np.clip(np.floor(y).astype(int), 0, a.shape[0] - 2)
        fx = np.clip(x - x0, 0, 1)[..., None]; fy = np.clip(y - y0, 0, 1)[..., None]
        top = a[y0, x0] * (1 - fx) + a[y0, x0 + 1] * fx; bot = a[y0 + 1, x0] * (1 - fx) + a[y0 + 1, x0 + 1] * fx
        out[r0:r0 + chunk] = top * (1 - fy) + bot * fy
    return out


def relief(size):
    """Hillshade (0.75..1.2) and normalised height (0..1, sea < 0) at image size, from our height raster."""
    H = tifffile.imread(str(HERE / "terrain" / "3k_dlc07_main_map.height.191fd803c1a801d.tif"))[::2, ::2].astype(np.float32)
    im = np.array(Image.fromarray(H).resize(size, Image.BILINEAR))
    gy, gx = np.gradient(im / 1500.0)
    shade = np.clip(1.0 + (-gx + gy) * 0.06, 0.94, 1.04)
    return shade, (im - 14220) / (60000 - 14220)


def region_edges(size, names, f):
    """Pixels on a border that involves a new region (either side)."""
    Wo, Ho = size; w, h = f["region"].shape[1], f["region"].shape[0]
    new = np.array([is_new(n) for n in names] + [False])
    npl = names.index("3k_main_reg_non_playable")
    edge = np.zeros((Ho, Wo), bool); prev = None
    x = (np.arange(Wo) + 0.5) / Wo * NWW * (WARP.W * 0.668 / NWW)          # hex-world x across the image
    for r0 in range(0, Ho, 256):
        r1 = min(Ho, r0 + 256)
        z = (1 - (np.arange(r0, r1) + 0.5) / Ho) * WARP.H * 0.772
        X, Z = np.broadcast_arrays(x[None, :], z[:, None])
        c, r = nearest_hex(X, Z, w, h)
        reg = f["region"][np.clip(r, 0, h - 1), np.clip(c, 0, w - 1)]
        land = f["terr"][np.clip(r, 0, h - 1), np.clip(c, 0, w - 1)] != 1
        isnew = new[np.clip(reg, -1, len(names) - 1)]
        land = land & (reg != npl)
        e = np.zeros_like(land)
        e[:, 1:] |= (reg[:, 1:] != reg[:, :-1]) & (isnew[:, 1:] | isnew[:, :-1]) & land[:, 1:] & land[:, :-1]
        e[1:, :] |= (reg[1:, :] != reg[:-1, :]) & (isnew[1:, :] | isnew[:-1, :]) & land[1:, :] & land[:-1, :]
        if prev is not None:
            e[0, :] |= (reg[0, :] != prev[0]) & (isnew[0, :] | prev[1]) & land[0, :] & prev[2]
        prev = (reg[-1, :].copy(), isnew[-1, :].copy(), land[-1, :].copy())
        edge[r0:r1] = e
    return edge


def region_mask(size, names, f):
    """Pixels over land of the new regions."""
    Wo, Ho = size; w, h = f["region"].shape[1], f["region"].shape[0]
    new = np.array([is_new(n) for n in names] + [False])
    x = (np.arange(Wo) + 0.5) / Wo * WARP.W * 0.668; out = np.zeros((Ho, Wo), bool)
    for r0 in range(0, Ho, 256):
        r1 = min(Ho, r0 + 256); z = (1 - (np.arange(r0, r1) + 0.5) / Ho) * WARP.H * 0.772
        X, Z = np.broadcast_arrays(x[None, :], z[:, None]); c, r = nearest_hex(X, Z, w, h)
        c = np.clip(c, 0, w - 1); r = np.clip(r, 0, h - 1)
        out[r0:r1] = new[np.clip(f["region"][r, c], -1, len(names) - 1)] & (f["terr"][r, c] != 1)
    return out


def town_px(size, names, f, key):
    m = (f["region"] == names.index(key)) & (f["slot"] == 0)
    r, c = np.argwhere(m).mean(0)
    x = c * 0.668 / (WARP.W * 0.668) * size[0]; z = r * 0.772 + (int(round(c)) & 1) * 0.386
    return int(round(x)), int(round((1 - z / (WARP.H * 0.772)) * size[1]))


def stamp_icons(out, size, names, f):
    """Copy the painted town icon of an existing capital / resource town onto every new town (icon pixels only:
    those that differ from the parchment around them)."""
    tpl = {}
    for kind, key in (("capital", "3k_main_chenjun_capital"), ("resource", "3k_main_chenjun_resource_1")):
        x, y = town_px(size, names, f, key); R = max(14, round(size[0] / 280))
        patch = out[y - R:y + R + 1, x - R:x + R + 1].copy()
        bg = np.median(np.concatenate([patch[0], patch[-1], patch[:, 0], patch[:, -1]]), 0)
        mask = np.abs(patch[..., :3] - bg[:3]).sum(-1) > 60
        tpl[kind] = (patch, mask, R)
    n = 0
    for i, key in enumerate(names):
        if not is_new(key) or not ((f["region"] == i) & (f["slot"] == 0)).any(): continue
        patch, mask, R = tpl["capital" if key.endswith("_capital") else "resource"]
        x, y = town_px(size, names, f, key)
        if R <= x < size[0] - R and R <= y < size[1] - R:
            dst = out[y - R:y + R + 1, x - R:x + R + 1]; dst[mask] = patch[mask]; n += 1
    return n


def warp_painted(src_img, size, names, f, shade, hn, is_palette=False):
    a = np.array(src_img.convert("RGBA")); Hs, Ws = a.shape[:2]
    key = (size, (Ws, Hs))
    if key not in _MAPS: _MAPS[key] = src_maps(size, (Ws, Hs))
    xs, ys, pad = _MAPS[key]
    out = bilinear(a, xs, ys)
    # parchment: the painting's own colours next to the seam, spread smoothly outward (heavy box blur of the
    # edge-clamped warp), lightly shaded by our relief; mountains tinted a little, sea from the painted sea
    from dem_fill import box3
    al = out[..., 3] / 255.0
    den = box3(np.ascontiguousarray(al.astype(np.float32)), 40)
    base = np.stack([box3(np.ascontiguousarray((out[..., k] * al).astype(np.float32)), 40) for k in range(3)], -1) / np.maximum(den, 1e-3)[..., None]
    seac = np.median(a[int(Hs * .55):int(Hs * .75), int(Ws * .8):int(Ws * .95), :3].reshape(-1, 3), 0).astype(np.float32)
    mtn = np.array([150, 118, 88], np.float32)
    t = np.clip((hn - 0.45) / 0.4, 0, 1)[..., None] * 0.35
    paint = (base * (1 - t) + mtn * t) * shade[..., None]
    paint = np.where((hn < 0)[..., None], seac, paint)
    # feather the seam: distance (px) into the padding
    dx = np.maximum(np.maximum(-0.5 - xs, xs - (Ws - 0.5)), 0); dy = np.maximum(np.maximum(-0.5 - ys, ys - (Hs - 0.5)), 0)
    d = np.maximum(dx, dy) * (size[0] / Ws)
    wgt = np.clip(d / 120.0, 0, 1)[..., None]; wgt = wgt * wgt * (3 - 2 * wgt)
    # padding: smooth base colour ramping into the shaded paint (never the raw edge-clamped pixels, which streak)
    inpad = pad[..., None]
    padval = base * (1 - wgt) + paint * wgt
    out[..., :3] = np.where(inpad, np.clip(padval, 0, 255), out[..., :3])
    # alpha in the padding: the painting's edge coverage, smoothed; opaque over the new regions
    # vignette images (frontend maps: soft transparent frame) keep the padding transparent; opaque maps are painted
    vignette = (a[..., 3] < 250).mean() > 0.02
    out[..., 3] = np.where(pad, 0 if vignette else 255, out[..., 3])
    e = region_edges(size, names, f)
    k = max(1, round(size[0] / 2400))                                  # painted borders are ~3 px at this size
    ee = e.copy()
    for dy in range(-k, k + 1):
        for dx in range(-k, k + 1):
            if dx * dx + dy * dy <= k * k: ee |= np.roll(np.roll(e, dy, 0), dx, 1)
    out[ee, :3] = out[ee, :3] * 0.15 + BORDER * 0.85
    stamp_icons(out, size, names, f)
    return Image.fromarray(np.clip(out + 0.5, 0, 255).astype(np.uint8), "RGBA")


def trees():
    """2026-10-02: the tree list is built natively from the decoded-vanilla CampaignTree raster (trees_x15.py writes it
    into terrain/ and the kit) - `Atlas3K.Cli build-campaign --steps rasters,trees`; trees_190e_moved() is the old way."""
    import subprocess, shutil
    cli = r"Z:/Claude/TerryClone/src/Atlas3K.Cli/bin/Release/net9.0/Atlas3K.Cli.exe"
    ak = r"C:/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/assembly_kit_190E"
    outw = HERE / "build_newmap"
    r = subprocess.run([cli, "build-campaign", "--steps", "rasters,trees", "--ak", ak, "--map", "3k_190e_expanded_map", "--out", str(outw)],
                       capture_output=True, text=True)
    print("\n".join(l for l in r.stdout.splitlines() if "trees" in l or "note" in l))
    src = outw / "campaign_maps" / "3k_190e_expanded_map" / "display" / "trees" / "trees.campaign_tree_list"
    assert r.returncode == 0 and src.exists(), r.stdout[-500:]
    (OUT / "display" / "trees").mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, OUT / "display" / "trees" / "trees.campaign_tree_list")


def trees_190e_moved():
    d = (SRC / "display" / "trees" / "trees.campaign_tree_list").read_bytes()
    ver, a, b, ww, wh, n = struct.unpack_from("<IIIffI", d, 0); p = 24
    out = [struct.pack("<IIIffI", ver, a, b, NWW, NWH, n)]; total = 0
    for _ in range(n):
        ln = struct.unpack_from("<H", d, p)[0]; name = d[p + 2:p + 2 + ln]; p += 2 + ln
        cnt = struct.unpack_from("<I", d, p)[0]; p += 4; insts = []
        for _ in range(cnt):
            x, y, z, flag, var, sc = struct.unpack_from("<fffBBI", d, p); q = p + 18 + 4 * sc
            nx, nz = MAP.fwd_world(x, z)
            insts.append(struct.pack("<fffBB", float(nx), y, float(nz), flag, var) + d[p + 14:q]); total += 1; p = q
        out.append(struct.pack("<H", ln) + name + struct.pack("<I", len(insts)) + b"".join(insts))
    assert p == len(d)
    (OUT / "display" / "trees").mkdir(parents=True, exist_ok=True)
    (OUT / "display" / "trees" / "trees.campaign_tree_list").write_bytes(b"".join(out))
    print(f"trees: {total:,} instances moved, header world {NWW:.3f} x {NWH:.3f} (was {ww:.3f} x {wh:.3f})")
    from tree_clear import tree_mask, filter_tree_list                 # no trees in / near settlements and roads
    m, wh_ = tree_mask(); filter_tree_list(OUT / "display" / "trees" / "trees.campaign_tree_list", m, wh_)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    mh = HERE / "hex" / "map.hex"; src = mh.read_bytes(); P, w, h = C.locate_dims(src)
    f = unpack(np.frombuffer(src, np.uint8, 16 * w * h, P + 8).reshape(h, w, 16))
    L = hexmap.load(str(mh))["lists"]; names = L["land_regions"] + L["sea_regions"]
    size = Image.open(WORK / "3k_main_campaign_map_lookup.tga").size       # CAIME/BOB lookup of the new map
    shade, hn = relief(size)
    for n in ("three_kingdoms_china_map.png", "campaign_map_multiplayer.png", "campaign_map_records.png"):
        warp_painted(Image.open(SRC / n), size, names, f, shade, hn).save(OUT / n); print(n, size)
    cb = VAN / "custom_battle_map.png"
    if cb.exists():
        warp_painted(Image.open(cb), size, names, f, shade, hn).save(OUT / "custom_battle_map.png"); print("custom_battle_map.png", size)
    save_dds_rgba(warp_painted(Image.open(SRC / "3K_overlay_map.dds"), size, names, f, shade, hn), OUT / "3K_overlay_map.dds")
    print("3K_overlay_map.dds", size)
    mm = Image.open(SRC / "3k_main_minimap.png")
    rgba = warp_painted(mm, size, names, f, shade, hn)
    pal_img = Image.new("P", (1, 1)); pal_img.putpalette(mm.getpalette())
    rgba.convert("RGB").quantize(palette=pal_img, dither=Image.Dither.NONE).save(OUT / "3k_main_minimap.png"); print("3k_main_minimap.png", size)
    # (lookups and camera_heightmap are staged separately from CAIME/BOB and build-campaign output)
    trees()
    for root, _, fs in os.walk(OUT):
        for fn in fs:
            q = os.path.join(root, fn); print(f"  {os.path.relpath(q, OUT):48s} {os.path.getsize(q):>12,}")


if __name__ == "__main__":
    main()
