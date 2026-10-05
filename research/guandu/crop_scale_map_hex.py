#!/usr/bin/env python3
"""Crop a 3K map.hex to the Guandu box, then nearest-neighbour upscale it (all layers at once).

Reuses Z:/Claude/CAIME/scale_map_hex.py (dims locate, record scaling, CRC32 footer).
Hex grid: flat-top hexes, column-offset (0.668 x 0.772 world per hex), row 0 = SOUTH edge,
8 heightmap px per hex. Crop must start on an even column to keep the column-offset parity.

Usage: python crop_scale_map_hex.py [--scale 2.25] [--in map.hex] [--out DIR]
"""
import argparse, struct, sys, zlib
from pathlib import Path
import numpy as np

sys.path.insert(0, r"Z:/Claude/CAIME")
from scale_map_hex import locate_dims, scale_records, verify, STRIDE

VANILLA = r"C:/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/assembly_kit/raw_data/EmpireDesignData/campaign_maps/3k_dlc07_main_map/map.hex"
# Guandu box: west edge takes in Jincheng + Wuwei (Wuwei capital starts at col 125), south edge just below the
# Yangtze's lowest bend (world z 250), north/east as crop_preview.py. hex col = x / 0.668, hex row = z / 0.772.
COL0, COL1 = 120, 710          # [COL0, COL1), even start + even width
ROW0, ROW1 = 323, 672          # [ROW0, ROW1), south-origin hex rows
SCALE = 2.25
# Scaled map size. Both are multiples of 4 hexes: the tile map is 2 px per hex and BOB lays the global meshes on a
# 16-column grid of tile-map width / 16 (vanilla 892 hexes -> 1784 px = 16 x 111.5). A width that does not divide
# (1094 -> 2188 px) made BOB build a 17th mesh column past the map edge ("Building mesh 272 of 256") and left
# see-through notches beside every road tile in game.
NW = 4 * round((COL1 - COL0) * SCALE / 4)
NH = 4 * round((ROW1 - ROW0) * SCALE / 4)


def rename(prefix, name):
    """Replace the campaign map name in the header prefix (u32 x4, then u32-length game, u32-length map name) -
    the same single field CAIME's Rename changes. CAIME writes outputs to working_data/campaign_maps/<name>."""
    p = 16; glen = struct.unpack_from("<I", prefix, p)[0]; p += 4 + glen
    nlen = struct.unpack_from("<I", prefix, p)[0]
    nb = name.encode("ascii")
    return prefix[:p] + struct.pack("<I", len(nb)) + nb + prefix[p + 4 + nlen:]


def region_of(g):
    """Region index per hex (CAIME MapHexFile.ReadHexData: 13 bits, byte0 >> 3 low, byte1 high; -1 = none)."""
    return ((g[..., 1].astype(np.int32) << 5) | (g[..., 0].astype(np.int32) >> 3)) - 1


def fix_orphans(full, crop):
    """Regions the crop cut away from their town slot(s) crash CA's map-data builder (a region must keep its
    settlement). Their leftover hexes go to the nearest region that kept its slots (land to land, sea to sea);
    orphaned land becomes impassable with no town sprawl - the off-map fringe south of the Yangtze / west edge.
    Returns the fixed crop and the orphan region indices."""
    crop = crop.copy()
    slot_full, slot_crop = full[..., 2] >> 4, crop[..., 2] >> 4           # town slot index + 1 (0 = none)
    reg_full, reg = region_of(full), region_of(crop)
    # any cut into a settlement footprint counts (a partly-cut slot also crashes the builder), so compare the
    # number of hexes per slot index, not just which slots exist
    def slot_counts(slots):
        v, n = np.unique(slots[slots > 0], return_counts=True)
        return dict(zip(v.tolist(), n.tolist()))
    orphans = [r for r in np.unique(reg) if r >= 0 and
               slot_counts(slot_full[reg_full == r]) != slot_counts(slot_crop[reg == r])]
    # settlements inside the edge frame would be made impassable by frame_edges: treat them as cut too
    band = np.zeros(reg.shape, bool); band[:3, :] = band[-3:, :] = True; band[:, :3] = band[:, -3:] = True
    orphans = sorted(set(orphans) | set(np.unique(reg[band & (slot_crop > 0)]).tolist()) - {-1})
    bad = np.isin(reg, orphans)
    sea = (crop[..., 0] & 3) == 1
    h, w = reg.shape
    # nearest good region by multi-source BFS over the grid, kept within the same land/sea class
    from collections import deque
    new = reg.copy(); seen = ~bad; q = deque(zip(*np.nonzero(~bad)))
    while q:
        y, x = q.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and not seen[ny, nx] and sea[ny, nx] == sea[y, x]:
                seen[ny, nx] = True; new[ny, nx] = new[y, x]; q.append((ny, nx))
    left = bad & ~seen                                   # no same-class path: any nearest region
    if left.any():
        q = deque(zip(*np.nonzero(seen)))
        while q:
            y, x = q.popleft()
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w and not seen[ny, nx]:
                    seen[ny, nx] = True; new[ny, nx] = new[y, x]; q.append((ny, nx))
    ri = (new[bad] + 1).astype(np.int32)
    crop[..., 0][bad] = ((ri & 0x1F) << 3) | (crop[..., 0][bad] & 0b111)
    crop[..., 1][bad] = ri >> 5
    # water with no path to a kept sea region (cut-off river-sea strips) was handed a land region: make it land
    # (impassable mountain) so region and terrain agree
    dry = left & sea
    if dry.any():
        crop[..., 0][dry] &= 0b11111100
        gt = 8 + 1                                       # 'mountain' ground type index + 1
        crop[..., 5][dry] = (crop[..., 5][dry] & 0x0F) | ((gt & 15) << 4)
        crop[..., 6][dry] = (crop[..., 6][dry] & 0xF8) | ((gt >> 4) & 7)
        sea = sea & ~dry
    land = bad & ~sea
    crop[..., 2][land] |= 0b1000                        # impassable
    crop[..., 2][bad] &= 0b00001111                     # leftover town slot hexes of the cut settlement
    crop[..., 3][bad] &= 0b11111110                     # no town sprawl
    return crop, orphans


def frame_edges(crop, width=2):
    """Vanilla's map edge is never playable; a crop leaves passable land, roads and rivers running off the edge.
    Make a frame of `width` hexes impassable and clear roads, bridges, rivers, trade routes and town sprawl in it
    (town slots are left alone - regions cut through their slots were already handled by fix_orphans)."""
    crop = crop.copy()
    edge = np.zeros(crop.shape[:2], bool)
    edge[:width, :] = edge[-width:, :] = True
    edge[:, :width] = edge[:, -width:] = True
    land = edge & ((crop[..., 0] & 3) != 1)
    crop[..., 2][land] |= 0b1000                    # impassable
    crop[..., 3][edge] = 0                          # bridge, road edge mask, town sprawl
    crop[..., 4][edge] = 0                          # river edge mask + trade route low bits
    crop[..., 5][edge] &= 0b11110000                # trade route high bits (keep ground type)
    return crop


def drop_broken_bridges(before, after):
    """A bridge whose hexes were touched by the fixes (made impassable, framed) can lose one side, which breaks
    CAIME's pathfinding (empty bridge part). Remove every connected bridge that touches a changed hex."""
    after = after.copy()
    bridge = (after[..., 3] >> 7) == 1
    changed = np.any(before[..., :6] != after[..., :6], axis=-1)
    near = changed.copy()                               # changed hexes plus their neighbours
    near[1:] |= changed[:-1]; near[:-1] |= changed[1:]; near[:, 1:] |= changed[:, :-1]; near[:, :-1] |= changed[:, 1:]
    h, w = bridge.shape; seen = np.zeros_like(bridge); removed = 0
    for y, x in zip(*np.nonzero(bridge)):
        if seen[y, x]: continue
        comp, stack = [], [(y, x)]; seen[y, x] = True
        while stack:
            cy, cx = stack.pop(); comp.append((cy, cx))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < h and 0 <= nx < w and bridge[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True; stack.append((ny, nx))
        if any(near[p] for p in comp):
            for p in comp: after[p[0], p[1], 3] &= 0b01111111
            removed += 1
    return after, removed


def crop_scale(mh, scale, name=None, fix=True):
    P, w, h = locate_dims(mh)
    grid = np.frombuffer(mh, np.uint8, STRIDE * w * h, P + 8).reshape(h, w, STRIDE)
    crop = grid[ROW0:ROW1, COL0:COL1]
    if fix:
        raw = crop
        crop, orphans = fix_orphans(grid, crop)
        crop = frame_edges(crop)
        crop, bridges = drop_broken_bridges(raw, crop)
        print(f"orphaned regions (lost their town slots to the crop): {len(orphans)}; bridges removed: {bridges}")
    cw, ch = crop.shape[1], crop.shape[0]
    nw = round(cw * scale); nw -= nw % 2            # CAIME wants even width
    nh = round(ch * scale)
    out = np.ascontiguousarray(scale_records(crop, cw, ch, nw, nh))
    prefix = rename(mh[:P], name) if name else mh[:P]
    body = prefix + struct.pack("<II", nw, nh) + out.tobytes()
    res = body + struct.pack("<I", zlib.crc32(body) & 0xFFFFFFFF)
    verify(res, (cw, ch), (nw, nh))
    return res, (w, h), (cw, ch), (nw, nh)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=float, default=2.25)
    ap.add_argument("--in", dest="src", default=VANILLA)
    ap.add_argument("--out", default=str(Path(__file__).parent / "hex"))
    ap.add_argument("--name", default="3k_guandu_map", help="campaign map name written into the header")
    a = ap.parse_args()
    res, src, crop, new = crop_scale(Path(a.src).read_bytes(), a.scale, a.name)
    out = Path(a.out) / f"map_x{a.scale:g}"; out.mkdir(parents=True, exist_ok=True)
    (out / "map.hex").write_bytes(res)
    nw, nh = new
    print(f"source {src[0]}x{src[1]} -> crop {crop[0]}x{crop[1]} (cols {COL0}-{COL1-1}, rows {ROW0}-{ROW1-1})"
          f" -> x{a.scale:g} = {nw}x{nh} = {nw*nh:,} hexes")
    print(f"world {(nw-1)*0.668:.1f} x {(nh-1)*0.772:.1f} units | heightmap {nw*8} x {nh*8} px")
    print(f"written {out/'map.hex'} ({len(res):,} bytes)")
