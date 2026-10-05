"""Field-level diff of two tile_list.bin files: header tables, then each record field (version, path, climate, x, y,
orientation, flag) and the per-record low/high heights.
usage: tilelist_fields.py <a.bin> <b.bin>"""
import struct, sys, collections


def parse(p):
    b = open(p, "rb").read(); o = 0
    hdr = b[:12]; o = 12
    def strs():
        nonlocal o
        n = struct.unpack_from("<I", b, o)[0]; o += 4; out = []
        for _ in range(n):
            l = struct.unpack_from("<H", b, o)[0]; out.append(b[o + 2:o + 2 + l].decode("latin1")); o += 2 + l
        return out
    paths = strs(); clim = strs(); mid = b[o:o + 24 + 44 + 1]; o += 24 + 44 + 1
    cnt = struct.unpack_from("<I", b, o)[0]; o += 4
    recs = [struct.unpack_from("<HIBHHBB", b, o + i * 21) for i in range(cnt)]
    rest = b[o + cnt * 21:]
    return dict(hdr=hdr, paths=paths, clim=clim, mid=mid, cnt=cnt, recs=recs, rest=rest, raw=b, rec0=o)


A, B = parse(sys.argv[1]), parse(sys.argv[2])
print("header equal", A["hdr"] == B["hdr"], "| paths equal", A["paths"] == B["paths"], len(A["paths"]), len(B["paths"]),
      "| climates equal", A["clim"] == B["clim"], "| mid (map_area etc.) equal", A["mid"] == B["mid"], "| counts", A["cnt"], B["cnt"])
if A["paths"] != B["paths"]:
    i = next((k for k, (x, y) in enumerate(zip(A["paths"], B["paths"])) if x != y), None)
    print("  first path difference at", i, A["paths"][i:i + 2] if i is not None else "", B["paths"][i:i + 2] if i is not None else "")
    print("  path sets equal:", set(A["paths"]) == set(B["paths"]))
names = ("version", "path", "climate", "x", "y", "orientation", "flag")
diff = collections.Counter()
for ra, rb in zip(A["recs"], B["recs"]):
    for k, (u, v) in enumerate(zip(ra, rb)):
        if names[k] == "path":
            if A["paths"][u] != B["paths"][v]: diff["path"] += 1
        elif u != v: diff[names[k]] += 1
print("record field differences:", dict(diff))
print("tail section equal:", A["rest"] == B["rest"], len(A["rest"]), len(B["rest"]))
if A["rest"] != B["rest"]:
    i = next(k for k, (x, y) in enumerate(zip(A["rest"], B["rest"])) if x != y)
    print("  first tail difference at offset", i, "of", len(A["rest"]))
