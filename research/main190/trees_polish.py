#!/usr/bin/env python3
"""Tree-raster polish for the new areas (docs/proposals/new_areas_lookover.md H4 + M1), applied by trees_x15.build()
after the top-up and before the clean-up, so every build (tree_clear.py -> trees_x15.main) re-applies it.

Works on the per-hex class array `out` (h, w; palette index, NO_TREE = 19). Palette (kit campaign_tree_ids colours):
  0 bamboo, 1 bamboo small, 2 castanopsis small, 3 castanopsis large   <- subtropical
  4 fir large/medium, 6 fir medium/small, 7 katsura large, 8 katsura single, 14 katsura medium/small, 15 katsura blossom,
  9 poplar large, 16 poplar medium/small, 5/10 metasequoia, 11 rock, 12 flower, 13 rock shrub, 17/18 farm foliage.
Groups (from the map.hex region names, as the proposal's py/common.py):
  hexi = ironic_hexi_* + ironic_region_{hanyang,xi_,wuwei,xiping}; nomad = ironic_nomad_* + ironic_region_wuyuan;
  korea_ne = other ironic_region_*; np_new = non-playable hexes inside terrain/pad_mask.png; everything else untouched.
Steps (all deterministic: stable per-hex hashes, no RNG state; each is (near-)idempotent on its own output, which matters
because the next build feeds this raster back in as the "current" raster for the new land / pads):
  P1 (H4) subtropical classes 0-3 in hexi / nomad / korea_ne / np_new at row >= NORTH_ROW -> by map.hex climate:
     arid -> poplar, cold -> fir, temperate (and anything else) -> katsura; large/small kept (0,3 large; 1,2 small).
  P2 (M1) speckle: 7-hex (hex + 6 neighbours) majority filter of tree / no-tree on hexi / nomad / np_new land, iterated
     to a fixed point; a hex that turns into a tree takes the commonest class of its tree neighbours.
  P3 (M1) nomad arid cover -> NOMAD_ARID_TARGET (counted after the later clean-up, i.e. hexes in `cut` count as empty):
     drop patches < 4 hexes (smallest first), then peel outer rings (fewest tree neighbours first).
  P4 (M1 optional) korea_ne lowland (bottom height tercile) fir -> katsura on ~50% of them (clumped fixed-seed noise).

V2 (2026-10-04, blend_v2 brief; QUILT = True): the P2 majority filter turned the steppe woods into big round blobs (mean
patch 36 -> 94 hexes) and the P3 ring peel rounded them further. With QUILT, P2 / P3 are replaced by
  Q2 terrain-guided donor quilting of the forest layer on the quilt domain (blend_v2's new-land domain: hexi / nomad /
     korea_ne without Korea's south / np_new / np_old north of row 830 or in the Hexi zone): 12x12-hex windows of the
     VANILLA tree layer of this map (same climate band, similar slope / water / river mix) are quilted in, picked by
     overlap mismatch with what is already there + a per-hex terrain correspondence term (vanilla's P(tree | climate,
     slope, valley / ridge, river distance), so woods sit on slopes, in valleys and along rivers like vanilla) + the
     cover the zone wants (trees_x15.ZONE_TARGET by plan zone, KOREA_NE_COVER, else the vanilla terrain rate), and
     joined along min-cut seams. Species come with the donor (vanilla north species), then P1 remaps any subtropical.
     The result depends only on terrain / zones / vanilla / fixed seeds, never on the incoming raster in the domain,
     so the trees_x15 fixed-point loop converges at once (and the result is cached across its rounds).
  Q3 nomad arid cover -> NOMAD_ARID_TARGET by removing the least terrain-suitable tree hexes (no ring peeling).
Set QUILT = False for the previous (majority) behaviour; trees_polish.py.pre_v2 is the untouched previous file."""
from pathlib import Path
import numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
HERE = Path(__file__).parent

NO_TREE = 19
SUBTROP = (0, 1, 2, 3)
SMALL = {0: False, 1: True, 2: True, 3: False}
# climate code -> (large choices, small choices)
REMAP = {0: ((9,), (16,)),                 # arid: poplar
         1: ((4,), (6,)),                  # cold: fir
         4: ((7, 8), (14, 15))}            # temperate (default): katsura
NORTH_ROW = 430                            # rows count from the south (row 0 = bottom of the raster)
SMOOTH_GROUPS = ("hexi", "nomad", "np_new")
REMAP_GROUPS = ("hexi", "nomad", "korea_ne", "np_new")
NOMAD_ARID_TARGET = 0.185
SMALL_PATCH = 4
KOREA_FIR_TO_KATSURA = 0.5
FIR = {4: 7, 6: 14}
# V2 quilting (see the docstring)
QUILT = True
QP, QOV = 12, 4                            # window / overlap (hexes)
QK, QTOL, QSEED = 48, 0.06, 20261004
QW_OV, QW_G, QW_D, QW_RE = 1.0, 1.0, 0.4, 0.03
KOREA_NE_COVER = 0.55                      # Manchurian / north Korean woods stay dense (current 57.8%, vanilla 43%)
NPOLD_ROW = 830                            # = blend_v2.NPOLD_ROW


def hash01(w, h, salt):
    """Stable per-hex value in [0, 1) (independent of the clean-up hash in trees_x15)."""
    c = np.arange(w, dtype=np.int64)[None, :]; r = np.arange(h, dtype=np.int64)[:, None]
    x = (c * 0x9E3779B1 + r * 0x85EBCA77 + salt * 0xC2B2AE3D) & 0xFFFFFFFF
    x ^= x >> 15; x = (x * 0x2C1B3C6D) & 0xFFFFFFFF; x ^= x >> 12; x = (x * 0x297A2D39) & 0xFFFFFFFF; x ^= x >> 15
    return x.astype(np.float64) / 2.0 ** 32


def group_of(n):
    if n.startswith("ironic_hexi_"): return "hexi"
    if n.startswith("ironic_nomad_"): return "nomad"
    if n.startswith("ironic_central_"): return "central"
    if n.startswith("ironic_south_"): return "south"
    if n.startswith("ironic_sea_"): return "sea"
    if n.startswith("ironic_region_"):
        if any(n.startswith("ironic_region_" + k) for k in ("hanyang", "xi_", "wuwei", "xiping")): return "hexi"
        if n.startswith("ironic_region_wuyuan"): return "nomad"
        return "korea_ne"
    return "vanilla"


def sample_hex(arr, s, w, h):
    """Per-hex sample of a north-up raster with s px per hex (hex centre, as output/proposals/new_areas/py/common.py)."""
    rr, cc = np.indices((h, w))
    px = s * cc + s // 2; py = arr.shape[0] - s * rr - s // 2 - (s // 2) * (cc & 1)
    return arr[np.clip(py, 0, arr.shape[0] - 1), np.clip(px, 0, arr.shape[1] - 1)]


def groups(f, names, w, h):
    G = np.array([group_of(n) for n in names] + ["?"], dtype=object)[np.where(f["region"] >= 0, f["region"], len(names))]
    if "3k_main_reg_non_playable" in names:
        pad = sample_hex(np.array(Image.open(HERE / "terrain" / "pad_mask.png")) > 0, 8, w, h)
        npk = (f["region"] == names.index("3k_main_reg_non_playable"))
        G = G.copy(); G[npk & pad] = "np_new"; G[npk & ~pad] = "np_old"
    return G


_HGT = {}


def hex_height(w, h):
    if (w, h) not in _HGT: _HGT[(w, h)] = _hex_height(w, h)
    return _HGT[(w, h)]


def _hex_height(w, h):
    p = next((HERE / "terrain").glob("3k_dlc07_main_map.height.*.tif"), None)
    if p is None: return None
    a = np.array(Image.open(p))
    if a.shape[1] != 8 * w or abs(a.shape[0] - 8 * h) > 8: return None           # stale / other-grid height
    return sample_hex(a, 8, w, h).astype(np.int64)


def components(m, NA):
    """Hex-connected components of mask m -> (labels (h, w) with -1 outside, sizes)."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    h, w = m.shape; idx = np.full(m.shape, -1, np.int64); idx[m] = np.arange(int(m.sum()))
    a, b = [], []
    for nr, nc, v in NA[:3]:                                     # 3 directions are enough for an undirected graph
        e = m & v & m[nr, nc]; a.append(idx[e]); b.append(idx[nr[e], nc[e]])
    n = int(m.sum()); a = np.concatenate(a); b = np.concatenate(b)
    if n == 0: return idx, np.zeros(0, int)
    g = coo_matrix((np.ones(len(a), np.int8), (a, b)), shape=(n, n))
    k, lab = connected_components(g, directed=False)
    L = np.full(m.shape, -1, np.int64); L[m] = lab
    return L, np.bincount(lab, minlength=k)


def topup_skip(f, names, w, h):
    """Hexes whose tree cover P3 manages (nomad arid land): trees_x15.topup leaves them alone."""
    return (groups(f, names, w, h) == "nomad") & (f["terr"] == 0) & (f["climate"] == 0)


def ncount(t, NA):
    s = np.zeros(t.shape, np.int16)
    for nr, nc, v in NA: s += (v & t[nr, nc])
    return s


# ---------------------------------------------------------------- V2: terrain-guided forest quilting -------------------
_QCACHE = {}


def quilt_domain(f, names, w, h):
    """blend_v2's new-land domain on the hex grid (land only) and the blend_v2 group code per hex."""
    import blend_v2 as BV
    reg = f["region"]
    code = np.array([BV.group_code(n) for n in names] + [BV.PROT], np.uint8)[np.where(reg >= 0, reg, len(names))]
    rows = np.arange(h)[:, None].repeat(w, 1)
    if "3k_main_reg_non_playable" in names:
        pad = sample_hex(np.array(Image.open(HERE / "terrain" / "pad_mask.png")) > 0, 8, w, h)
        npk = reg == names.index("3k_main_reg_non_playable")
        flag = npk & ~pad & (rows >= NPOLD_ROW)
        try:
            import hexi_geo
            from scipy import ndimage as ndi
            zw = hexi_geo._zone()["w"]
            if zw.shape == (h, w):
                z = zw > 0; edge = z ^ ndi.binary_erosion(z)
                flag |= npk & ~pad & (z | (ndi.distance_transform_edt(~edge) <= BV.ZONE_EDGE))
        except Exception as e:
            print("trees_polish: hexi zone unavailable:", e)
        code = code.copy(); code[npk & pad] = BV.NPNEW; code[npk & ~pad] = BV.NPOLD; code[flag] = BV.NPOLDF
    return np.isin(code, (BV.HEXI, BV.NOMAD, BV.KNE, BV.NPNEW, BV.NPOLDF)) & (f["terr"] == 0), code


def terrain_features(f, w, h):
    """per hex: slope (u16 / px), relief (height - 6-hex mean; < 0 = valley), river distance, water distance (hexes)."""
    from scipy import ndimage as ndi
    hg = hex_height(w, h)
    if hg is None: raise RuntimeError("trees_polish V2 needs the polished height raster on this grid")
    hg = hg.astype(np.float32)
    hs = ndi.gaussian_filter(hg, 1.0); gy, gx = np.gradient(hs)
    return dict(sl=np.hypot(gx, gy) / 8, rel=hg - ndi.gaussian_filter(hg, 6.0),
                dr=ndi.distance_transform_edt(~(f["river"] > 0)), dw=ndi.distance_transform_edt(f["terr"] == 0))


def suitability(out, f, van, Tf, log=print):
    """vanilla P(tree | climate, slope band, relief band, river band) per hex (smoothed towards the climate x slope rate)."""
    sb = np.digitize(Tf["sl"], np.percentile(Tf["sl"][van], [25, 50, 75, 90]))
    eb = np.digitize(Tf["rel"], np.percentile(Tf["rel"][van], [10, 30, 70, 90]))
    rb = np.digitize(Tf["dr"], (0.5, 1.5, 3, 6))
    cl = np.minimum(f["climate"], 4)
    tree = (out != NO_TREE)
    key = ((cl * 5 + sb) * 5 + eb) * 5 + rb
    n = np.bincount(key[van], minlength=625); t = np.bincount(key[van], weights=tree[van], minlength=625)
    k2 = cl * 5 + sb
    n2 = np.bincount(k2[van], minlength=25); t2 = np.bincount(k2[van], weights=tree[van], minlength=25)
    p2 = (t2 + 2 * tree[van].mean()) / (n2 + 2)
    p = (t + 20 * p2[np.arange(625) // 25]) / (n + 20)
    return p[key].astype(np.float32), sb


def quilt_forests(out, f, names, w, h, cut, log=print):
    """Q2 (in place on `out`): returns (domain mask, suitability, info)."""
    import hashlib, json
    from scipy import ndimage as ndi
    from blend_v2 import graph_cut, smooth_noise
    import blend_v2 as BV
    dom, code = quilt_domain(f, names, w, h)
    land = f["terr"] == 0
    van = (code == BV.VAN) & land
    key = hashlib.md5(out[~dom].tobytes() + dom.tobytes() + np.ascontiguousarray(out.shape).tobytes()).hexdigest()
    if key in _QCACHE:
        res, suit, info = _QCACHE[key]; out[dom] = res[dom]; return dom, suit, dict(info)
    Tf = terrain_features(f, w, h)
    suit, sb = suitability(out, f, van, Tf)
    rows = np.arange(h)[:, None].repeat(w, 1)
    # wanted cover per hex: the zone's target (trees_x15.ZONE_TARGET), shaped by the terrain suitability
    from trees_x15 import ZONE_TARGET
    Z = np.full((h, w), "", object)
    for pf in ("steppe_plan.json", "hexi_plan.json"):
        p = HERE / "korea_ref" / pf
        if not p.exists(): continue
        for r, runs in json.load(open(p, encoding="utf-8"))["zone_rle"].items():
            for s0, n, z in runs: Z[int(r), s0:s0 + n] = z
    E = suit.copy()
    A = (code == BV.NOMAD) & land & (f["climate"] == 0)
    for z in set(Z[dom].tolist()) - {""}:
        for cl in np.unique(f["climate"][dom & (Z == z)]):
            m = dom & (Z == z) & (f["climate"] == cl)
            tgt = NOMAD_ARID_TARGET * 1.15 if (m & A).sum() > m.sum() / 2 else ZONE_TARGET.get(z, None)
            if tgt is None or m.sum() < 20: continue
            E[m] = suit[m] * tgt / max(float(suit[m].mean()), 1e-3)
    m = dom & (code == BV.KNE); E[m] = suit[m] * KOREA_NE_COVER / max(float(suit[m].mean()), 1e-3) if m.any() else E[m]
    E = np.clip(E, 0, 0.95).astype(np.float32)
    src = out.copy(); canvas = out
    pres = (src != NO_TREE)
    # donor windows (even column offsets keep the hex parity): mostly vanilla land
    n = QP
    wat = ~land
    chans = [(van & pres).astype(np.float32), van.astype(np.float32), wat.astype(np.float32),
             (Tf["dr"] <= 1.5).astype(np.float32), (Tf["dw"] <= 1.6).astype(np.float32)] + [(sb == b).astype(np.float32) for b in range(5)]
    ys = np.arange(0, h - n, 2); xs = np.arange(0, w - n, 2)
    gy, gx = np.meshgrid(ys, xs, indexing="ij"); gy, gx = gy.ravel(), gx.ravel()
    S = np.stack([ndi.uniform_filter(ch, n, mode="constant", origin=-(n // 2))[gy, gx] for ch in chans], 1)
    ok = (S[:, 1] >= 0.8) & (S[:, 1] + S[:, 2] >= 0.97)
    cy, cx, S = gy[ok], gx[ok], S[ok]
    ccov = S[:, 0] / np.maximum(S[:, 1], 1e-3); cslope = S[:, 5:10]; criv, cwat = S[:, 3], S[:, 4]
    crow = (cy + n // 2).astype(np.float32); ccl = f["climate"][cy + n // 2, cx + n // 2]
    creg = f["region"][cy + n // 2, cx + n // 2]
    used = np.zeros(len(cy), np.float32)
    rng = np.random.default_rng(QSEED)
    nz = (0.6 + 0.4 * (smooth_noise((h + n, w + n), 3, QSEED + 1) + 1) / 2).astype(np.float32)
    filled = np.zeros((h, w), bool)
    rr_, cc_ = np.nonzero(dom)
    wins = []
    for r in range(max(0, rr_.min() - QOV), rr_.max() + 1, n - QOV):
        for c in range(max(0, cc_.min() - QOV) & ~1, cc_.max() + 1, n - QOV):
            r0 = int(np.clip(r + rng.integers(-2, 3), 0, h - n)); c0 = int(np.clip(c + 2 * rng.integers(-1, 2), 0, w - n)) & ~1
            wins.append((r0, c0))
    info = dict(Q2_windows=0, Q2_hexes=int(dom.sum()), Q2_donor_windows=int(len(cy)))
    donor = {}
    for r0, c0 in wins:
        sl = (slice(r0, r0 + n), slice(c0, c0 + n))
        dm = dom[sl]; fil = filled[sl]
        must_new = dm & ~fil
        if not must_new.any(): continue
        cnt = int(dm.sum())
        tc = float(E[sl][dm].mean()); tsl = np.bincount(sb[sl][dm], minlength=5)[:5] / cnt
        triv = float((Tf["dr"][sl][dm] <= 1.5).mean()); twat = float((Tf["dw"][sl][dm] <= 1.6).mean())
        trow = float(r0 + n // 2); tcl = int(np.bincount(f["climate"][sl][dm]).argmax())
        dc = (3.0 * np.abs(ccov - tc) + np.abs(cslope - tsl).sum(1) + 0.5 * np.abs(criv - triv) + 0.5 * np.abs(cwat - twat)
              + 1.5 * np.clip((np.abs(crow - trow) - 120) / 300, 0, 1) + 0.3 * (ccl != tcl))
        k = min(QK, len(dc) - 1); idx = np.argpartition(dc, k)[:k]
        blocks = np.stack([src[a:a + n, b:b + n] for a, b in zip(cy[idx], cx[idx])])
        dsuit = np.stack([suit[a:a + n, b:b + n] for a, b in zip(cy[idx], cx[idx])])
        old = canvas[sl]
        known = (~dm | fil).astype(np.float32); known[wat[sl]] *= 0.2
        bp = blocks != NO_TREE; op = old != NO_TREE
        mis = (bp != op[None]) + 0.3 * ((blocks != old[None]) & bp & op[None])
        ov = (mis * known[None]).sum((1, 2)) / max(float(known.sum()), 1.0)
        gm = (np.abs(dsuit - suit[sl][None]) * dm[None]).sum((1, 2)) / cnt
        cost = QW_OV * ov + 2.0 * QW_G * gm + QW_D * dc[idx] + QW_RE * used[idx]
        okk = np.nonzero(cost <= cost.min() + QTOL)[0]; j = int(okk[rng.integers(len(okk))])
        new = blocks[j]
        border = np.zeros((n, n), bool); border[0, :] = border[-1, :] = border[:, 0] = border[:, -1] = True
        must_old = ~dm | (border & fil)
        wpx = np.where(wat[sl], 0.2, 1.0).astype(np.float32)
        take = graph_cut(np.where(op, old, 255), np.where(bp[j], new, 255), must_old, must_new, nz[sl], wpx)
        wr = take & dm
        old[wr] = new[wr]; fil |= dm
        used[idx[j]] += 1; info["Q2_windows"] += 1
        rg = int(creg[idx[j]]); donor[rg] = donor.get(rg, 0) + int(wr.sum())
    tot = max(sum(donor.values()), 1)
    info["Q2_donor_regions"] = [(names[k] if 0 <= k < len(names) else str(k), round(100 * v / tot, 1))
                                for k, v in sorted(donor.items(), key=lambda kv: -kv[1])[:15]]
    info["Q2_donor_reuse_max"] = int(used.max())
    log(f"trees_polish Q2: {info['Q2_windows']:,} windows over {info['Q2_hexes']:,} domain hexes, "
        f"{info['Q2_donor_windows']:,} donor windows; top donors {info['Q2_donor_regions'][:6]}")
    _QCACHE[key] = (canvas.copy(), suit, dict(info))
    return dom, suit, info


def polish(out, f, names, w, h, NA, cut, log=print):
    """Returns (new out, info dict). `cut` = hexes the trees_x15 clean-up will clear afterwards (counted as empty)."""
    out = out.copy(); land = f["terr"] == 0
    rows = np.arange(h)[:, None].repeat(w, 1)
    G = groups(f, names, w, h); info = {}
    # P1 (H4): subtropical species in the north-west / north -> climate species
    m1 = np.isin(G, REMAP_GROUPS) & (rows >= NORTH_ROW) & np.isin(out, SUBTROP)
    hs = hash01(w, h, 11); n1 = 0
    for cl in np.unique(f["climate"][m1]):
        large, small = REMAP.get(int(cl), REMAP[4])
        for src in SUBTROP:
            mm = m1 & (f["climate"] == cl) & (out == src)
            if not mm.any(): continue
            ch = np.array(small if SMALL[src] else large)
            out[mm] = ch[np.minimum((hs[mm] * len(ch)).astype(int), len(ch) - 1)]; n1 += int(mm.sum())
    info["P1_subtropical_remapped"] = n1
    A = (G == "nomad") & land & (f["climate"] == 0)
    tgt = int(round(NOMAD_ARID_TARGET * A.sum())); hp = hash01(w, h, 23)
    dom = np.isin(G, SMOOTH_GROUPS) & land & ~cut
    info.update(P2_filled=0, P2_cleared=0, P3_dropped_small_patch_hexes=0, P3_dropped_ring_hexes=0,
                P3_cover_before=float(((out != NO_TREE) & A & ~cut).sum() / max(A.sum(), 1)))

    def majority(out):
        """P2 (M1): 7-hex majority (hex + 6 neighbours >= 4 trees) on hexi / nomad / np_new land, to a fixed point."""
        for _ in range(8):
            T = (out != NO_TREE) & land & ~cut
            want = (T.astype(np.int16) + ncount(T, NA)) >= 4
            on = dom & want & ~T; off = dom & ~want & T
            if not on.any() and not off.any(): break
            if on.any():                                     # class = commonest class among the tree neighbours
                votes = np.zeros((int(on.sum()), 20), np.int16); rr, cc = np.nonzero(on)
                for nr, nc, v in NA:
                    k = out[nr[rr, cc], nc[rr, cc]]; ok = v[rr, cc] & T[nr[rr, cc], nc[rr, cc]]
                    np.add.at(votes, (np.nonzero(ok)[0], k[ok]), 1)
                votes[:, NO_TREE] = -1
                out[rr, cc] = votes.argmax(1).astype(out.dtype)
            out[off] = NO_TREE; info["P2_filled"] += int(on.sum()); info["P2_cleared"] += int(off.sum())

    def thin(out):
        """P3 (M1): nomad arid steppe cover -> target: small patches (< 4 hexes) first, then outer rings."""
        E = (out != NO_TREE) & A & ~cut
        if E.sum() <= tgt: return
        L, sizes = components(E, NA)
        small = np.nonzero(sizes < SMALL_PATCH)[0]
        if len(small):
            # drop whole small patches, smallest first (label order = raster scan order, deterministic), to the target
            excess = int(E.sum()) - tgt; kill = []
            for p in sorted(small.tolist(), key=lambda p: (sizes[p], p)):
                if excess <= 0: break
                kill.append(p); excess -= int(sizes[p])
            km = E & np.isin(L, kill); out[km] = NO_TREE; E &= ~km; info["P3_dropped_small_patch_hexes"] += int(km.sum())
        while E.sum() > tgt:                                 # peel: fewest tree neighbours first, then a stable hash
            nb = ncount(E, NA); edge = E & (nb < 6)
            excess = int(E.sum()) - tgt
            if edge.sum() <= excess: sel = edge
            else:
                rr, cc = np.nonzero(edge); o = np.lexsort((hp[rr, cc], nb[rr, cc]))[:excess]
                sel = np.zeros_like(E); sel[rr[o], cc[o]] = True
            out[sel] = NO_TREE; E &= ~sel; info["P3_dropped_ring_hexes"] += int(sel.sum())

    if QUILT:
        # Q2: terrain-guided quilting of the forest layer from vanilla (replaces the majority filter); P1 again on it
        qd, suit, qinfo = quilt_forests(out, f, names, w, h, cut, log=log)
        info.update(qinfo)
        m1q = qd & (rows >= NORTH_ROW) & np.isin(out, SUBTROP)
        for cl in np.unique(f["climate"][m1q]):
            large, small = REMAP.get(int(cl), REMAP[4])
            for src in SUBTROP:
                mm = m1q & (f["climate"] == cl) & (out == src)
                if not mm.any(): continue
                ch = np.array(small if SMALL[src] else large)
                out[mm] = ch[np.minimum((hs[mm] * len(ch)).astype(int), len(ch) - 1)]; info["P1_subtropical_remapped"] += int(mm.sum())
        # Q3: nomad arid cover target, least suitable tree hexes go first (terrain-shaped edges, no ring peeling)
        E = (out != NO_TREE) & A & ~cut
        info["P3_cover_before"] = float(E.sum() / max(A.sum(), 1))
        if E.sum() > tgt:
            rr, cc = np.nonzero(E); o = np.lexsort((hp[rr, cc], suit[rr, cc]))[:int(E.sum()) - tgt]
            out[rr[o], cc[o]] = NO_TREE; info["P3_dropped_ring_hexes"] = int(len(o))
        info["P23_rounds"] = 1
    else:
        # P2 + P3 alternate until neither changes anything (the result is then stable when the next build re-applies
        # them); a final P3 guarantees the cover target even if the cap is hit
        for rnd in range(8):
            prev = out.copy(); majority(out); thin(out)
            if (prev == out).all(): break
        else:
            thin(out)
        info["P23_rounds"] = rnd + 1
    info["P3_cover_after"] = float(((out != NO_TREE) & A & ~cut).sum() / max(A.sum(), 1))
    # P4 (M1 optional): Korea lowland fir -> katsura on a stable half
    K = (G == "korea_ne") & land; hgt = hex_height(w, h); n4 = 0
    if hgt is not None and K.any():
        t1 = np.percentile(hgt[K], 100 / 3)
        # clumped choice (whole groves switch, not a per-hex checkerboard): fixed-seed smooth noise against its own
        # map-wide quantile, so the chosen hexes never depend on the current raster (idempotent)
        from scipy import ndimage as ndi
        nz = ndi.gaussian_filter(np.random.default_rng(37).random((h, w)), 3.0)
        pick = nz < np.quantile(nz, KOREA_FIR_TO_KATSURA)
        for a, b in FIR.items():
            mm = K & (out == a) & (hgt <= t1) & pick; out[mm] = b; n4 += int(mm.sum())
    info["P4_korea_fir_to_katsura"] = n4
    log("trees_polish:", info)
    return out, info


# ---------------------------------------------------------------- dry-run report (trees_x15.py --dry) -------------------
REPORT_GROUPS = ("vanilla", "central", "south", "np_old", "np_old_n", "hexi", "nomad", "korea_ne", "korea_s", "np_new")


def _patches(t):
    """The proposal's forest-structure metric (py/trees.py): 4-connected labels, edge = not in the binary erosion."""
    from scipy import ndimage as ndi
    lab, n = ndi.label(t)
    if n == 0: return 0.0, 0.0, 0
    sizes = np.bincount(lab.ravel())[1:]; edge = t & ~ndi.binary_erosion(t)
    return float(sizes.mean()), float(edge.sum() / t.sum()), int(n)


def metrics(B, G):
    out, f = B["out"], B["f"]; h, w = out.shape; land = f["terr"] == 0
    rows = np.arange(h)[:, None].repeat(w, 1); tree = (out != NO_TREE) & land; M = {}
    for g in REPORT_GROUPS:
        m = (G == g) & land
        if not m.any(): continue
        tn = tree & m & (rows >= 700); d = dict(land=int(m.sum()), cover=float(tree[m].mean()))
        d["subtrop_share_row700"] = float(np.isin(out[tn], SUBTROP).mean()) if tn.any() else 0.0
        d["mean_patch"], d["edge_share"], d["patches"] = _patches(tree & m)
        tm = tree & m; d["fir_share"] = float(np.isin(out[tm], (4, 6)).mean()) if tm.any() else 0.0
        for cl, nm in ((0, "arid"), (1, "cold"), (4, "temperate")):
            mc = m & (f["climate"] == cl)
            if mc.sum() >= 500: d[f"cover_{nm}"] = float(tree[mc].mean())
        d.update(_shape(tree & m))
        M[g] = d
    return M


_NA = {}


def _shape(t):
    """hex-adjacency forest patches: area-weighted patch size (hexes; the size of the wood a random tree hex is in),
    median roundness of patches >= 10 hexes (isoperimetric quotient on hexes: 2*pi*3*sqrt(3)*n / e^2, e = open hex
    edges; a hexagonal disc ~0.9, ragged / elongated shapes lower) and the share of tree hexes with >= 1 open edge."""
    from hexgrid import neighbour_arrays
    h, w = t.shape
    if (h, w) not in _NA: _NA[(h, w)] = neighbour_arrays(h, w)
    NA = _NA[(h, w)]
    L, sizes = components(t, NA)
    if not len(sizes): return dict(patch_area_weighted=0.0, roundness_median=None, open_edge_share=0.0)
    e = np.zeros(t.shape, np.int16)
    for nr, nc, v in NA: e += t & ~(v & t[nr, nc])
    pe = np.bincount(L[t], weights=e[t], minlength=len(sizes))
    big = sizes >= 10
    q = 2 * np.pi * 3 * np.sqrt(3) * sizes[big] / np.maximum(pe[big], 1) ** 2
    return dict(patch_area_weighted=float((sizes.astype(float) ** 2).sum() / sizes.sum()),
                roundness_median=float(np.median(q)) if big.any() else None,
                open_edge_share=float((e[t] > 0).mean()))


def _preview(B0, B1, G, box, path, scale=1):
    pal = np.array(B0["pal"][:60], np.uint8).reshape(20, 3); f = B0["f"]
    c0, c1, r0, r1 = box
    tiles = []
    for B in (B0, B1):
        o = B["out"][r0:r1, c0:c1]; rgb = pal[o].copy()
        land = f["terr"][r0:r1, c0:c1] == 0
        rgb[(o == NO_TREE) & land] = (226, 214, 180); rgb[~land] = (18, 30, 80)
        rgb[(o == NO_TREE) & land & (G[r0:r1, c0:c1] == "vanilla")] = (200, 196, 186)      # shows the group borders
        tiles.append(rgb[::-1])                                                            # north up
    gap = np.full((tiles[0].shape[0], 6, 3), 255, np.uint8)
    im = Image.fromarray(np.concatenate([tiles[0], gap, tiles[1]], 1))
    if scale != 1: im = im.resize((int(im.width * scale), int(im.height * scale)), Image.NEAREST)
    im.save(path)


V2_OUT = HERE.parent.parent / "output" / "polish" / "blend_v2" / "trees"


def report_groups(f, names, w, h):
    """groups() with np_old split into np_old_n (the quilt domain's north / Hexi-zone part) and np_old, and Korea's
    south (protected in blend_v2) as korea_s."""
    import blend_v2 as BV
    G = groups(f, names, w, h).copy()
    _, code = quilt_domain(f, names, w, h)
    G[code == BV.NPOLDF] = "np_old_n"
    G[(G == "korea_ne") & (code != BV.KNE)] = "korea_s"
    return G


def current_raster(B0):
    """the tree raster now in terrain/ (what the game has: last trees_x15 build, old polish), per hex."""
    import trees_x15
    a = np.array(Image.open(HERE / "terrain" / trees_x15.TREE))
    return dict(B0, out=trees_x15.hexvals(a, B0["w"], B0["h"]))


def _preview3(Bc, B1, G, ct, cv, path, size=(110, 170), scale=3):
    pal = np.array(Bc["pal"][:60], np.uint8).reshape(20, 3); f = Bc["f"]; h, w = Bc["out"].shape
    hg = hex_height(w, h)
    shade = np.ones((h, w), np.float32)
    if hg is not None:
        gy, gx = np.gradient(hg.astype(np.float32)); shade = np.clip(1 + (gx - gy) / 2500.0, 0.6, 1.3)
    def tile(B, c):
        r0 = int(np.clip(c[0] - size[0] // 2, 0, h - size[0])); c0 = int(np.clip(c[1] - size[1] // 2, 0, w - size[1]))
        sl = (slice(r0, r0 + size[0]), slice(c0, c0 + size[1]))
        o = B["out"][sl]; rgb = pal[o].astype(np.float32)
        land = f["terr"][sl] == 0
        rgb[(o == NO_TREE) & land] = (226, 214, 180); rgb *= shade[sl][..., None]; rgb[~land] = (18, 30, 80)
        rgb = np.clip(rgb, 0, 255).astype(np.uint8)[::-1]
        return np.repeat(np.repeat(rgb, scale, 0), scale, 1)
    a, b, c = tile(B1, cv), tile(Bc, ct), tile(B1, ct)
    gap = np.full((a.shape[0], 6, 3), 255, np.uint8)
    from PIL import ImageDraw
    im = Image.fromarray(np.concatenate([a, gap, b, gap, c], 1)); d = ImageDraw.Draw(im)
    for i, t in enumerate(("VANILLA reference", "CURRENT (in game)", "V2 (quilted)")):
        d.text((4 + i * (a.shape[1] + 6), 3), t, fill=(0, 0, 0))
    im.save(path, optimize=True)


def report(B0, B1, chain, base, out_dir):
    import json
    if QUILT: out_dir = V2_OUT; out_dir.mkdir(parents=True, exist_ok=True)
    f, names, w, h = B0["f"], B0["names"], B0["w"], B0["h"]
    G = report_groups(f, names, w, h) if QUILT else groups(f, names, w, h)
    Bc = current_raster(B0)
    M0, M1, Mc = metrics(B0, G), metrics(B1, G), metrics(Bc, G)
    changed = {g: int(((B0["out"] != B1["out"]) & (G == g)).sum()) for g in np.unique(G).tolist()}
    gl = np.unique(G).tolist()
    dif = lambda X, Y: {g: int(((X["out"] != Y["out"]) & (G == g)).sum()) for g in gl}
    rerun = [dif(chain[i], chain[i + 1]) for i in range(len(chain) - 1)]
    rerun_base = dif(base[0], base[1]); Mlast = metrics(chain[-1], G)
    res = dict(before=M0, after=M1, after_build4=Mlast, hexes_changed_by_group=changed, rerun_changes_by_group=rerun,
               rerun_changes_unpolished_pipeline=rerun_base, polish=B1["polish"], rerun_polish=[c["polish"] for c in chain[1:]])
    json.dump(res, open(out_dir / "metrics.json", "w"), indent=1)
    res["current_file"] = Mc; json.dump(res, open(out_dir / "metrics.json", "w"), indent=1, default=str)
    keys = ("cover", "cover_arid", "cover_cold", "cover_temperate", "subtrop_share_row700", "mean_patch", "patch_area_weighted",
            "edge_share", "open_edge_share", "roundness_median", "fir_share")
    lines = ["group      metric                 unpolished  current(game)    after  after 4 builds   vanilla"]
    def fm(k, x):
        if x is None: return "       -"
        return f"{x:8.1f}" if k in ("mean_patch", "patch_area_weighted") else (f"{x:8.2f}" if k == "roundness_median" else f"{100 * x:7.1f}%")
    for g in REPORT_GROUPS:
        if g not in M0: continue
        for k in keys:
            if k in M0[g]:
                lines.append(f"{g:10s} {k:22s} {fm(k, M0[g][k])}    {fm(k, Mc[g].get(k))} {fm(k, M1[g][k])} {fm(k, Mlast[g][k])}"
                             f"        {fm(k, M1['vanilla'].get(k))}")
    lines.append(f"hexes changed by polish per group: {changed}")
    for i, r in enumerate(rerun): lines.append(f"build {i + 2} vs build {i + 1} (input = previous output) changes: {r}")
    lines.append(f"unpolished pipeline, build 2 vs 1 changes (pre-existing top-up ratchet): {rerun_base}")
    txt = "\n".join(lines); print(txt); (out_dir / "metrics.txt").write_text(txt + "\n", encoding="utf-8")
    # previews: before | after, north up, 1 px per hex
    def bbox(sel, pad=10):
        rr, cc = np.nonzero(sel); return (max(cc.min() - pad, 0), min(cc.max() + pad, w), max(rr.min() - pad, 0), min(rr.max() + pad, h))
    if not QUILT:
        _preview(B0, B1, G, bbox(G == "hexi", 40), out_dir / "preview_nw_hexi.png")
        _preview(B0, B1, G, bbox(G == "nomad"), out_dir / "preview_steppe_nomad.png")
        _preview(B0, B1, G, bbox(G == "korea_ne"), out_dir / "preview_korea_ne.png")
        _preview(B0, B1, G, (0, w, 0, h), out_dir / "preview_full_half.png", scale=0.5)
    else:
        # vanilla reference | current (game) | after, same scale (3 px / hex), north up, hillshade under the woods
        hx = lambda x, z: (int(round(h - 1 - (874.18 - z) / 0.0964 / 8)), int(x / 0.0834 / 8))     # world -> (row, col)
        van_arid, van_temp = hx(375, 790), hx(560, 600)
        hr, hc = np.nonzero(G == "hexi")
        crops = {"ordos_430_705": (hx(430, 705), van_arid), "north_480_760": (hx(480, 760), van_arid),
                 "steppe_north_band": ((h - 1 - 80, 900), van_temp), "korea_ne": ((1000, 1300), (930, 1100)),
                 "hexi_corridor": ((int(hr.mean()), int(hc.mean())), van_arid), "padding_nw": ((1000, 80), van_arid)}
        for nm, (ct, cv) in crops.items():
            _preview3(Bc, B1, G, ct, cv, out_dir / f"trees_v2_{nm}.png")
        _preview(Bc, B1, G, (0, w, h // 2, h), out_dir / "trees_v2_north_half_current_vs_after.png", scale=1)
    print("dry report written to", out_dir)
