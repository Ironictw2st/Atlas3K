"""Check the QTU euler->quaternion->matrix emulation (matrix_fit.qtu_*) against every BOB prop record whose entity is
found directly in a layer. usage: matrix_check.py <layers dir> <bob_props_raw.csv>"""
import csv, glob, os, re, sys, collections, io, contextlib
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
with contextlib.redirect_stdout(io.StringIO()): import matrix_fit as M
F = np.float32
f32 = lambda v: int(F(float(v)).view(np.int32))
tr_re = re.compile(r'<ECTransform position="([^"]*)" rotation="([^"]*)" scale="([^"]*)"')
mesh_re = re.compile(r'<(?:ECMesh|ECDecal) model_path="([^"]*)"')
E = {}
for p in glob.glob(os.path.join(sys.argv[1], "*.layer")):
    model = None
    for line in open(p, encoding="utf-8"):
        if "<entity " in line: model = None
        m = mesh_re.search(line)
        if m: model = m.group(1).lower(); continue
        m = tr_re.search(line)
        if m and model:
            pos = m.group(1).split(); E.setdefault((model, f32(pos[0]), f32(pos[2])), []).append((pos, m.group(2).split(), m.group(3).split()))
c = collections.Counter(); ex = []
for r in csv.DictReader(open(sys.argv[2], encoding="utf-8")):
    k = (r["path"].lower(), f32(r["x"]), f32(r["z"]))
    if k not in E: c["unmatched"] += 1; continue
    bob = np.frombuffer(bytes.fromhex(r["m"]), "<u4"); best = None
    for pos, rot, sc in E[k]:
        R = M.qtu_matrix(M.qtu_quat(*[float(v) for v in rot]), [float(v) for v in sc], [float(v) for v in pos])
        got = np.array([R[j][i] for i in range(3) for j in range(3)], dtype=np.float32).view(np.uint32)
        d = np.abs(got.astype(np.int64) - bob.astype(np.int64))
        if best is None or d.max() < best[0].max(): best = (d, rot, sc)
    d, rot, sc = best
    if (d == 0).all(): c["exact"] += 1
    else:
        c["max ulp %s" % ("1" if d.max() == 1 else "2-4" if d.max() <= 4 else ">4")] += 1
        if len(ex) < 12: ex.append((rot, sc, [i for i in range(9) if d[i]], int(d.max())))
print(dict(c))
for e in ex: print(e)
