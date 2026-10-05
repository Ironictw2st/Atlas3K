"""Check the warped AK project against the warped map.hex: each <region>_capital props layer's median
(non-vegetation) prop position should fall in that region's hexes (or within 2 hexes of them)."""
import re, os, sys, statistics as st, numpy as np
from pathlib import Path
sys.path.insert(0, "../guandu"); sys.path.insert(0, "..")
import crop_scale_map_hex as C, hexmap
from rebuild_hex import unpack
from hexgrid import nearest_hex
AK = "ak/3k_dlc07_main_map"; NAME = "3k_dlc07_main_map"
src = Path("hex/map.hex").read_bytes(); P, w, h = C.locate_dims(src)
f = unpack(np.frombuffer(src, np.uint8, 16 * w * h, P + 8).reshape(h, w, 16))
L = hexmap.load("hex/map.hex")["lists"]; names = L["land_regions"] + L["sea_regions"]
t = open(f"{AK}/{NAME}.terry", encoding="utf-8").read()
ok = near = bad = 0; bads = []
for lid, name in re.findall(r'<entity id="([0-9a-f]+)" name="([a-z0-9_]+)_capital">', t):
    fn = f"{AK}/{NAME}.{lid}.layer"
    if not os.path.exists(fn): continue
    pts = []
    for e in re.findall(r"<entity id.*?</entity>", open(fn, encoding="utf-8").read(), re.S):
        m = re.search(r'model_path="([^"]*)"', e); p = re.search(r'position="([^"]+)"', e)
        if m and p and "vegetation" not in m.group(1).lower():
            x, _, z = map(float, p.group(1).split()); pts.append((x, z))
    if len(pts) < 10: continue
    x, z = st.median(a for a, _ in pts), st.median(b for _, b in pts)
    c, r = nearest_hex(np.array([x]), np.array([z]), w, h); c, r = int(c[0]), int(r[0])
    cand = [n for n in names if n.endswith(name.split("_", 2)[-1] + "_capital") or n == name + "_capital"]
    reg = names[f["region"][r, c]] if f["region"][r, c] >= 0 else None
    want = [names.index(n) for n in cand]
    if reg in cand: ok += 1; continue
    win = f["region"][max(0, r - 2):r + 3, max(0, c - 2):c + 3]
    if np.isin(win, want).any(): near += 1
    else: bad += 1; bads.append((name, (c, r), reg))
print(f"capital layers: {ok} in region, {near} within 2 hexes, {bad} off"); print(bads[:20])
