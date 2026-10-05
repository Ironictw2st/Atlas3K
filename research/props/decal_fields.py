"""Tabulate BOB decal record bytes 72..104 against the layer ECDecal attributes. usage: decal_fields.py <layers> <bob_props_raw.csv>"""
import csv, glob, os, re, sys, collections
import numpy as np
f32 = lambda v: int(np.float32(float(v)).view(np.int32))
dec_re = re.compile(r'<ECDecal model_path="([^"]*)"([^>]*)/>'); pos_re = re.compile(r'<ECTransform position="([^ ]+) [^ ]+ ([^ "]+)"')
E = {}
for p in glob.glob(os.path.join(sys.argv[1], "*.layer")):
    cur = None
    for line in open(p, encoding="utf-8"):
        if "<entity " in line: cur = None
        m = dec_re.search(line)
        if m: cur = (m.group(1).lower(), m.group(2).strip()); continue
        m = pos_re.search(line)
        if m and cur: E[(cur[0], f32(m.group(1)), f32(m.group(2)))] = cur[1]
c = collections.Counter()
for r in csv.DictReader(open(sys.argv[2], encoding="utf-8")):
    if r["path"].startswith("scene:"): continue
    k = (r["path"].lower(), f32(r["x"]), f32(r["z"]))
    if k in E:
        a = dict(re.findall(r'(\w+)="([^"]*)"', E[k])); fl = bytes.fromhex(r["flags"])
        c[(a["parallax_scale"], a["apply_to_terrain"], a["apply_to_objects"], a["render_above_snow"], a["normal_mode"], fl[8:12].hex(), fl[28:33].hex())] += 1
for k, v in c.most_common(): print(v, k)
