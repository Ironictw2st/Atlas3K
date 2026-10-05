"""Walk TileMatchSimulator placements in order (CSV) against a BOB tile_list.bin: first diverging placement, match
rate before / after it, mismatches by tile set. usage: sim_first_divergence.py <sim.csv> <tile_list.bin> [n_show]"""
import collections, sys
from pathlib import Path
exec(open(Path(__file__).parent / "sim_compare.py", encoding="utf-8").read().split("sim = []")[0])   # read_tl()
BS = chr(92)
sim = []
for line in open(sys.argv[1]):
    loc, x, y, r, c, layer = line.strip().rsplit(",", 5)
    sim.append((loc.lower().rstrip(BS), int(x), int(y), int(r), int(c), int(layer)))
ref = read_tl(sys.argv[2])
R = collections.Counter((r[0], r[1], r[2], r[3]) for r in ref)
Rpos = collections.defaultdict(list)
for r in ref: Rpos[(r[1], r[2])].append(r)
ok = []
for s in sim:
    k = s[:4]
    if R[k] > 0: R[k] -= 1; ok.append(True)
    else: ok.append(False)
bad = [i for i, o in enumerate(ok) if not o]
n = len(sim); first = bad[0] if bad else n
print(f"placements {n}, BOB records {len(ref)}, exact matches {n - len(bad)} ({1 - len(bad) / n:.3%}); first divergence at #{first}")
def rate(lo, hi): return sum(ok[lo:hi]) / max(1, hi - lo)
for lo, hi in ((0, first), (first, first + 1000), (first + 1000, n // 4), (n // 4, n // 2), (n // 2, n)):
    if hi > lo: print(f"  placements {lo:>7}..{hi:<7} match {rate(lo, hi):.3f}")
name = lambda p: p.split(BS)[-1] or p.split(BS)[-2]
setname = lambda p: (p.split(BS) + [""] * 5)[3]
print("mismatches by tile set:", collections.Counter(setname(sim[i][0]) for i in bad).most_common(10))
for i in bad[:int(sys.argv[3]) if len(sys.argv) > 3 else 12]:
    s = sim[i]; there = Rpos.get((s[1], s[2]), [])
    print(f"  #{i}: sim {name(s[0])} @({s[1]},{s[2]}) rot {s[3]}  | BOB at that point: {[(name(t[0]), t[3]) for t in there] or 'nothing'}")
