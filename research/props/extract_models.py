"""Extract the models a props-cells CSV references (wsmodel + their geometry rigid_model_v2) from the game packs into
output/props_parity/models, using output/props_parity/pack_index.tsv (pack \t path). Later packs win like the game
(fast.pack after models2 after models). usage: extract_models.py"""
import os, re, subprocess
from pathlib import Path
OUT = Path(r"Z:/Claude/TerryClone/output/props_parity")
DD = r"C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\data"
order = {"models.pack": 0, "models2.pack": 1, "data.pack": 2, "fast.pack": 3}
where = {}
for line in open(OUT / "pack_index.tsv", encoding="utf-8"):
    p, path = line.rstrip("\n").split("\t")
    k = path.lower()
    if k not in where or order[p] > order[where[k][0]]: where[k] = (p, path)
want = [m.strip() for m in open(OUT / "models.txt", encoding="utf-8") if m.strip() and "terrain/campaigns" not in m]
def extract(paths):
    by = {}
    for k in paths:
        if k in where: by.setdefault(where[k][0], []).append(where[k][1])
    for pack, ps in by.items():
        for i in range(0, len(ps), 60):
            args = []
            for x in ps[i:i + 60]: args += ["-f", f"{x};{OUT / 'models'}"]
            subprocess.run([r"Z:/RPFM/rpfm_cli.exe", "--game", "three_kingdoms", "pack", "extract", "-p", os.path.join(DD, pack)] + args,
                           capture_output=True)
missing = [k for k in want if k not in where]
extract(want)
# wsmodel -> geometry
geo = set()
for k in want:
    if k.endswith(".wsmodel"):
        f = OUT / "models" / k
        if f.exists():
            m = re.search(r"<geometry>([^<]+)</geometry>", f.read_text(encoding="utf-8", errors="replace"))
            if m: geo.add(m.group(1).strip().lower())
extract(sorted(geo))
have = sum((OUT / "models" / k).exists() for k in want)
print(f"wanted {len(want)}, extracted {have}, not in packs {len(missing)} {missing[:5]}; geometry files {len(geo)}, "
      f"extracted {sum((OUT / 'models' / g).exists() for g in geo)}")
