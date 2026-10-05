import pickle, sys, collections
from hlp_parse import parse
entries=pickle.load(open("/tmp/hlp2_result07.pkl","rb"))
h,nodes,_,_=parse("../../output/hlp_spd/vanilla/campaign_maps/3k_dlc07_main_map/hlp_data.esf")
ref={s["area"]:s for n in nodes for s in n["subs"]}
mine={E["aid"]:E for E in entries}
n=int(sys.argv[1]) if len(sys.argv)>1 else 5; skip=int(sys.argv[2]) if len(sys.argv)>2 else 0
cat=collections.Counter()
shown=0
for aid in sorted(ref):
    s=ref[aid]; E=mine[aid]
    rs={(t["p"],t["q"],t["to"]):t for t in s["tr"]}; ms={(t["p"],t["q"],t["to"]):t for t in E["tr"]}
    for k,t in rs.items():
        if k not in ms: cat[("missing", t["f1"], t["idx"]==0)]+=1
        elif ms[k]["cost"]!=t["cost"]: cat[("cost", t["f1"], ms[k]["cost"] is None)]+=1
    if set(rs)==set(ms) and all(ms[k]["cost"]==rs[k]["cost"] for k in rs): continue
    if skip>0: skip-=1; continue
    if shown<n:
        print("AREA",aid,"centre",s["centre"])
        for t in s["tr"]: print("  ref ",t["p"],t["q"],t["cost"],t["to"],t["idx"],t["f1"], "" if (t["p"],t["q"],t["to"]) in ms and ms[(t["p"],t["q"],t["to"])]["cost"]==t["cost"] else "<<")
        for t in E["tr"]: print("  mine",t["p"],t["q"],t["cost"],t["to"],t["idx"],t["f1"], "" if (t["p"],t["q"],t["to"]) in rs else "<<")
        shown+=1
print(cat)
