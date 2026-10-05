#!/usr/bin/env python3
"""Jeju after jeju_scale.py (user 2026-10-02: coast holes + both Tamna towns without city bars).
1. coast ring on Jeju only: scaling doubled the beach / cliff ring - coast hexes not touching sea become plain land
   (beach ground of the island interior), then coast hexes not touching plain land become sea (the island's sea region);
   repeated until stable; cliff -> cliff end where it touches beach is left to the tile map's coast rule.
2. towns: town_move_x15.py moves Mugeun-seong and Seobul 3+ hexes clear of sea / beach / cliff / river / impassable
   (the pre-scale fix that gave Mugeun-seong its bar back), then jeju_post.py redraws the road between them."""
import shutil, struct, subprocess, sys, time, zlib
from pathlib import Path
import numpy as np
from scipy import ndimage as ndi
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
import town_fix as T
from hexgrid import neighbour_arrays
TOWNS = ["ironic_region_tamna_capital", "ironic_region_baek_resource_1"]


def coast():
    HEX = HERE / "hex" / "map.hex"
    shutil.copy2(HEX, HERE / "hex" / f"map_pre_jejufix_{time.strftime('%Y%m%d_%H%M%S')}.hex")
    b, P, w, h, g, f, names = T.load(str(HEX)); NA = neighbour_arrays(h, w); G = g.copy()
    land = f["terr"] != 1
    lab, _ = ndi.label(land)
    k0 = names.index(TOWNS[0]); rr, cc = np.nonzero((f["slot"] == 0) & (f["region"] == k0))
    isl = lab == lab[rr[0], cc[0]]
    zone = ndi.binary_dilation(isl, iterations=2)
    sea_reg = int(np.bincount(f["region"][zone & ~land]).argmax())
    plain_ground = int(np.bincount(f["ground"][isl & (f["terr"] == 0)] + 1).argmax()) - 1
    terr = f["terr"].copy(); town = (f["slot"] >= 0) | (f["sprawl"] > 0)
    to_land = to_sea = 0
    for _ in range(4):
        ns = np.zeros((h, w), bool); nl = np.zeros((h, w), bool)
        for nr, nc, v in NA: ns |= v & (terr[nr, nc] == 1); nl |= v & (terr[nr, nc] == 0)
        a = zone & np.isin(terr, [2, 3]) & ~ns                     # inner coast: becomes land
        terr[a] = 0; to_land += int(a.sum())
        ns = np.zeros((h, w), bool); nl = np.zeros((h, w), bool)
        for nr, nc, v in NA: ns |= v & (terr[nr, nc] == 1); nl |= v & (terr[nr, nc] == 0)
        s_ = zone & np.isin(terr, [2, 3]) & ~nl & ~town            # outer coast with no land behind: sea
        terr[s_] = 1; to_sea += int(s_.sum())
        if not a.any() and not s_.any(): break
    ch = zone & (terr != f["terr"])
    for r, c in zip(*np.nonzero(ch)):
        t = int(terr[r, c])
        G[r, c, 0] = (G[r, c, 0] & 0xFC) | t
        if t == 0:
            gt = plain_ground + 1
            G[r, c, 5] = (G[r, c, 5] & 0x0F) | ((gt & 15) << 4); G[r, c, 6] = (G[r, c, 6] & 0xF8) | ((gt >> 4) & 7)
        if t == 1:                                                  # sea hex: the island's sea region, impassable, no lines
            reg = sea_reg + 1
            G[r, c, 0] = (G[r, c, 0] & 0x07) | ((reg & 0x1F) << 3) | 1; G[r, c, 1] = (reg >> 5) & 0xFF
            G[r, c, 2] = (G[r, c, 2] & 0x0F) | 0x08; G[r, c, 3] = 0; G[r, c, 4] &= 0xC0
    out = bytearray(b); out[P + 8:P + 8 + 16 * w * h] = G.tobytes()
    out[-4:] = struct.pack("<I", zlib.crc32(bytes(out[:-4])) & 0xFFFFFFFF); HEX.write_bytes(bytes(out))
    # a sea region change needs the region edge bits (b15) recomputed
    from rebuild_hex import unpack, pack
    b2, P2, w, h, g2, f2, _ = T.load(str(HEX))
    reg = f2["region"]; redge = np.zeros((h, w), np.int32)
    for d, (nr, nc, v) in enumerate(NA): redge |= ((v & (reg[nr, nc] != reg)).astype(np.int32) << d)
    f2["redge"] = redge; o = pack(f2); o[..., 10:15] = g2[..., 10:15]
    out = bytearray(b2); out[P2 + 8:P2 + 8 + 16 * w * h] = o.tobytes()
    out[-4:] = struct.pack("<I", zlib.crc32(bytes(out[:-4])) & 0xFFFFFFFF); HEX.write_bytes(bytes(out))
    print(f"jeju coast: {to_land} inner coast hexes -> land, {to_sea} stray coast hexes -> sea")


if __name__ == "__main__":
    coast()
    subprocess.run([sys.executable, str(HERE / "town_move_x15.py")] + TOWNS, check=True)
    subprocess.run([sys.executable, str(HERE / "jeju_post.py")], check=True)
