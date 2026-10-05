"""Compare non-prop objects (props-cells *.other.csv) between BOB and native: match by (kind, name, x, y, z) as float32
bits; report region / cell / bucket / seasons / tags differences per kind. usage: other_compare.py <bob.other.csv> <native.other.csv>"""
import csv, collections, re, sys
import numpy as np
f32 = lambda v: int(np.float32(float(v)).view(np.int32))


def load(p):
    out = collections.defaultdict(list)
    for r in csv.DictReader(open(p, encoding="utf-8")):
        m = re.search(r"\.(\d+)\.(\d+)\.bin$", r["bmd"])
        r["cell"], r["bucket"] = (int(m.group(1)), int(m.group(2))) if m else (-1, -1)
        out[(r["kind"], r["path"].lower(), f32(r["x"]), f32(r["y"]), f32(r["z"]))].append(r)
    return out


A, B = load(sys.argv[1]), load(sys.argv[2])
kinds = collections.Counter(k[0] for k in A); kb = collections.Counter(k[0] for k in B)
print("objects bob", dict(kinds), " native", dict(kb))
for kind in sorted(set(kinds) | set(kb)):
    ka = {k for k in A if k[0] == kind}; kbb = {k for k in B if k[0] == kind}
    common = ka & kbb
    d = collections.Counter()
    for k in common:
        a, b = A[k][0], B[k][0]
        for f in ("region", "cell", "bucket", "seasons", "tags"):
            if a[f] != b[f]: d[f] += 1
    print(f"{kind:6s} bob {len(ka)} native {len(kbb)} common {len(common)} only bob {len(ka - kbb)} only native {len(kbb - ka)}; diffs {dict(d)}")
