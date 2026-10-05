#!/usr/bin/env python3
"""Sort the generated dressing into per-region layers (user 2026-10-03: "move the new props into their own layers like
how they are sorted for the new regions").

BUILD RULE (ak_main.py, last): north_dress (ids 0e...) and village_dress (ids 0d...) entities are taken out of the
non-playable host layer and grouped by the region under each entity (map.hex). A region that already has a layer in the
project (a .terry Scene entity named after the region key, as CA / 190E sort them) gets them appended; a region without
one (the ironic_* regions) gets a new layer file + Scene entity named after the region key (stable id from the name).
Sea / unassigned / 3k_main_reg_non_playable stay in the host layer."""
import hashlib, re, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
GENERATED = ("0e", "0d")
EMPTY = '<?xml version="1.0" encoding="UTF-8"?>\n<layer version="35">\n  <entities>\n  </entities>\n  <associations>\n    <Logical/>\n    <Transform/>\n  </associations>\n</layer>\n'
SCENE_ENT = ('      <entity id="{id}" name="{name}">\n        <ECLayerFile/>\n        <ECLayer/>\n'
             '        <ECLayerExport export="true" export_as_separate_file_if_not_meta_tagged="false" buildings_have_linked_destruction="false"/>\n'
             '      </entity>\n')


def sort(out_dir, map_name="3k_dlc07_main_map"):
    import town_fix as T, village_dress
    from hexgrid import nearest_hex
    out_dir = Path(out_dir)
    _, _, w, h, _, f, names = T.load(str(HERE / "hex" / "map.hex"))
    tp = out_dir / f"{map_name}.terry"; terry = open(tp, encoding="utf-8").read()
    layer_of = {m.group(2): m.group(1) for m in re.finditer(r'<entity id="([0-9a-f]+)" name="([^"]*)">\s*<ECLayerFile/>', terry)}
    host = village_dress._host(out_dir, map_name)
    t = open(host, encoding="utf-8").read()
    ents = list(re.finditer(r'\n?[ \t]*<entity id="([0-9a-f]+)">.*?</entity>', t, re.S))
    gen = [m for m in ents if m.group(1)[:2] in GENERATED]
    pos = np.array([[float(v) for v in re.search(r'position="([^ ]+) [^ ]+ ([^ "]+)"', m.group(0)).groups()] for m in gen])
    c, r = nearest_hex(pos[:, 0], pos[:, 1], w, h)
    reg = f["region"][r, c]; land = f["terr"][r, c] == 0
    groups, keep = {}, []
    for m, k, l in zip(gen, reg, land):
        name = names[k] if 0 <= k < len(names) else ""
        if not l or not name or name == "3k_main_reg_non_playable": keep.append(m); continue
        groups.setdefault(name, []).append(m.group(0).lstrip("\n"))
    # host: drop the moved entities (keep everything else exactly)
    moved = {m.start() for m in gen} - {m.start() for m in keep}
    pieces, last = [], 0
    for m in ents:
        if m.start() in moved: pieces.append(t[last:m.start()]); last = m.end()
    pieces.append(t[last:]); open(host, "w", encoding="utf-8", newline="").write("".join(pieces))
    new_layers = appended = 0
    scene_add = ""
    for name, es in sorted(groups.items()):
        lid = layer_of.get(name)
        if lid is None:
            lid = "1" + hashlib.md5(name.encode()).hexdigest()[:14]
            while lid in terry: lid = "1" + hashlib.md5((lid + name).encode()).hexdigest()[:14]
            (out_dir / f"{map_name}.{lid}.layer").write_text(EMPTY, encoding="utf-8")
            scene_add += SCENE_ENT.format(id=lid, name=name); layer_of[name] = lid; new_layers += 1
        lp = out_dir / f"{map_name}.{lid}.layer"
        lt = open(lp, encoding="utf-8").read()
        if "<entities/>" in lt: lt = lt.replace("<entities/>", "<entities>\n  </entities>", 1)
        i = lt.rindex("</entities>")
        lt = lt[:i] + "  " + "\n    ".join(e.strip() for e in es) + "\n  " + lt[i:]
        open(lp, "w", encoding="utf-8", newline="").write(lt); appended += len(es)
    if scene_add:
        i = terry.index("</data>", terry.index('<pc type="QTU::Scene">'))
        i = terry.rindex("\n", 0, i) + 1                                   # start of the "    </data>" line
        terry = terry[:i] + scene_add + terry[i:]
        open(tp, "w", encoding="utf-8", newline="").write(terry)
    print(f"layer_sort: {appended} generated entities -> {len(groups)} region layers ({new_layers} new); {len(keep)} stay in {host.name}")


if __name__ == "__main__":
    sort(HERE / "ak" / "3k_dlc07_main_map")
