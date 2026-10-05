"""Score extent rules for BOB's quadtree cell choice. Joins BOB's props-cells CSV (cell) with the native props-dump CSV
(rotation, scale) by (path, x, y, z), takes model LOD0 bounds from model_bounds.json and, per rule, computes the deepest
of 7 levels whose cell holds the object's x/z extent. usage: cell_rules.py"""
import csv, json, math, re, collections
import numpy as np
D = r"Z:/Claude/TerryClone/output/props_parity/"
W, H = 986.0513305664062, 873.7957
FIRST = [sum(4 ** k for k in range(L)) for L in range(8)]
bounds = json.load(open(D + "model_bounds.json"))
f32 = lambda v: int(np.float32(float(v)).view(np.int32))
key = lambda r: (r["path"].lower(), f32(r["x"]), f32(r["y"]), f32(r["z"]))
dump = {}
for r in csv.DictReader(open(D + "native_dump.csv", encoding="utf-8")):
    if r["kind"] == "prop": dump[key(r)] = r
rows = []
for r in csv.DictReader(open(D + "bob_cells.csv", encoding="utf-8")):
    k = key(r)
    m = re.search(r"\.(\d+)\.(\d+)\.bin$", r["bmd"])
    if k in dump and m and bounds.get(k[0]): rows.append((r, dump[k], int(m.group(1))))
print("joined props with bounds:", len(rows))


def cell(x0, x1, z0, z1, w=W, h=H):
    for L in range(6, 0, -1):
        n = 1 << L; cw, ch = w / n, h / n
        c0, c1 = math.floor(x0 / cw), math.floor(x1 / cw)
        r0, r1 = math.floor((h - z1) / ch), math.floor((h - z0) / ch)
        if c0 == c1 and r0 == r1 and 0 <= c0 < n and 0 <= r0 < n: return FIRST[L] + r0 * n + c0
    return 0


def rot(rx, ry, rz):
    a, b, c = map(math.radians, (rx, ry, rz))
    Rx = np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])
    Ry = np.array([[math.cos(b), 0, math.sin(b)], [0, 1, 0], [-math.sin(b), 0, math.cos(b)]])
    Rz = np.array([[math.cos(c), -math.sin(c), 0], [math.sin(c), math.cos(c), 0], [0, 0, 1]])
    return Ry @ Rx @ Rz


rules = collections.Counter(); n = 0
for r, d, bob in rows:
    x, z = float(r["x"]), float(r["z"]); b = bounds[r["path"].lower()]
    s = np.array([float(d["sx"]), float(d["sy"]), float(d["sz"])])
    mn, mx = np.array(b["min"]), np.array(b["max"])
    corners = np.array([[i, j, k] for i in (mn[0], mx[0]) for j in (mn[1], mx[1]) for k in (mn[2], mx[2])]) * s
    n += 1
    cand = {"R0 point": cell(x, x, z, z)}
    rr = b["r"] * max(abs(s[0]), abs(s[2])); cand["R1 circle"] = cell(x - rr, x + rr, z - rr, z + rr)
    for name, M in (("R2 rot YXZ", rot(float(d["rx"]), float(d["ry"]), float(d["rz"]))), ("R2b rot -yaw", rot(0, -float(d["ry"]), 0)),
                    ("R2c rot yaw", rot(0, float(d["ry"]), 0))):
        w_ = corners @ M.T
        cand[name] = cell(x + w_[:, 0].min(), x + w_[:, 0].max(), z + w_[:, 2].min(), z + w_[:, 2].max())
    r3 = b["r3"] * max(abs(s[0]), abs(s[1]), abs(s[2])); cand["R4 sphere3d pivot"] = cell(x - r3, x + r3, z - r3, z + r3)
    cc = np.array(b["c"]) * s; r3c = b["r3c"] * max(abs(s[0]), abs(s[1]), abs(s[2]))
    cand["R5 sphere3d centre"] = cell(x + cc[0] - r3c, x + cc[0] + r3c, z + cc[2] - r3c, z + cc[2] + r3c)
    # BOB (bob_terrain FUN_18005e050): .wsmodel paths -> default box [-1,1]^3; rigid models -> model aabb; 8 corners x world matrix
    bmn, bmx = (np.array([-1.0, -1, -1]), np.array([1.0, 1, 1])) if r["path"].lower().endswith(".wsmodel") else (mn, mx)
    bc = np.array([[i, j, k] for i in (bmn[0], bmx[0]) for j in (bmn[1], bmx[1]) for k in (bmn[2], bmx[2])]) * s
    for name, M in (("BOB ws/rot YXZ", rot(float(d["rx"]), float(d["ry"]), float(d["rz"]))), ("BOB ws/yaw", rot(0, float(d["ry"]), 0)), ("BOB ws/-yaw", rot(0, -float(d["ry"]), 0))):
        w_ = bc @ M.T
        cand[name] = cell(x + w_[:, 0].min(), x + w_[:, 0].max(), z + w_[:, 2].min(), z + w_[:, 2].max())
    cand["R3 box no rot"] = cell(x + corners[:, 0].min(), x + corners[:, 0].max(), z + corners[:, 2].min(), z + corners[:, 2].max())
    for k, v in cand.items(): rules[k] += (v == bob)
for k, v in rules.most_common(): print(f"  {k:16s} {v / n:.4%}")

# ---- mismatch analysis for the best rule (R3: scaled box, no rotation)
lvl = lambda c: max(l for l in range(7) if FIRST[l] <= c)
deeper = collections.Counter(); bym = collections.Counter(); total = collections.Counter(); ex = []
for r, d, bob in rows:
    x, z = float(r["x"]), float(r["z"]); b = bounds[r["path"].lower()]
    s = np.array([float(d["sx"]), float(d["sy"]), float(d["sz"])]); mn, mx = np.array(b["min"]) * s, np.array(b["max"]) * s
    lo, hi = np.minimum(mn, mx), np.maximum(mn, mx)
    c = cell(x + lo[0], x + hi[0], z + lo[2], z + hi[2])
    k = r["path"].split("/")[-1]; total[k] += 1
    if c != bob:
        deeper["rule deeper" if lvl(c) > lvl(bob) else ("bob deeper" if lvl(c) < lvl(bob) else "same level, other cell")] += 1
        bym[k] += 1
        if len(ex) < 6: ex.append((k, x, z, round(lo[0], 3), round(hi[0], 3), round(lo[2], 3), round(hi[2], 3), lvl(c), lvl(bob)))
print("R3 mismatches:", dict(deeper))
print("by model:", [(m, n, total[m]) for m, n in bym.most_common(12)])
for e in ex: print("  ", e)

# ---- BOB-rule residuals by suffix
res = collections.Counter(); tot = collections.Counter(); exm = collections.Counter()
for r, d, bob in rows:
    x, z = float(r["x"]), float(r["z"]); b = bounds[r["path"].lower()]
    s = np.array([float(d["sx"]), float(d["sy"]), float(d["sz"])])
    ws = r["path"].lower().endswith(".wsmodel")
    bmn, bmx = (np.array([-1.0, -1, -1]), np.array([1.0, 1, 1])) if ws else (np.array(b["min"]), np.array(b["max"]))
    bc = np.array([[i, j, k] for i in (bmn[0], bmx[0]) for j in (bmn[1], bmx[1]) for k in (bmn[2], bmx[2])]) * s
    w_ = bc @ rot(float(d["rx"]), float(d["ry"]), float(d["rz"])).T
    c = cell(x + w_[:, 0].min(), x + w_[:, 0].max(), z + w_[:, 2].min(), z + w_[:, 2].max())
    k = "wsmodel" if ws else "rigid"; tot[k] += 1
    if c != bob: res[k] += 1; exm[r["path"].split("/")[-1]] += 1
for src in ("h0", "hall", "vall"):
    miss = 0; n2 = 0
    for r, d, bob in rows:
        if r["path"].lower().endswith(".wsmodel"): continue
        b = bounds[r["path"].lower()]
        if not b.get(src): continue
        x, z = float(r["x"]), float(r["z"]); s = np.array([float(d["sx"]), float(d["sy"]), float(d["sz"])])
        bmn, bmx = np.array(b[src][0]), np.array(b[src][1])
        bc = np.array([[i, j, k] for i in (bmn[0], bmx[0]) for j in (bmn[1], bmx[1]) for k in (bmn[2], bmx[2])]) * s
        w_ = bc @ rot(float(d["rx"]), float(d["ry"]), float(d["rz"])).T
        n2 += 1; miss += cell(x + w_[:, 0].min(), x + w_[:, 0].max(), z + w_[:, 2].min(), z + w_[:, 2].max()) != bob
    print(f"rigid aabb source {src}: misses {miss}/{n2}")
print("BOB-rule residuals:", {k: f"{res[k]}/{tot[k]}" for k in tot}); print("  top models:", exm.most_common(10))
