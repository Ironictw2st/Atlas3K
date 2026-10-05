"""Map BOB prop records (props-cells csv, record order) to layer entities; print per-body entity sequences.
usage: order_study.py <layers dir> <bob_cells.csv> [body substring]"""
import csv, glob, os, re, sys, collections, pickle
import numpy as np
f32 = lambda v: int(np.float32(float(v)).view(np.int32))
ent_re = re.compile(r'<entity id="([0-9a-f]+)"')
mesh_re = re.compile(r'<ECMesh model_path="([^"]*)"')
pos_re = re.compile(r'<ECTransform position="([^ ]+) ([^ ]+) ([^ "]+)"')

def entities(d):
    cache = os.path.join(os.path.dirname(__file__), "_ents.pkl")
    if os.path.exists(cache): return pickle.load(open(cache, "rb"))
    out = {}
    layers = sorted(glob.glob(os.path.join(d, "*.layer")))
    for li, p in enumerate(layers):
        eid = None; model = None; k = 0; depth = 0
        for ln, line in enumerate(open(p, encoding="utf-8")):
            m = ent_re.search(line)
            if m: eid = m.group(1); model = None; k += 1; continue
            m = mesh_re.search(line)
            if m: model = m.group(1).lower(); continue
            m = pos_re.search(line)
            if m and eid and model:
                out.setdefault((model, f32(m.group(1)), f32(m.group(3))), []).append((os.path.basename(p), ln, eid, k))
    pickle.dump(out, open(cache, "wb"))
    return out

if __name__ == "__main__":
    E = entities(sys.argv[1])
    sub = sys.argv[3] if len(sys.argv) > 3 else None
    bodies = collections.defaultdict(list)
    for r in csv.DictReader(open(sys.argv[2], encoding="utf-8")):
        bodies[r["bmd"]].append(E.get((r["path"].lower(), f32(r["x"]), f32(r["z"])), [None]))
    for b, seq in bodies.items():
        if sub and sub not in b: continue
        print(b.split("bmd_objects.")[-1])
        for s in seq: print("   ", s)
