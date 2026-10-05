"""Renumber BOB's river models to match a reference map (e.g. vanilla), fixing global_props.bin to suit.

BOB numbers the river_N models in its own internal order, which ignores the entity names. This matches every
built river to the reference river with the same shape (by centreline), then:
  - renames models/river_N.wsmodel(.rigid_model_v2) and updates the geometry path inside each .wsmodel
  - rewrites the u16-length-prefixed "…/models/river_N.wsmodel" strings in global_props.bin and rebuilds the
    block offset table that follows the header (u32 count, then per block: name\0 + u32 offset into the body)
The height patches already use the entity numbering, so they are left alone.

usage: renumber_rivers.py <terrain output dir> <reference terrain dir> [--dry-run]
"""
import os
import re
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import rivers_from_meshes as RM  # noqa: E402


def river_ids(models_dir):
    return sorted(int(m.group(1)) for f in os.listdir(models_dir)
                  if (m := re.fullmatch(r"river_(\d+)\.wsmodel\.rigid_model_v2", f)))


def match(built_dir, ref_dir):
    ids = river_ids(built_dir)
    ref_ids = river_ids(ref_dir)
    sec = lambda d, i: RM.cross_sections(RM.read_river_mesh(f"{d}/river_{i}.wsmodel.rigid_model_v2"))[:, 1:4]
    built = {i: sec(built_dir, i) for i in ids}
    ref = {j: sec(ref_dir, j) for j in ref_ids}
    mapping, quality = {}, {}
    for i in ids:
        dists = {j: np.median(RM.xz_distance(built[i], ref[j])) for j in ref_ids}
        j = min(dists, key=dists.get)
        mapping[i], quality[i] = j, dists[j]
    if sorted(mapping.values()) != sorted(ids):
        raise SystemExit(f"matching is not a one-to-one renumbering: {mapping}")
    return mapping, quality


def patch_global_props(data, mapping):
    n = struct.unpack_from("<I", data, 0)[0]
    pos, names, offs = 4, [], []
    for _ in range(n):
        end = data.index(b"\x00", pos)
        names.append(data[pos:end])
        offs.append(struct.unpack_from("<I", data, end + 1)[0])
        pos = end + 5
    base = pos
    ends = offs[1:] + [len(data) - base]
    pat = re.compile(rb"(..)(terrain/campaigns/[^\x00]*?/models/river_)(\d+)(\.wsmodel)", re.S)
    blobs, changed = [], 0
    for o, e in zip(offs, ends):
        blob = data[base + o:base + e]

        def repl(m):
            nonlocal changed
            path_len = struct.unpack("<H", m.group(1))[0]
            old = m.group(2) + m.group(3) + m.group(4)
            if path_len != len(old):
                return m.group(0)  # not a length-prefixed path; leave untouched
            new = m.group(2) + str(mapping[int(m.group(3))]).encode() + m.group(4)
            changed += 1
            return struct.pack("<H", len(new)) + new

        blobs.append(pat.sub(repl, blob))
    out = bytearray(struct.pack("<I", n))
    new_off = 0
    for name, blob in zip(names, blobs):
        out += name + b"\x00" + struct.pack("<I", new_off)
        new_off += len(blob)
    for blob in blobs:
        out += blob
    return bytes(out), changed


def main(terrain_dir, ref_dir, dry_run=False):
    models = os.path.join(terrain_dir, "models")
    mapping, quality = match(models, os.path.join(ref_dir, "models"))
    for i in sorted(mapping):
        print(f"river_{i:<2d} -> river_{mapping[i]:<2d}  (centreline median {quality[i]:.3f})")
    gp_path = os.path.join(terrain_dir, "global_props.bin")
    new_gp, changed = patch_global_props(open(gp_path, "rb").read(), mapping)
    print(f"global_props.bin: {changed} river paths rewritten, {len(new_gp):,} bytes")
    if dry_run:
        return
    # rename through temporary names so swaps cannot collide
    for i in mapping:
        for ext in (".wsmodel", ".wsmodel.rigid_model_v2"):
            os.replace(f"{models}/river_{i}{ext}", f"{models}/river_{i}{ext}.tmp")
    for i, j in mapping.items():
        os.replace(f"{models}/river_{i}.wsmodel.rigid_model_v2.tmp", f"{models}/river_{j}.wsmodel.rigid_model_v2")
        ws = open(f"{models}/river_{i}.wsmodel.tmp", "rb").read()
        ws = re.sub(rb"(models/river_)\d+(\.wsmodel\.rigid_model_v2)", rb"\g<1>" + str(j).encode() + rb"\2", ws)
        open(f"{models}/river_{j}.wsmodel", "wb").write(ws)
        os.remove(f"{models}/river_{i}.wsmodel.tmp")
    open(gp_path, "wb").write(new_gp)
    print("done")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], "--dry-run" in sys.argv)
