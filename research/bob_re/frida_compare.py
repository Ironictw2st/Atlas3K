"""Compare a Frida dump of BOB's tile database / pass orders with the simulator's (--pass-order exports).
usage: frida_compare.py <frida jsonl> [sim order dir]"""
import json, sys
from pathlib import Path
src = Path(sys.argv[1]); simdir = Path(sys.argv[2]) if len(sys.argv) > 2 else src.parent
msgs = [json.loads(l) for l in open(src, encoding="utf-8")]
first = lambda k, p=None: next((m["tiles"] for m in msgs if m["kind"] == k and (p is None or m.get("pass") == p)), None)
fname = lambda t: t.split("|")[0].lower()
def sim(name):
    p = simdir / f"sim_order_{name}.txt"
    return [l.split()[0].lower() for l in open(p, encoding="utf-8")] if p.exists() else None
def cmp(label, bob, s):
    if bob is None or s is None: print(f"{label}: missing ({'bob' if bob is None else 'sim'})"); return
    b = [fname(t) for t in bob]
    same = sum(x == y for x, y in zip(b, s))
    i = next((k for k, (x, y) in enumerate(zip(b, s)) if x != y), None)
    print(f"{label}: bob {len(b)} sim {len(s)}; same position {same}/{len(b)}; sets equal {set(b) == set(s)}; first difference at {i}")
    if i is not None: print(f"   bob[{i}:{i+6}] {b[i:i+6]}\n   sim[{i}:{i+6}] {s[i:i+6]}")
# load order: what BOB had before TILE_DATABASE::sort vs the simulator's assumption (lower-case ordinal file names)
lo = [fname(t) for t in first("db_before")]
print("load order is lower-case ordinal:", lo == sorted(lo), "| case-sensitive ordinal:", [t.split('|')[0] for t in first('db_before')] == sorted(t.split('|')[0] for t in first('db_before')))
print("load order first 8:", lo[:8])
cmp("db (after TILE_DATABASE::sort)", first("db_after"), sim("db"))
for p in (1, 2, 3, 4, 5, 0):
    k = "sort_junction_after" if p == 3 else "sort_after"
    cmp(f"pass {p} sorted", first(k, p), sim(str(p)))
