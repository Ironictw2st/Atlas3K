#!/usr/bin/env python3
"""Round 8: move hex-space inputs from the round-6/7 warp (PinnedNorthWarp x1.4 both ways, 1428 x 896) to the
current warp (warp.current(): "taller only", no x scaling). Old new-hex -> 190E hex (old inverse) -> new hex.
Pair lists (int32 (col,row)) are mapped point by point and de-duplicated; (h, w) grids are resampled (for each new
hex: new inverse -> 190E -> old forward -> nearest old hex). Originals were backed up in
output/backups/main190_pre_xc230_*/ before this runs; it refuses to run twice (a stamp file)."""
import json, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
from warp import current
from warp3 import PinnedNorthWarp

OLD = PinnedNorthWarp(1.4, 330, 450)            # rounds 6-7
NEW = current()
OW, OH = OLD.W, OLD.H
NORTH = HERE / "research_r6" / "north"
STAMP = HERE / "research_r6" / "retargeted_to_tall.txt"


def pairs(a):
    x, y = OLD.inverse(a[:, 0].astype(float), a[:, 1].astype(float))
    nx, ny = NEW.forward(x, y)
    out = np.stack([np.rint(nx), np.rint(ny)], 1).astype(np.int32)
    ok = (out[:, 0] >= 0) & (out[:, 0] < NEW.W) & (out[:, 1] >= 0) & (out[:, 1] < NEW.H)
    return np.unique(out[ok], axis=0)


def grid(a):
    rr, cc = np.mgrid[0:NEW.H, 0:NEW.W]
    x, y = NEW.inverse(cc.ravel().astype(float), rr.ravel().astype(float))
    ox, oy = OLD.forward(x, y)
    ox = np.clip(np.rint(ox).astype(int), 0, OW - 1); oy = np.clip(np.rint(oy).astype(int), 0, OH - 1)
    return a[oy, ox].reshape(NEW.H, NEW.W)


def main():
    if STAMP.exists(): sys.exit(f"already retargeted ({STAMP.read_text().strip()})")
    print(f"old {OW}x{OH} -> new {NEW.W}x{NEW.H}")
    files = [NORTH / n for n in ("cull_blend.npy", "cull_imp_playable.npy", "zone_open.npy", "keep_range.npy", "open_nomad.npy",
                                 "height_flag.npy")] + [HERE / "research_r6" / "hexi_extension_hexes.npy"]
    for p in files:
        if not p.exists(): continue
        a = np.load(p)
        if a.ndim == 2 and a.shape[1] == 2:
            b = pairs(a); np.save(p, b); print(f"  {p.name}: {len(a)} -> {len(b)} hexes (pairs)")
        elif a.shape == (OH, OW):
            b = grid(a); np.save(p, b); print(f"  {p.name}: grid {a.shape} -> {b.shape}")
        else:
            print(f"  {p.name}: shape {a.shape} left alone")
    nt = NORTH / "new_type.npy"
    if nt.exists():
        a = np.load(nt)
        if a.shape == (OH, OW): np.save(nt, grid(a)); print(f"  new_type.npy: grid -> {NEW.H}x{NEW.W}")
    sj = NORTH / "sites.json"
    if sj.exists():
        d = json.load(open(sj, encoding="utf-8"))
        def fix(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if k in ("hex", "site") and isinstance(v, list) and len(v) == 2 and all(isinstance(q, (int, float)) for q in v):
                        o[k] = [int(q) for q in pairs(np.array([v], float))[0]]
                    elif k == "fp" and isinstance(v, list) and v and isinstance(v[0], list):
                        pts = np.array([q[:2] for q in v], float)
                        x, y = OLD.inverse(pts[:, 0], pts[:, 1]); nx, ny = NEW.forward(x, y)
                        o[k] = [[int(round(a_)), int(round(b_))] + list(q[2:]) for a_, b_, q in zip(nx, ny, v)]
                    else: fix(v)
            elif isinstance(o, list):
                for v in o: fix(v)
        fix(d); json.dump(d, open(sj, "w", encoding="utf-8"), indent=1); print("  sites.json: hex fields moved")
    STAMP.write_text(f"retargeted {OW}x{OH} -> {NEW.W}x{NEW.H}\n")


if __name__ == "__main__":
    main()
