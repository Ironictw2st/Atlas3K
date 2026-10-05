#!/usr/bin/env python3
"""North cull (user, 2026-09-30: "cull some of the mountains and props in the Northern side, so we can add some more
northern provinces for the Northern Tribes"; approved scope: the 4 CORE tribal provinces - Southern Xiongnu,
Yunzhong Xianbei (Budugen), Danhan Xianbei (Kebineng), Wuhuan (Tadun)).

Masks were computed by research_r6/north (cull_masks.py / sites.py / territory.py, NORTH_CORE=1) from the Copernicus
GLO-90 relief under a town-anchored georef; see docs/main190_north_cull_proposal.md. All masks are hex masks on the
1428 x 896 grid, stored as int32 (col, row) pairs:
  cull_blend.npy        mountain blend class 4-7 -> non-mountain (real relief < 350 m within +-4 km)
  new_type.npy          (h, w) uint8 repaint type per culled hex: 1 flat west (steppe mix), 2 flat east of 120E (grass
                        mix), 3 hill (light forest / grass)
  cull_imp_playable.npy impassable -> passable inside existing playable regions
  zone_open.npy         non-playable land the 4 core tribal provinces take (territory estimate, cap 2800 / region)
  keep_range.npy        real ranges kept (Yin, Yan, Taihang, Heng / Wutai, Khingan, Changbai ...)
  sites.json            proposed tribal town sites (only for the vegetation-prop clearing round them)

Entry points
  apply_rasters(terrain_dir, log)   after class_fill.py: repaint blend (FULL) + tree (QUARTER) rasters; idempotent
                                    (pristine copies in <terrain_dir>/_pre_north/, refreshed whenever the rasters are
                                    no longer our own output, i.e. class_fill re-ran)
  apply_hex(f, names, reg, terr, NA, log, mountain=None) -> dict
                                    in regions_carve6 right after the Liang-zone passability step
  drop_prop(entity_text, nx, nz) -> bool
                                    in ak_main.do_entity, after the warp: True = drop the entity
"""
import hashlib, json, os, shutil, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent
DATA = HERE / "research_r6" / "north"
for p in (HERE, HERE.parent / "guandu", HERE.parent, HERE.parent.parent / "output" / "pylibs"):
    if str(p) not in sys.path: sys.path.insert(0, str(p))

from warp import current as _current
_WP = _current(); W, H = _WP.W, _WP.H          # round 8: the masks were retargeted to the taller-only warp (retarget_hexspace.py)
MOUNTAIN_BLEND = (4, 5, 6, 7)
BLEND = "3k_dlc07_main_map.blend.191fd8068da8020.tif"
TREE = "3k_dlc07_main_map.tree.191fd7dc12fe7e4.tif"
# repaint mixes (class_fill's palette classes): 1 steppe (west), 2 grass (east), 3 hill (no mountain class 4)
MIXES = {1: {21: .4, 20: .2, 22: .2, 19: .2}, 2: {21: .45, 20: .15, 19: .2, 27: .2}, 3: {27: .5, 22: .3, 21: .2}}
OPEN_MARGIN = 4          # hexes of margin round the estimated tribal territory (carve6's own Dijkstra differs a little)
VEG_RING = 2             # vegetation props within this many hexes of a proposed town footprint are dropped
_cache = {}


def _mask(name, shape=(H, W)):
    k = ("mask", name)
    if k not in _cache:
        a = np.load(DATA / f"{name}.npy"); m = np.zeros(shape, bool)
        ok = (a[:, 0] >= 0) & (a[:, 0] < shape[1]) & (a[:, 1] >= 0) & (a[:, 1] < shape[0])
        if not ok.all(): raise ValueError(f"north_cull: {name}.npy has hexes outside {shape[1]}x{shape[0]}")
        m[a[:, 1], a[:, 0]] = True; _cache[k] = m
    return _cache[k]


def _grow(m, NA, k):
    for _ in range(k):
        g = m.copy()
        for nr, nc, v in NA: g |= v & m[nr, nc]
        m = g
    return m


# ----------------------------------------------------------------------------------------------------------------------
def apply_hex(f, names, reg, terr, NA, log=print, mountain=None):
    """Hex-side cull. Mutates f["imp"]:
       * cull_imp_playable -> passable (land, playable, never town / sprawl hexes, never *_pass regions)
       * open_nomad land that is not mountain after the cull -> passable (so ok_site can pick nomad sites there).
         carve6 must set imp = 1 again (and region = non-playable) on open_nomad hexes no nomad region claims.
    Returns {"open_nomad": bool (h, w), "mountain_after": bool (h, w), "keep_range": bool (h, w), "cull_blend": bool (h, w)}.
    mountain: carve6's blend-based mountain mask (np.isin(hb, MOUNTAIN_BLEND)); computed here if not given."""
    h, w = reg.shape
    if (h, w) != (H, W) or terr.shape != (h, w) or f["imp"].shape != (h, w):
        raise ValueError(f"north_cull.apply_hex: map is {w}x{h}, masks are for {W}x{H}")
    NP = names.index("3k_main_reg_non_playable")
    passes = [i for i, n in enumerate(names) if n.endswith("_pass")]
    town = (f["slot"] >= 0) | (f["sprawl"] == 1)
    land = terr == 0
    if mountain is None:
        from regions_carve import hex_blend_and_height
        hb, _ = hex_blend_and_height(w, h); mountain = np.isin(hb, MOUNTAIN_BLEND)
    cull_blend, keep = _mask("cull_blend"), _mask("keep_range")
    mountain_after = mountain & ~cull_blend
    # impassable -> passable inside playable regions
    ci = _mask("cull_imp_playable") & land & ~town & (reg >= 0) & (reg != NP) & ~np.isin(reg, passes) & ~mountain_after
    n0 = int((ci & (f["imp"] == 1)).sum()); f["imp"][ci] = 0
    # land the core tribal regions may use: the territory estimate + a margin, non-playable land only
    zone = _mask("zone_open")
    open_nomad = _grow(zone, NA, OPEN_MARGIN) & (reg == NP) & land
    op = open_nomad & ~mountain_after & ~town
    n1 = int((op & (f["imp"] == 1)).sum()); f["imp"][op] = 0
    log(f"north cull: {n0} playable hexes made passable; open_nomad {int(open_nomad.sum())} hexes "
        f"({int(op.sum())} passable, {int((open_nomad & mountain_after).sum())} mountain); "
        f"mountain {int(mountain.sum())} -> {int(mountain_after.sum())}")
    return {"open_nomad": open_nomad, "mountain_after": mountain_after, "keep_range": keep, "cull_blend": cull_blend}


# ----------------------------------------------------------------------------------------------------------------------
def _sha(p):
    h = hashlib.sha1()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""): h.update(b)
    return h.hexdigest()


def _quarter_hex(size):
    """hex (col, row) of every quarter-raster pixel centre (the raster <-> world mapping of hex_blend_and_height)."""
    from terrain_main import NWW, NWH
    from hexgrid import nearest_hex
    qw, qh = size
    xs = (np.arange(qw) + 0.5) / qw * NWW
    cols = np.empty((qh, qw), np.int32); rows = np.empty((qh, qw), np.int32)
    for r0 in range(0, qh, 256):
        r1 = min(qh, r0 + 256); z = (1 - (np.arange(r0, r1) + 0.5) / qh) * NWH
        X, Z = np.broadcast_arrays(xs[None, :], z[:, None])
        c, r = nearest_hex(X.ravel(), Z.ravel(), W, H)
        cols[r0:r1] = np.asarray(c).reshape(X.shape); rows[r0:r1] = np.asarray(r).reshape(X.shape)
    return cols, rows


def apply_rasters(terrain_dir, log=print):
    """Repaint mountain blend classes on the culled hexes (FULL blend raster) and redraw the tree classes there
    (QUARTER tree raster) from the per-class tree distribution of the rest of the map. Idempotent."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    from class_fill import smooth_noise, ranked, pick
    T = Path(terrain_dir); KEEP = T / "_pre_north"; KEEP.mkdir(exist_ok=True)
    stamp = KEEP / "applied.json"
    done = json.load(open(stamp)) if stamp.exists() else {}
    for n in (BLEND, TREE):
        cur = T / n
        if not (KEEP / n).exists() or _sha(cur) != done.get(n):      # first run, or class_fill wrote a fresh raster
            shutil.copy2(cur, KEEP / n); log(f"north cull: pristine copy of {n} taken")
    im = Image.open(KEEP / BLEND); full = np.array(im); pal = im.getpalette()
    tim = Image.open(KEEP / TREE); tr = np.array(tim); tpal = tim.getpalette()
    qh, qw = tr.shape
    FH, FW = full.shape
    cols, rows = _quarter_hex((qw, qh))
    cull = _mask("cull_blend"); typ = np.zeros((H, W), np.uint8)
    nt = np.load(DATA / "new_type.npy"); typ[:] = nt if nt.shape == (H, W) else 0
    qtype = np.where(cull[rows, cols], typ[rows, cols], 0).astype(np.uint8)       # repaint type per quarter pixel
    # FULL pixels: quarter pixel = full // 4 (the raster pair is exactly 4x, as class_fill assumes)
    ys, xs = np.nonzero(np.isin(full, MOUNTAIN_BLEND))
    qy, qx = np.minimum(ys // 4, qh - 1), np.minimum(xs // 4, qw - 1)
    t_px = qtype[qy, qx]; k = t_px > 0; ys, xs, qy, qx, t_px = ys[k], xs[k], qy[k], qx[k], t_px[k]
    out = full.copy()
    nq = (0.5 * smooth_noise((qh, qw), 12, 61) + smooth_noise((qh, qw), 48, 62)).astype(np.float32)   # patches
    for t, mix in MIXES.items():
        s = t_px == t
        if s.any(): out[ys[s], xs[s]] = pick(mix, ranked(nq[qy[s], qx[s]]))
    n_sel = len(ys)
    # trees: quarter pixels whose blend majority changed get a tree class drawn from the tree distribution of their
    # new blend class elsewhere on the map (class_fill's rule)
    q_old = full[::4, ::4][:qh, :qw]; q_new = out[::4, ::4][:qh, :qw]
    chg = (q_old != q_new)
    tab = np.zeros((256, 256), np.int64); np.add.at(tab, (q_old[~chg & (qtype == 0)], tr[~chg & (qtype == 0)]), 1)
    ut = ranked((smooth_noise((qh, qw), 8, 63) + 0.5 * smooth_noise((qh, qw), 32, 64))[chg])
    tnew = tr.copy(); bq = q_new[chg]; tc = tr[chg].copy()
    for b in np.unique(bq):
        s = bq == b
        if tab[b].sum(): tc[s] = np.minimum(np.searchsorted(np.cumsum(tab[b]) / tab[b].sum(), ut[s]), 255)
    tnew[chg] = tc
    tif = {"compression": "tiff_lzw", "strip_size": FW * 2, "tiffinfo": {277: 1, 339: 1, 284: 1}}
    res = Image.fromarray(out.astype(np.uint8), "P"); res.putpalette(pal); res.save(T / BLEND, **tif)
    res = Image.fromarray(tnew.astype(np.uint8), "P"); res.putpalette(tpal); res.save(T / TREE, **tif | {"strip_size": qw * 2})
    json.dump({BLEND: _sha(T / BLEND), TREE: _sha(T / TREE)}, open(stamp, "w"), indent=1)
    log(f"north cull: blend {n_sel} px repainted (~{n_sel / 64:.0f} hexes), tree {int(chg.sum())} px redrawn")
    return dict(blend_px=n_sel, tree_px=int(chg.sum()))


# ----------------------------------------------------------------------------------------------------------------------
def _prop_masks():
    if "props" not in _cache:
        from hexgrid import neighbour_arrays
        NA = neighbour_arrays(H, W)
        mnt = (_mask("cull_blend") | _grow(_mask("zone_open"), NA, OPEN_MARGIN)) & ~_mask("keep_range")
        fp = np.zeros((H, W), bool)
        S = json.load(open(DATA / "sites.json"))
        for p in S["placed"].values():
            for x, y, *_ in p["fp"]: fp[y, x] = True
        _cache["props"] = (mnt, _grow(fp, NA, VEG_RING))
    return _cache["props"]


def drop_prop(entity_text, nx, nz):
    """True if a (warped) AK entity should be dropped: mountain / rock props on culled or opened land outside the kept
    ranges, and vegetation props within VEG_RING hexes of a proposed tribal town. nx, nz = new-map world x / z."""
    import re, warp
    if warp.is_scale(): return False                     # base 190E x1.5: no north cull
    m = re.search(r'model_path="([^"]*)"', entity_text)
    if not m: return False
    mp = m.group(1).lower()
    mountain = "/mountains/" in mp or "rocks/general" in mp; veg = "/vegetation/" in mp
    if not (mountain or veg): return False
    from hexgrid import nearest_hex
    c, r = nearest_hex(np.array([float(nx)]), np.array([float(nz)]), W, H); c, r = int(c[0]), int(r[0])
    mnt, vegm = _prop_masks()
    return bool(mnt[r, c]) if mountain else bool(vegm[r, c])


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--rasters", help="terrain dir to repaint (default: none)")
    a = ap.parse_args()
    if a.rasters: apply_rasters(a.rasters)
