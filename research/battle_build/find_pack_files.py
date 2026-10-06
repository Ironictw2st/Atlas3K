"""List (and optionally extract) game-pack entries whose path contains all given substrings (case-insensitive).
usage: find_pack_files.py <substr> [substr ...] [--exclude ext,ext] [--extract <dir>]"""
import glob, os, sys
sys.path.insert(0, r"Z:/Claude/UpdateMod/tools")
from packidx import index

GAME = r"C:/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/data"
args = sys.argv[1:]
out = None
excl = []
if "--extract" in args:
    i = args.index("--extract"); out = args[i + 1]; del args[i:i + 2]
if "--exclude" in args:
    i = args.index("--exclude"); excl = args[i + 1].split(","); del args[i:i + 2]
keys = [a.lower().replace("/", "\\") for a in args]
for p in sorted(glob.glob(os.path.join(GAME, "*.pack"))):
    try:
        entries = index(p)
    except Exception:
        continue
    for n, sz, off, comp in entries:
        nl = n.lower()
        if all(k in nl for k in keys) and not any(nl.endswith(e) for e in excl):
            print(os.path.basename(p), n, sz, comp)
            if out and comp == 0:
                dst = os.path.join(out, os.path.basename(p), n.replace("\\", "/"))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with open(p, "rb") as f:
                    f.seek(off)
                    open(dst, "wb").write(f.read(sz))
