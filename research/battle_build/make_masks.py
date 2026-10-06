"""Compare all bob_run* snapshots of each corpus project and write masks of bytes that change between BOB runs.

usage: make_masks.py [corpus root]
Writes <corpus>/<id>/masks.json: {"<relative path>": [[start, end_exclusive], ...]} for files whose bytes differ
between runs (same size in every run). Masked ranges are widened to whole 4-byte words (the varying fields are
uninitialised u32s / floats). Files whose size differs between runs are listed under "_unstable_size".
Also prints a per-project summary.
"""
import glob, json, os, sys

CORPUS = sys.argv[1] if len(sys.argv) > 1 else r"Z:/Claude/BattleMaps/out/battle_parity"
MAX_MASK_WORDS = 16   # more varying words than this = a record-order variant, not uninitialised bytes
for proj in sorted(glob.glob(os.path.join(CORPUS, "*", ""))):
    runs = sorted(d for d in glob.glob(os.path.join(proj, "bob_run*")) if os.path.isdir(d))
    if len(runs) < 2:
        continue
    base = runs[0]
    rels = sorted(os.path.relpath(os.path.join(r, f), base).replace("\\", "/")
                  for r, _, fs in os.walk(base) for f in fs)
    masks, unstable, variants, varying = {}, [], [], 0
    for rel in rels:
        datas = [open(os.path.join(r, rel), "rb").read() for r in runs if os.path.exists(os.path.join(r, rel))]
        if len(datas) != len(runs) or len({len(d) for d in datas}) != 1:
            unstable.append(rel); continue
        diff = set()
        a = datas[0]
        for b in datas[1:]:
            if a != b:
                diff.update(i for i in range(len(a)) if a[i] != b[i])
        if not diff:
            continue
        varying += 1
        words = sorted({i & ~3 for i in diff})
        if len(words) > MAX_MASK_WORDS:     # not stray memory but a different ORDER of records: keep as variants
            variants.append(rel); continue
        ranges = []
        for w in words:
            if ranges and ranges[-1][1] == w:
                ranges[-1][1] = w + 4
            else:
                ranges.append([w, w + 4])
        masks[rel] = [[s, min(e, len(a))] for s, e in ranges]
    out = {**masks, "_unstable_size": unstable, "_order_variants": variants, "_runs": [os.path.basename(r) for r in runs]}
    with open(os.path.join(proj, "masks.json"), "w") as f:
        json.dump(out, f, indent=1)
    print(f"{os.path.basename(proj.rstrip(os.sep))}: {len(runs)} runs, {len(rels)} files, {varying} with varying bytes, "
          f"{len(unstable)} unstable-size, order variants {variants}; " + "; ".join(f"{k} {v}" for k, v in masks.items()))
