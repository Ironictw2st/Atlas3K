"""Extra / missing (area -> target area) pairs between two hlp files, with hex types of the transition ends."""
import sys, collections; sys.path.insert(0, '.')
from hlp_parse import parse
from ppd import Ppd
mine = parse(sys.argv[1])[1]; ref = parse(sys.argv[2])[1]
p = Ppd(sys.argv[3]); t = p.hex_type()
def pairs(nodes):
    out = {}
    for n in nodes:
        for s in n["subs"]:
            for tr in s["tr"]: out.setdefault((s["area"], tr["to"]), []).append(tr)
    return out
M, R = pairs(mine), pairs(ref)
atype = {}
extra = [k for k in M if k not in R]; missing = [k for k in R if k not in M]
print("pairs mine", len(M), "ref", len(R), "extra", len(extra), "missing", len(missing))
c = collections.Counter()
for k in extra:
    tr = M[k][0]; c[(int(t[tr["p"][1], tr["p"][0]]), int(t[tr["q"][1], tr["q"][0]]))] += 1
print("extra by (type p, type q)", c.most_common())
for k in extra[:15]: tr = M[k][0]; print(" extra", k, tr["p"], tr["q"], tr["cost"])
for k in missing[:15]: tr = R[k][0]; print(" missing", k, tr["p"], tr["q"], tr["cost"])
cr = collections.Counter(); ex = collections.defaultdict(list)
for k, trs in R.items():
    for tr in trs:
        key = (int(t[tr["p"][1], tr["p"][0]]), int(t[tr["q"][1], tr["q"][0]]))
        cr[key] += 1
        if len(ex[key]) < 3: ex[key].append((k, tr["p"], tr["q"], tr["cost"], tr["f1"], tr["f2"]))
print("ref transitions by types", cr.most_common())
for k, v in ex.items(): print(k, v)
cm = collections.Counter()
for k, trs in M.items():
    for tr in trs: cm[(int(t[tr["p"][1], tr["p"][0]]), int(t[tr["q"][1], tr["q"][0]]))] += 1
print("mine transitions by types", cm.most_common())
