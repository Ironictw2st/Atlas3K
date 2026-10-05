import sys, json
sys.path.insert(0, '.')
import rpfm_mcp as R
sid = R.session()
K = r"C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\data\!!190_expanded_region_test_main190.pack"
def call(name, args, t=600):
    _, m = R.post({"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": name, "arguments": args}}, sid, t)
    return json.dumps(m[-1])[:600]
mode = sys.argv[1]
if mode == "open":
    print(call("close_all_packs", {}, 120))
    print(call("set_game_selected", {"game_name": "three_kingdoms", "rebuild_dependencies": False}))
    print(call("open_packfiles", {"paths": [K]}))
elif mode in ("build1", "build0"):
    print(call("build_starpos", {"pack_key": K, "campaign_id": "3k_main_campaign_map", "process_hlp_spd": mode == "build1"}, 20000))
elif mode == "post":
    for n, a in (("build_starpos_post", {"pack_key": K, "campaign_id": "3k_main_campaign_map", "process_hlp_spd": True}), ("save_packfile", {"pack_key": K}), ("close_all_packs", {})):
        print(n, call(n, a, 3000))
