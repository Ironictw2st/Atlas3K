#!/usr/bin/env python3
"""Missing-tile detector: tile-map cells that no tile_list.bin record covers (see-through holes in game).

Every tile-map cell (quarter-lf pixel, 2x2 per hex) must be covered by a placed tile: base tiles (generic,
mountains, sea, coast) or line tiles (rivers, roads, canals - these carry their own geometry). Coverage follows
BOB's height query (src/Atlas3K.Core/Campaign/GlobalMesh/TileCoverage.cs): a record covers w x h cells from
(x, y) (w/h swapped for orientation 0x20/0x80), and the sub-tile, rotated by the orientation, must be set in the
tile database mask. y = 0 is the south row.

Reports:
  - tile paths in tile_list.bin that the tile database doesn't know (BOB's "Failed to find tile": nothing placed)
  - uncovered cells, grouped into clusters, with the hex (col,row) and region of each cluster
  - cells covered more than once by base tiles are normal (overlap at edges) and not reported
  - clusters are classified: settlement (on/next to slot or sprawl hexes - filled by settlement models, vanilla has
    them), edge (touching the map border), suspect (everything else - the ones to look at in game)
  - an image: grey = covered, red suspect, yellow settlement, blue edge (north up), optional

usage: tile_holes.py <tile_list.bin> <hex map.hex> [out.png] [--db <tile database dir>]
Run it on vanilla first: vanilla's own count is the baseline for "normal".
"""
import argparse, os, sys
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
for p in (HERE, os.path.join(HERE, "..", "guandu"), os.path.join(HERE, ".."), os.path.join(HERE, "..", "derived_maps")):
    sys.path.insert(0, p)
import tiles_lib as T


def norm(p):
    p = p.replace("/", "\\").lower()
    return p if p.endswith("\\") else p + "\\"


def coverage(tl_path, db):
    paths, climates, floats, ints, rec = T.read_tile_list(tl_path)
    W, H = ints[1], ints[2]
    info = [db.get(norm(p)) for p in paths]
    unknown = sorted({paths[i] for i in set(rec["path"].tolist()) if info[i] is None})
    cov = np.zeros((H, W), np.uint8)                        # number of records covering the cell
    for r in rec:
        t = info[r["path"]]
        if t is None: continue
        tw, th, mask = t["w"], t["h"], t["mask"]
        o = r["orient"] & 0xF0
        w, h = (th, tw) if o in (0x20, 0x80) else (tw, th)
        for j in range(h):
            y = r["y"] + j
            if y >= H: break
            for i in range(w):
                x = r["x"] + i
                if x >= W: break
                if o == 0x20: row, col = i, tw - j - 1
                elif o == 0x40: row, col = th - j - 1, tw - i - 1
                elif o == 0x80: row, col = th - i - 1, j
                else: row, col = j, i
                mr = th - row - 1                           # mask rows are stored north first
                if mask and not (len(mask) == tw * th and mask[mr * tw + col] == "1"): continue
                cov[y, x] = min(255, cov[y, x] + 1)
    return cov, unknown, (W, H), len(rec)


def clusters(hole):
    """4-connected components of hole cells: list of (size, [ys], [xs])."""
    seen = np.zeros_like(hole); out = []
    for y0, x0 in zip(*np.nonzero(hole)):
        if seen[y0, x0]: continue
        st = [(y0, x0)]; seen[y0, x0] = True; ys, xs = [], []
        while st:
            y, x = st.pop(); ys.append(y); xs.append(x)
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                a, b = y + dy, x + dx
                if 0 <= a < hole.shape[0] and 0 <= b < hole.shape[1] and hole[a, b] and not seen[a, b]:
                    seen[a, b] = True; st.append((a, b))
        out.append((len(ys), ys, xs))
    return sorted(out, key=lambda c: -c[0])


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("tile_list"); ap.add_argument("hex"); ap.add_argument("out", nargs="?")
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--all", action="store_true", help="settlement clusters are holes too (vanilla has 0 of them: "
                    "the town models do NOT fill uncovered cells - 2026-10-01 baseline)")
    ap.add_argument("--feedback", help="merge the hexes of suspect clusters into this json (tile_repair.py reads it; "
                    "counts how many rounds each hex has been a hole)")
    a = ap.parse_args()
    db = T.read_db()
    cov, unknown, (W, H), n = coverage(a.tile_list, db)
    import hexmap
    from regions_plan import load
    f, names, hw, hh = load(a.hex)
    hole = cov == 0
    print(f"tile_list {W}x{H} cells, {n:,} records; hex grid {hw}x{hh}")
    print(f"tile paths unknown to the tile database (never placed): {len(unknown)}")
    for p in unknown[:20]: print("   ", p)
    cl = clusters(hole)
    sx, sy = W / hw, H / hh
    # classify: settlement footprints (slot/sprawl hexes, filled by the settlement models - vanilla has them too),
    # the map edge, and the rest (suspects: see-through in game unless something else fills them)
    town = (f["slot"] >= 0) | (f["sprawl"] > 0)
    town = town | np.roll(town, 1, 0) | np.roll(town, -1, 0) | np.roll(town, 1, 1) | np.roll(town, -1, 1)   # + 1 ring
    kinds = {"settlement": [], "edge": [], "suspect": []}
    img_kind = np.zeros((H, W), np.uint8)
    for size, ys, xs in cl:
        ys, xs = np.array(ys), np.array(xs)
        hc = np.minimum((xs / sx).astype(int), hw - 1); hr = np.minimum((ys / sy).astype(int), hh - 1)
        if (ys.min() < 2) | (xs.min() < 2) | (ys.max() > H - 3) | (xs.max() > W - 3): k = "edge"
        elif town[hr, hc].mean() > 0.5 and not a.all: k = "settlement"
        else: k = "suspect"
        kinds[k].append((size, ys, xs)); img_kind[ys, xs] = {"settlement": 1, "edge": 2, "suspect": 3}[k]
    print(f"uncovered cells: {int(hole.sum()):,} in {len(cl)} clusters: "
          + ", ".join(f"{k} {sum(s for s, _, _ in v):,} cells / {len(v)} clusters" for k, v in kinds.items()))
    print("largest suspects (hex col,row; row 0 = south):")
    for size, ys, xs in kinds["suspect"][:a.top]:
        c = min(int(np.mean(xs) / sx), hw - 1); r = min(int(np.mean(ys) / sy), hh - 1)
        reg = f["region"][r, c]; rn = names[reg] if 0 <= reg < len(names) else "-"
        print(f"   {size:6d} cells  around hex ({c},{r})  terr {f['terr'][r, c]}  road {int(f['road'][r, c] > 0)}  "
              f"river {int(f['river'][r, c] > 0)}  region {rn}")
    if a.feedback:
        import json
        fb = json.load(open(a.feedback)) if os.path.exists(a.feedback) else {}
        hexes = set()
        for size, ys, xs in kinds["suspect"]:
            for y, x in zip(ys, xs):
                c = int(x) // 2; hexes.add((c, (int(y) - (c & 1)) // 2))    # tile-map cell (y = 0 south) -> hex
        for c, r in hexes: fb[f"{c},{r}"] = fb.get(f"{c},{r}", 0) + 1
        json.dump(fb, open(a.feedback, "w")); print(f"feedback: {len(hexes)} hexes -> {a.feedback} ({len(fb)} total)")
    if a.out:
        img = np.zeros((H, W, 3), np.uint8); img[cov > 0] = (40, 40, 40)
        img[img_kind == 1] = (255, 200, 0); img[img_kind == 2] = (0, 120, 255); img[img_kind == 3] = (255, 0, 0)
        Image.fromarray(img[::-1]).save(a.out); print("wrote", a.out, "(red suspect, yellow settlement, blue edge)")


if __name__ == "__main__":
    main()
