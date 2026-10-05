"""Per-cell region order in BOB's global_props.bin vs a CA_STD hash map emulation (research/trees/camap.py, validated
on the tree type order: CA::murmur_hash from calibs, 1 bucket growing to 2b+1, re-bucketing in list order).
Insertion order candidates per cell: regions by first (lowest) entity id, by first Seq (scene order), ...
usage: cell_map_order.py <bob global_props.bin> <native trace.csv>"""
import collections, csv, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent)); sys.path.insert(0, str(Path(__file__).parent.parent / "trees"))
from gp_entries import parse
from camap import ca_map_order

names, _, _ = parse(sys.argv[1])
bob = collections.defaultdict(list)
for n in names:
    m = re.search(r"bmd_objects\.(.+)\.(\d+)\.bin$", n)
    if m and not re.search(r"\.\d+\.\d+\.bin$", n): bob[int(m.group(2))].append(m.group(1))
first_id, first_seq = {}, {}
for r in csv.reader(open(sys.argv[2], encoding="utf-8")):
    m = re.search(r"bmd_objects\.(.+)\.(\d+)\.(\d+)\.bin$", r[0]); key = (m.group(1), int(m.group(2)))
    i, s = int(r[2], 16), int(r[5])
    first_id[key] = min(first_id.get(key, 1 << 64), i); first_seq[key] = min(first_seq.get(key, 1 << 62), s)
for label, key in (("by first id", first_id), ("by first seq", first_seq)):
    ok = tot = ent_ok = ent = 0
    for c, rs in bob.items():
        seq = sorted(rs, key=lambda r: key.get((r, c), 1 << 64))
        pred = ca_map_order(seq)
        tot += 1; ok += pred == rs; ent += len(rs); ent_ok += sum(a == b for a, b in zip(pred, rs))
    print(f"{label:14s} cells matched {ok}/{tot}; entries in place {ent_ok}/{ent}")
