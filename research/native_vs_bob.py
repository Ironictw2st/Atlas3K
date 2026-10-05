"""Compare a native campaign build with a BOB build of the same map, output by output.

usage: native_vs_bob.py <native target root> <bob working_data root> <map> <tile_map.png used by both>
Both roots are laid out like working_data: terrain/campaigns/<map>/..., campaign_maps/<map>/...
Prints a summary table; per-output detail goes to stdout as it runs."""
import collections
import hashlib
import os
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CLI = os.path.join(HERE, "..", "src", "Atlas3K.Cli", "bin", "Release", "net9.0", "Atlas3K.Cli.exe")
BS = chr(92)


def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def files(root):
    out = {}
    for dp, _, fs in os.walk(root):
        for f in fs:
            p = os.path.join(dp, f)
            out[os.path.relpath(p, root).replace(BS, "/").lower()] = p
    return out


def same_files(nat, bob, rel):
    a, b = os.path.join(nat, rel), os.path.join(bob, rel)
    if not (os.path.exists(a) and os.path.exists(b)):
        return f"missing ({'native' if not os.path.exists(a) else 'bob'})"
    if os.path.getsize(a) == os.path.getsize(b) and md5(a) == md5(b):
        return "byte-identical"
    return f"differs ({os.path.getsize(a):,} vs {os.path.getsize(b):,} B)"


def read_tile_list(p):
    b = open(p, "rb").read()
    o = 12
    lists = []
    for _ in range(2):
        n = struct.unpack_from("<I", b, o)[0]
        o += 4
        items = []
        for _ in range(n):
            ln = struct.unpack_from("<H", b, o)[0]
            items.append(b[o + 2:o + 2 + ln].decode("latin1"))
            o += 2 + ln
        lists.append(items)
    header = b[o:o + 69]
    o += 69
    cnt = struct.unpack_from("<I", b, o)[0]
    o += 4
    recs = []
    for i in range(cnt):
        _, pi, c, x, y, ori, fl, lo, hi = struct.unpack_from("<HIBHHBBff", b, o + i * 21)
        recs.append((lists[0][pi].lower().rstrip(BS), x, y, ori, lists[1][c] if c < len(lists[1]) else c, fl, lo, hi))
    return header, recs


def compare_tile_list(nat, bob, tile_map, summary):
    n = os.path.join(nat, "terrain/campaigns", MAP, "tile_list.bin")
    r = os.path.join(bob, "terrain/campaigns", MAP, "tile_list.bin")
    hn, a = read_tile_list(n)
    hr, b = read_tile_list(r)
    full = lambda t: t[:6]
    place = lambda t: t[:3]
    A, B = collections.Counter(map(full, a)), collections.Counter(map(full, b))
    P, Q = collections.Counter(map(place, a)), collections.Counter(map(place, b))
    exact = sum((A & B).values()) / max(len(b), 1)
    same_place = sum((P & Q).values()) / max(len(b), 1)
    print(f"tile_list: records native {len(a):,} / BOB {len(b):,}; header {'identical' if hn == hr else 'differs'}")
    print(f"  identical records (path, x, y, orientation incl. flow bits, climate, flag): {exact:.1%}")
    print(f"  same tile at the same place: {same_place:.1%}")
    out = subprocess.run([sys.executable, os.path.join(HERE, "tilelist_holes.py"), tile_map, r], capture_output=True, text=True).stdout
    out2 = subprocess.run([sys.executable, os.path.join(HERE, "tilelist_holes.py"), tile_map, n], capture_output=True, text=True).stdout
    holes_b = out.split(":")[1].split("uncovered")[0].strip()
    holes_n = out2.split(":")[1].split("uncovered")[0].strip()
    print(f"  uncovered tile-set points: native {holes_n}, BOB {holes_b}")
    summary.append(("tile_list", f"{len(a):,} / {len(b):,} records; {same_place:.1%} same tile+place, {exact:.1%} identical; holes {holes_n} / {holes_b}"))


def compare_dir_counts(nat, bob, rel, label, summary, pattern=None):
    fa = {k for k in os.listdir(os.path.join(nat, rel))} if os.path.isdir(os.path.join(nat, rel)) else set()
    fb = {k for k in os.listdir(os.path.join(bob, rel))} if os.path.isdir(os.path.join(bob, rel)) else set()
    if pattern:
        fa = {f for f in fa if pattern(f)}
        fb = {f for f in fb if pattern(f)}
    ident = sum(1 for f in fa & fb if same_files(os.path.join(nat, rel), os.path.join(bob, rel), f) == "byte-identical")
    print(f"{label}: native {len(fa)}, BOB {len(fb)}, common names {len(fa & fb)}, byte-identical {ident}")
    only_n, only_b = sorted(fa - fb), sorted(fb - fa)
    if only_n:
        print(f"  only native: {only_n[:8]}{' ...' if len(only_n) > 8 else ''}")
    if only_b:
        print(f"  only BOB: {only_b[:8]}{' ...' if len(only_b) > 8 else ''}")
    summary.append((label, f"{len(fa)} / {len(fb)} files, {ident} byte-identical"))
    return fa, fb


def props_stats(path):
    import csv
    import tempfile
    tmp = os.path.join(tempfile.gettempdir(), "nvb_" + hashlib.md5(path.encode()).hexdigest() + ".csv")
    subprocess.run([CLI, "--map", MAP, "props-dump", path, tmp], capture_output=True, text=True)
    with open(tmp, encoding="utf-8", errors="replace", newline="") as f:
        rows = list(csv.DictReader(f))
    for p in (tmp, os.path.splitext(tmp)[0] + ".nested.csv"):
        if os.path.exists(p):
            os.remove(p)
    return rows


def compare_props(nat, bob, summary):
    a = props_stats(os.path.join(nat, "terrain/campaigns", MAP, "global_props.bin"))
    b = props_stats(os.path.join(bob, "terrain/campaigns", MAP, "global_props.bin"))
    def counts(rows, cols, digits=None):
        def k(r):
            v = []
            for c in cols:
                x = r[c]
                if digits is not None and c in ("x", "y", "z"):
                    x = round(float(x), digits)
                v.append(x)
            return tuple(v)
        return collections.Counter(k(r) for r in rows)
    print(f"  objects: native {len(a):,}, BOB {len(b):,}")
    for kind in ("prop", "composite"):
        print(f"  {kind}: native {sum(r['kind'] == kind for r in a):,}, BOB {sum(r['kind'] == kind for r in b):,}")
    results = {}
    for label, cols, digits in (("model", ["path"], None), ("model+position", ["path", "x", "y", "z"], 2),
                                ("model+position+region", ["path", "x", "y", "z", "region"], 2)):
        ka, kb = counts(a, cols, digits), counts(b, cols, digits)
        results[label] = sum((ka & kb).values()) / max(len(b), 1)
        print(f"  same {label}: {results[label]:.1%} of BOB's objects")
    summary.append(("global_props", f"{len(a):,} / {len(b):,} objects; same model+position {results['model+position']:.1%}, "
                                    f"+region {results['model+position+region']:.1%}"))


def main():
    global MAP
    nat, bob, MAP, tile_map = sys.argv[1:5]
    summary = []
    t = f"terrain/campaigns/{MAP}"
    c = f"campaign_maps/{MAP}"
    print("== rasters (kit copies were built natively, not by BOB)")
    for f in ("lf_height_map.compressed_map", "lf_sea_height_map.compressed_map", "lf_height_map.dds", "lf_sea_height_map.dds", "climate_map.cm"):
        r = same_files(nat, bob, f"{t}/{f}")
        print(f"  {f}: {r}")
    print("== tile_list")
    compare_tile_list(nat, bob, tile_map, summary)
    print("== global_map")
    for f in ("global_map/global_blend.dds", "global_map/texture_arrays.xml", "global_map/tile_list.bin"):
        r = same_files(nat, bob, f"{t}/{f}")
        print(f"  {f}: {r}")
        summary.append((f, r))
    print("== global_meshes")
    fa, fb = compare_dir_counts(nat, bob, f"{t}/global_meshes", "global_meshes", summary)
    for kind in ("land_mesh", "sea_mesh"):
        na = len({f.split(".")[0] for f in fa if f.startswith(kind)})
        nb = len({f.split(".")[0] for f in fb if f.startswith(kind)})
        print(f"  {kind}: native {na}, BOB {nb}")
        summary.append((kind, f"{na} / {nb} meshes"))
    print("== rivers")
    compare_dir_counts(nat, bob, f"{t}/models", "models (river_N)", summary)
    compare_dir_counts(nat, bob, f"{t}/height_patches", "height_patches", summary)
    print("== global_props")
    compare_props(nat, bob, summary)
    print("== lookup")
    for f in ("3k_main_campaign_map_lookup.dds", "3k_main_campaign_map_lookup.tga", "3k_main_campaign_map_lookup_minimap.tga"):
        r = same_files(nat, bob, f"{c}/{f}")
        print(f"  {f}: {r}")
        summary.append((f, r))
    print("\n| Output | native / BOB |\n|---|---|")
    for k, v in summary:
        print(f"| {k} | {v} |")


main()
