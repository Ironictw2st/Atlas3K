"""SUPERSEDED (2026-09-27): don't use this. The premise was wrong. The compiled sea values are the source scaled by
65535/44217, not "spread" water. The correct source is the DDS x 44217/65535 (see compressed_map.py and
docs/bob_campaign_build.md section 2).

Rebuild a Terry source sea-height map from BOB's compiled lf_sea_height_map.dds.

The compiled map is not what was painted in Terry: BOB spreads the sea surface out past the water, so near the
coasts and along the rivers it rises above the land. Terry draws the sea layer wherever it is above the land, so
feeding the compiled map back in floods river valleys and beaches.

What this keeps:
  - open sea: the flat sea level (14219) exactly as compiled
  - lakes: wide areas where the compiled surface stands above the land. Found by a morphological opening of the
    "sea above land" mask; the river bands and coastal fringes are narrow and drop out.
Everywhere else, the sea layer is set to sea level where the land is below it, and to 0 (no water) otherwise.

usage: source_sea_from_compiled.py <lf_sea_height_map.dds> <lf_height_map.dds> <out.npy> [preview.png]
"""
import sys
import numpy as np

SEA_LEVEL = 14219
WORLD_WIDTH = 595.0999755859375
DEPTH_MIN = 0.05 / 0.00021849      # sea must stand at least 0.05 world units above the land to count as water
LAKE_RADIUS_UNITS = 3.0            # bands narrower than about 2 x this are treated as fill, not lakes


def erode(mask, r):
    out = mask.copy()
    for _ in range(r):
        m = out
        out = m.copy()
        out[1:, :] &= m[:-1, :]
        out[:-1, :] &= m[1:, :]
        out[:, 1:] &= m[:, :-1]
        out[:, :-1] &= m[:, 1:]
    return out


def dilate(mask, r):
    out = mask.copy()
    for _ in range(r):
        m = out
        out = m.copy()
        out[1:, :] |= m[:-1, :]
        out[:-1, :] |= m[1:, :]
        out[:, 1:] |= m[:, :-1]
        out[:, :-1] |= m[:, 1:]
    return out


def build(sea, land):
    """sea: compiled sea map (u16); land: land heights resampled to the sea grid (u16)."""
    above = (sea != SEA_LEVEL) & (sea.astype(np.int64) > land.astype(np.int64) + DEPTH_MIN)
    r = int(round(LAKE_RADIUS_UNITS * sea.shape[1] / WORLD_WIDTH))
    lakes = dilate(erode(above, r), r + 2) & above
    out = np.where(land < SEA_LEVEL, SEA_LEVEL, 0).astype(np.uint16)
    out[sea == SEA_LEVEL] = SEA_LEVEL
    out[lakes] = sea[lakes]
    return out, above, lakes


if __name__ == "__main__":
    sea = np.fromfile(sys.argv[1], "<u2", offset=128)
    land_full = np.fromfile(sys.argv[2], "<u2", offset=128)
    # the sea map is half the land resolution in both directions
    h = int(round((sea.size / 1.27) ** 0.5))
    land_full = land_full.reshape(-1, 7136) if land_full.size % 7136 == 0 else None
    sea = sea.reshape(land_full.shape[0] // 2, land_full.shape[1] // 2)
    land = land_full.reshape(sea.shape[0], 2, sea.shape[1], 2).max(axis=(1, 3))
    out, above, lakes = build(sea, land)
    np.save(sys.argv[3], out)
    print(f"sea-above-land px (non sea level): {above.sum():,}  kept as lakes: {lakes.sum():,}")
    print(f"still above land after rebuild (non sea level): {((out != SEA_LEVEL) & (out > land)).sum():,}")
    if len(sys.argv) > 4:
        from PIL import Image
        img = np.stack([np.clip((land.astype(float) - SEA_LEVEL) / 20000, 0, 1) * 120 + 60] * 3, -1)
        img[(out == SEA_LEVEL) & (out > land)] = [30, 60, 140]
        img[above & ~lakes] = [255, 80, 40]
        img[lakes] = [60, 200, 255]
        Image.fromarray(img.astype(np.uint8)[::2, ::2]).save(sys.argv[4])
