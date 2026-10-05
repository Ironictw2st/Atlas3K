"""Compare two folders of BOB-style outputs file by file, masking BOB's uninitialised bytes:
global meshes 0x148-0x14B (all) and 0xA5-0xA7 (sea meshes); river models 0xA5-0xA7 and 0x31A-0x31B.
usage: cmp_dirs.py <native dir> <bob dir> [glob]"""
import fnmatch, os, sys
from pathlib import Path

nat, ref = Path(sys.argv[1]), Path(sys.argv[2])
pat = sys.argv[3] if len(sys.argv) > 3 else "*"
MASK = {"land_mesh": [range(0x148, 0x14C)], "sea_mesh": [range(0x148, 0x14C), range(0xA5, 0xA8)],
        "river_": [range(0xA5, 0xA8), range(0x31A, 0x31C)]}


def masked(name, b):
    b = bytearray(b)
    if name.endswith(".rigid_model_v2"):
        for k, rs in MASK.items():
            if name.startswith(k):
                for r in rs:
                    for i in r:
                        if i < len(b): b[i] = 0
    return bytes(b)


names = sorted(f for f in os.listdir(ref) if fnmatch.fnmatch(f, pat))
same, diff, missing = 0, [], []
for f in names:
    p = nat / f
    if not p.exists(): missing.append(f); continue
    a, b = masked(f, p.read_bytes()), masked(f, (ref / f).read_bytes())
    if a == b: same += 1
    else: diff.append((f, len(a), len(b), next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))))
extra = sorted(set(f for f in os.listdir(nat) if fnmatch.fnmatch(f, pat)) - set(names))
print(f"{len(names)} reference files: identical {same}, different {len(diff)}, missing in native {len(missing)}, native-only {len(extra)}")
for d in diff[:12]: print("  differs", d)
if missing: print("  missing", missing[:10])
if extra: print("  native-only", extra[:10])
