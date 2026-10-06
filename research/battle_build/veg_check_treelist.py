"""Builds the tree list from a frida_procedural.js dump's instances (+ the project's hand-placed trees) and compares it
with BOB's. usage: check_treelist_dump.py <label> <corpus project dir> <climate> [k]"""
import math, re, sys
from veg_dump import dump
import veg_treelist as T

label, proj, climate = sys.argv[1:4]
k = int(sys.argv[4]) if len(sys.argv) > 4 else 0
d = dump(label)[k]
P = d["object_params"]
items = []
for p in sorted(d["instances"]):
    for inst in d["instances"][p]:
        prm = P[inst["obj"]]
        if prm["raw"][0xB5] == 1:
            key = ("BattleTerrain/vegetation/" + prm["name"] + ".rigid_model_v2").replace("\\", "/")
            items.append((key, inst["x"], 0.0, inst["z"], inst["scale"], T.rot_byte(inst["rot"]), False))
# hand-placed ECVegetation entities of the layer
import glob
for layer in glob.glob(proj + "/src/tile/*.layer"):
    t = open(layer, encoding="utf-8").read()
    for m in re.finditer(r'<ECVegetation key="([^"]+)"/>\s*<ECTransform position="([^"]+)" rotation="([^"]+)" scale="([^"]+)"', t):
        x, y, z = map(float, m.group(2).split())
        ry = float(m.group(3).split()[1])
        sc = float(m.group(4).split()[0])
        items.append(("BattleTerrain/vegetation/" + m.group(1) + ".rigid_model_v2", x, y, z, sc,
                      T.rot_byte(ry * math.pi / 180), False))
lst = T.build(items)
ref = proj + f"/bob_run1/tile/{climate}.tree_list"
b = T.to_bin(lst)
rb = open(ref + ".bin", "rb").read()
print("bin", b == rb, len(b), len(rb))
if b != rb:
    i = next((i for i in range(min(len(b), len(rb))) if b[i] != rb[i]), min(len(b), len(rb)))
    print("first diff", i)
x = T.to_xml(lst)
rx = open(ref + ".xml", encoding="utf-8", newline="").read()
print("xml", x == rx, len(x), len(rx))
if x != rx:
    i = next((i for i in range(min(len(x), len(rx))) if x[i] != rx[i]), min(len(x), len(rx)))
    print(repr(x[max(0, i - 120):i + 60]))
    print(repr(rx[max(0, i - 120):i + 60]))
