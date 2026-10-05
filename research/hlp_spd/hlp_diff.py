import pickle, sys
from hlp_parse import parse
entries=pickle.load(open("/tmp/hlp_entries07.pkl","rb"))
h,nodes,_,_=parse("../../output/hlp_spd/vanilla/campaign_maps/3k_dlc07_main_map/hlp_data.esf")
ref={s["area"]:s for n in nodes for s in n["subs"]}
mine={E["aid"]:E for r in entries for E in entries[r]}
shown=0
for aid in sorted(ref):
    s=ref[aid]; E=mine[aid]
    rs={(t["p"],t["q"],t["to"]) for t in s["tr"]}; ms={(t["p"],t["q"],t["to"]) for t in E["tr"]}
    if rs==ms: continue
    print("AREA",aid,"centre",s["centre"])
    for t in s["tr"]: print("  ref ",t["p"],t["q"],t["cost"],t["to"],t["idx"],t["f1"], "" if (t["p"],t["q"],t["to"]) in ms else "<<")
    for t in E["tr"]: print("  mine",t["p"],t["q"],t["cost"],t["to"],t["idx"],t["f1"], "" if (t["p"],t["q"],t["to"]) in rs else "<<")
    shown+=1
    if shown>=int(sys.argv[1]) if len(sys.argv)>1 else 6: break
