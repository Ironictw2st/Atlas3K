"""Which tile instances (vanilla tile_list.bin) cover each tree, and does the lf-only height miss correlate with tiles
that carry a non-zero hf map? Tile-space point = (x / T, (z / 1.15476) / T), T = 595.1/1784, y from the south; a tile
covers [X, X + w] x [Y, Y + h] (rotation 0x20/0x80 swaps w/h), inclusive as in get_height_worker (0x371030).
Tile size in tile-map points = (hf map width - 1) / 4."""
import collections, struct, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from lf_exact import load_trees, load_lf, lf_height_bob, F
HERE = Path(__file__).parent
TL = Path(r"Z:/Claude/TerryClone/Vanilla/Map/terrain/campaigns/3k_dlc07_main_map/tile_list.bin")
BS = chr(92)


def read_tile_list(p):
    b = open(p, "rb").read(); o = 12
    def strs():
        nonlocal o
        n = struct.unpack_from("<I", b, o)[0]; o += 4; out = []
        for _ in range(n):
            l = struct.unpack_from("<H", b, o)[0]; out.append(b[o + 2:o + 2 + l].decode("latin1")); o += 2 + l
        return out
    paths = strs(); strs(); o += 24 + 44 + 1
    cnt = struct.unpack_from("<I", b, o)[0]; o += 4
    recs = []
    for i in range(cnt):
        v, pi, c, x, y, ori, fl = struct.unpack_from("<HIBHHBB", b, o + i * 21)
        lo, hi = struct.unpack_from("<ff", b, o + i * 21 + 13)
        parts = paths[pi].rstrip(BS).split(BS)
        recs.append((parts[-2] + "/" + parts[-1], x, y, ori & 0xF0, lo, hi))
    return recs


def bob_tile_sizes():
    """file name -> (w, h) from the Frida dump of BOB's tile database (research/bob_re/frida_out/frida_vanilla6.jsonl)."""
    import json
    for l in open(HERE.parent / "bob_re/frida_out/frida_vanilla6.jsonl", encoding="utf-8"):
        d = json.loads(l)
        if d["kind"] == "db_after" and len(d["tiles"]) == 544:
            return {t.split("|")[0].lower(): (int(t.split("|")[2]), int(t.split("|")[3])) for t in d["tiles"]}


def tile_info():
    sizes = bob_tile_sizes()
    info = {}
    for p in (HERE / "tile_hf/terrain/tiles/campaign").glob("*/*/hf_height_map.compressed_map"):
        b = open(p, "rb").read(50); w, h = struct.unpack_from("<II", b, 10); hd = struct.unpack_from("<6f", b, 26)
        k = p.parts[-3] + "/" + p.parts[-2]; tw, th = sizes.get(f"{p.parts[-3]}_{p.parts[-2]}.bin".lower(), (None, None))
        info[k] = dict(w=tw, h=th, nz=bool(hd[1] or hd[4]), kind="map")
    for p in (HERE / "tile_hf/terrain/tiles/campaign").glob("*/*/hf_height_map.data"):
        k = p.parts[-3] + "/" + p.parts[-2]
        tw, th = sizes.get(f"{p.parts[-3]}_{p.parts[-2]}.bin".lower(), (None, None))
        info.setdefault(k, dict(w=tw, h=th, nz=True, kind="data"))
    return info


if __name__ == "__main__":
    xs, ys, zs = load_trees(); raster = load_lf()
    lfh = lf_height_bob(xs, zs, raster); exact = lfh.view(np.int32) == ys.view(np.int32)
    recs = read_tile_list(TL); info = tile_info()
    T = F(F(595.1) / F(1784))
    tx = (xs / T).astype(F); ty = ((zs / F(1.15476)).astype(F) / T).astype(F)
    W, H = 1784, 1405
    # cover grid: per tile-map point, list of record indices (painted inclusive of the far edge)
    cover = collections.defaultdict(list); unknown = collections.Counter()
    for i, (k, x, y, rot, lo, hi) in enumerate(recs):
        ti = info.get(k)
        if ti is None or ti["w"] is None: unknown[k.split("/")[0]] += 1; continue
        w, h = (ti["h"], ti["w"]) if rot in (0x20, 0x80) else (ti["w"], ti["h"])
        for yy in range(y, min(y + h + 1, H + 1)):
            for xx in range(x, min(x + w + 1, W + 1)):
                cover[(xx, yy)].append(i)
    print("records", len(recs), "without size info (old .data path or missing):", dict(unknown.most_common(8)))
    cat = []
    for i in range(len(xs)):
        cell = (int(tx[i]), int(ty[i]))
        sets = {recs[j][0].split("/")[0] for j in cover.get(cell, [])}
        hfnz = any(info.get(recs[j][0], {}).get("nz") for j in cover.get(cell, []))
        cat.append(("hf" if hfnz else "flat") + ":" + ("+".join(sorted(sets)) if sets else "none"))
    cat = np.array(cat)
    by = collections.defaultdict(lambda: [0, 0])
    for c, e in zip(cat, exact): by[c][0] += 1; by[c][1] += int(e)
    flat = np.array([c.startswith("flat") for c in cat])
    print(f"trees on zero-hf tiles: {flat.mean():.2%}, exact there {exact[flat].mean():.2%}; on hf tiles exact {exact[~flat].mean():.2%}")
    for c, (n, e) in sorted(by.items(), key=lambda kv: -kv[1][0])[:25]:
        print(f"  {c:60s} n {n:7d}  exact {e / n:.2%}")
