#!/usr/bin/env python3
"""x15 build helpers (the proposal session's tile map / prop clearing plan, docs/main190_x15_tilemap_proposal.md):

tile_clear(out, NW, NH, log)  - applied by caime_tilemap.py after the area colours:
  * new land (proposal masks): playable corridor / valleys / steppe and desert -> generic land 96aa64; the Qilian wall,
    the Xiping ring and the steppe ranges -> cold mountain 1820c1 (lakes are sea from map.hex already)
  * tier 1: mountain tiles within 4 hexes of a new / moved town, or 1 hex of a road hex inside a new / moved region
    -> generic
  * tier 2 (user: yes): mountain tiles on flat ground inside new regions (relief below the 35th percentile of the
    mountain tiles' relief) -> generic
drop_prop(entity_text, nx, nz)  - applied by ak_main.py: old 190E mountain / rock props whose new position is on the new
  playable land or the desert are dropped (the ranges keep theirs).
Active when proposal_x15/build_masks.npz matches the current grid and regions_new.json has the x15 provinces."""
import json, re
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent
MASKS = HERE / "proposal_x15" / "build_masks.npz"
GENERIC, COLD_MTN = 0x96aa64, 0x1820c1
MOUNTAIN_KINDS = (0x1820c1, 0xb69237, 0x53b021, 0x463a76, 0xffff7f, 0x10ffe4)
_M = None


def masks(W=None, H=None):
    global _M
    if _M is None and MASKS.exists():
        z = np.load(MASKS); _M = {k: z[k] for k in z.files}
    if _M is None: return None
    if W is not None and next(iter(_M.values())).shape != (H, W): return None
    return _M


def _new_ids(names):
    nj = json.load(open(HERE / "regions_new.json", encoding="utf-8"))
    keys = {r for p in nj.get("provinces", {}).values() for r in p.get("regions", [])} | set(nj.get("moved", {}))
    return {i for i, n in enumerate(names) if n in keys}


def tile_clear(out, NW, NH, log=print, hex_path=HERE / "hex" / "map.hex"):
    M = masks(NW, NH)
    if M is None: log("tile_clear: no x15 masks for this grid - skipped"); return
    import sys
    for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
    import town_fix as T
    from hexgrid import neighbour_arrays
    from regions_carve import hex_blend_and_height
    _, _, w, h, _, f, names = T.load(str(hex_path))
    assert (w, h) == (NW, NH)
    NA = neighbour_arrays(h, w)
    def grow(m, k):
        for _ in range(k):
            g = m.copy()
            for nr, nc, v in NA: g |= v & m[nr, nc]
            m = g
        return m
    land = f["terr"] == 0
    mtn = np.isin(out, MOUNTAIN_KINDS)
    # new land
    play = (M["hexi_play"] | M["steppe_play"] | M["hexi_desert"]) & land
    rng = (M["hexi_mountain"] | M["steppe_mountain"]) & land & ~play
    n0 = int((play & (out != GENERIC)).sum()); out[play] = GENERIC; out[rng] = COLD_MTN
    log(f"tile_clear: new land {n0} hexes -> generic, {int(rng.sum())} ranges -> cold mountain")
    # tier 1
    ids = _new_ids(names); newreg = np.isin(f["region"], list(ids))
    towns = ((f["slot"] >= 0) | (f["sprawl"] > 0)) & newreg
    # 2026-10-02 (user: steppe towns buried): range tiles next to a new town go too - only roads keep ~rng
    near = ((grow(towns, 4) & land & np.isin(out, MOUNTAIN_KINDS)) |
            (grow((f["road"] > 0) & newreg, 1) & land & mtn & ~rng))
    out[near] = GENERIC; log(f"tile_clear tier 1: {int(near.sum())} mountain tiles near new towns / roads -> generic")
    # tier 2: painted mountains on flat ground in the new regions
    _, hh = hex_blend_and_height(w, h)
    rel = np.zeros((h, w), np.float32)
    for nr, nc, v in NA: rel = np.maximum(rel, np.where(v, np.abs(hh[nr, nc] - hh), 0))
    mt = np.isin(out, MOUNTAIN_KINDS) & land
    thr = float(np.percentile(rel[mt], 35)) if mt.any() else 0
    flat = mt & newreg & (rel < thr) & ~rng
    out[flat] = GENERIC; log(f"tile_clear tier 2: {int(flat.sum())} flat-ground mountain tiles in new regions -> generic (relief < {thr:.0f})")
    # Korea rework north (user 2026-10-02: no mountain tiles there, to be replaced by hand later)
    kn = HERE / "korea_ref" / "north_open.npy"
    if kn.exists():
        nm = np.load(kn)
        if nm.shape == out.shape:
            hit = nm & land & np.isin(out, MOUNTAIN_KINDS); out[hit] = GENERIC
            log(f"tile_clear korea north: {int(hit.sum())} mountain tiles -> generic")


_PM = None


def drop_prop(entity_text, nx, nz):
    """True for an old mountain / rock prop on the new playable land or desert (x15 masks); nx, nz new-map world x / z."""
    global _PM
    m = re.search(r'model_path="([^"]*)"', entity_text)
    if not m: return False
    mp = m.group(1).lower()
    if "/mountains/" not in mp and "rocks/general" not in mp: return False
    if _PM is None:
        from warp import current
        W = current(); M = masks(W.W, W.H)
        _PM = (M["hexi_play"] | M["steppe_play"] | M["hexi_desert"]) if M is not None else False
        kn = HERE / "korea_ref" / "north_open.npy"
        if kn.exists() and _PM is not False and np.load(kn).shape == _PM.shape: _PM = _PM | np.load(kn)
    if _PM is False: return False
    import sys
    for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
    from hexgrid import nearest_hex
    h, w = _PM.shape
    c, r = nearest_hex(np.array([float(nx)]), np.array([float(nz)]), w, h)
    return bool(_PM[int(r[0]), int(c[0])])


_JJ = None


def jeju_warp(nx, nz):
    """Jeju enlarged in place (jeju_scale.py, 2026-10-02): props inside the old island disc move outward with it."""
    global _JJ
    if _JJ is None:
        m = HERE / "hex" / ".jeju_scaled"
        _JJ = json.loads(m.read_text()) if m.exists() else False
    if not _JJ: return nx, nz
    dx, dz = nx - _JJ["cx"], nz - _JJ["cz"]
    if dx * dx + dz * dz > _JJ["R0"] ** 2: return nx, nz
    return _JJ["cx"] + dx * _JJ["S"], _JJ["cz"] + dz * _JJ["S"]
