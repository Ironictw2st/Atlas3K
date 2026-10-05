"""Tile database sort: does the MsvcSort port + TILE_DATABASE::sort comparator (area desc, link targets desc, name
ordinal) turn BOB's load order into BOB's sorted order? Keys from the Frida dump (file|name|w|h|link_targets).
usage: db_sort_check.py <frida jsonl>"""
import json, sys
from pathlib import Path
sys.argv += []
msgs = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8")]
pairs = [(m["tiles"], n["tiles"]) for m, n in zip([m for m in msgs if m["kind"] == "db_before"], [m for m in msgs if m["kind"] == "db_after"])]
src = open(Path(__file__).parent / "sort_check.py", encoding="utf-8").read()
exec(src[src.index("def msvc_sort"):src.index("for p, kind in")])          # msvc_sort()
def parse(t):
    f, name, w, h, lt = t.split("|"); return f.lower(), name, int(w), int(h), int(lt)
def less(x, y):                                     # FUN_1803e8ef0 (TILE_DATABASE::sort comparator)
    a, b = parse(x), parse(y)
    if a[2] * a[3] != b[2] * b[3]: return a[2] * a[3] > b[2] * b[3]
    if a[4] != b[4]: return a[4] > b[4]
    return a[1].encode("latin1") < b[1].encode("latin1")
for k, (bef, aft) in enumerate(pairs):
    out = msvc_sort(list(bef), less)
    same = [parse(x)[0] for x in out] == [parse(x)[0] for x in aft]
    print(f"db sort #{k}: n {len(bef)}  port == BOB: {same}")
    if not same:
        i = next(i for i, (x, y) in enumerate(zip(out, aft)) if x != y)
        print("  first diff", i, "port", out[i:i + 3], "\n  bob ", aft[i:i + 3])
    # compare with the simulator's assumed keys if the sim db order export is there
    so = Path(sys.argv[1]).parent / "sim_order_db.txt"
    if len(bef) == 544 and so.exists():
        sim = [l.split()[0].lower() for l in open(so, encoding="utf-8")]
        print("  sim db order == BOB:", sim == [parse(x)[0] for x in aft], "| sim == port(BOB input):", sim == [parse(x)[0] for x in out])
