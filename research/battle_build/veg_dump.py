"""Loads a research/bob_re/frida_veg_procedural.js dump (Z:/Claude/BattleMaps/research/bob_re/frida_veg/<label>.jsonl +
<label>_bin/). dump(label) -> {k: call dict} with numpy arrays: header bytes, groups (n,20) bytes, objects (n,12) bytes,
object params (name, raw 0x100 bytes), height (h,w) / blend (h,w,8) float32, exclusion bytes, instances [pass]."""
import json, os
import numpy as np

ROOT = r"Z:/Claude/BattleMaps/research/bob_re/frida_veg"
INST = np.dtype([("obj", "<i4"), ("x", "<f4"), ("z", "<f4"), ("scale", "<f4"), ("rot", "<f4")])


def dump(label, root=ROOT):
    calls = {}
    bin_dir = os.path.join(root, f"{label}_bin")
    for line in open(os.path.join(root, f"{label}.jsonl"), encoding="utf-8"):
        p = json.loads(line)
        if "k" not in p:
            continue
        c = calls.setdefault(p["k"], {"object_params": [], "instances": {}, "group_compile": []})
        raw = open(os.path.join(bin_dir, p["file"]), "rb").read() if "file" in p else b""
        kind = p["kind"]
        if kind == "object_param":
            c["object_params"].append({"name": p["name"], "raw": raw, "ptr": p["ptr"], "group": p.get("group")})
        elif kind == "group_compile":
            c["group_compile"].append({**p, "out": raw})
        elif kind == "groups":
            c["groups"] = np.frombuffer(raw, np.uint8).reshape(-1, 20)
        elif kind == "objects":
            c["objects"] = np.frombuffer(raw, np.uint8).reshape(-1, 12)
        elif kind in ("height", "blend"):
            if p.get("null"):
                c[kind] = None
            else:
                a = np.frombuffer(raw, np.float32)
                c[kind] = a.reshape(p["h"], p["w"], p["c"]) if p["c"] > 1 else a.reshape(p["h"], p["w"])
                c[kind + "_hdr"] = p["hdr"]
        elif kind == "instances":
            c["instances"][p["pass"]] = np.frombuffer(raw, INST)
        else:
            c[kind] = raw
    return calls
