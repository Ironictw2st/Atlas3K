#!/usr/bin/env python3
"""Resource re-theme of the new x15 resource regions (user 2026-10-04: fewer northern horses, silk only on the Silk Road,
grounded in 190 AD; plan "re-theme the resources of the 77 new resource regions"). Writes regions_new.json "retemplate"
entries; retemplate_x15.py (run by regions_db.py) applies them to the start-pos tables. Regions that keep grain are listed
too so the intent is recorded (retemplate_x15 skips them as already matching).
Rule (user 2026-10-04): fishing / trading ports only for settlements ON the coastline (vanilla: town 1 hex from sea);
the new towns sit 2+ hexes inland (city-bar rule), so none of them gets 3k_resource_wood_fish / water_trading_port."""
import json, shutil, time
from pathlib import Path
HERE = Path(__file__).parent
R = "3k_resource_"
PLAN = {
    # Central Plains
    "ironic_central_hejian_capital": "wood_farms_grain", "ironic_central_ba_resource_3": "water_salt",
    "ironic_central_ba_resource_1": "wood_lumber_bamboo", "ironic_central_ba_resource_2": "wood_tea",
    "ironic_central_yingchuan_resource_1": "wood_farms_grain", "ironic_central_jiyin_capital": "metal_tools",
    "ironic_central_henan_resource_1": "wood_farms_grain", "ironic_central_zhuo_capital": "wood_livestock",
    "ironic_central_jibei_capital": "metal_tools", "ironic_central_donghai_resource_1": "water_salt",
    "ironic_central_donghai_resource_2": "wood_lumber_pine", "ironic_central_qi_capital": "water_salt",
    "ironic_central_xiapi_resource_4": "wood_farms_rice", "ironic_central_guangling_resource_2": "water_salt",
    "ironic_central_jiangxia_capital": "wood_lumber_pine", "ironic_central_jiangxia_resource_3": "metal_copper",
    "ironic_central_jiangxia_resource_2": "wood_farms_rice", "ironic_central_longxi_capital": "wood_livestock",
    "ironic_central_longxi_resource_1": "fire_northern_horses", "ironic_central_beidi_capital": "wood_livestock",
    "ironic_central_henan_resource_2": "metal_craftsmen_weapon", "ironic_central_nan_resource_3": "wood_lumber_pine",
    "ironic_central_nanyang_resource_1": "fire_iron", "ironic_central_nan_resource_1": "wood_lumber_pine",
    "ironic_central_nan_resource_2": "wood_farms_grain", "ironic_central_lujiang_resource_1": "wood_farms_rice",
    "ironic_central_pei_resource_1": "wood_farms_grain", "ironic_central_rencheng_capital": "wood_farms_grain",
    "ironic_central_qinghe_capital": "wood_farms_grain", "ironic_central_runan_capital": "wood_farms_grain",
    "ironic_central_qianwei_sg_capital": "wood_tea", "ironic_central_xiapi_resource_3": "wood_livestock",
    "ironic_central_xiapi_resource_2": "wood_farms_grain", "ironic_central_yanmen_resource_1": "wood_livestock",
    "ironic_central_yanmen_resource_2": "metal_copper", "ironic_central_chenliu_capital": "wood_farms_grain",
    "ironic_central_yuyang_capital": "fire_iron",
    # South
    "ironic_south_wu_resource_2": "metal_craftsmen_armour", "ironic_south_wu_resource_3": "wood_lumber_bamboo",
    "ironic_south_kuaiji_resource_1": "wood_farms_rice", "ironic_south_kuaiji_resource_2": "wood_lumber_pine",
    "ironic_south_danyang_resource_1": "metal_copper", "ironic_south_yuzhang_resource_1": "wood_lumber_pine",
    "ironic_south_changsha_resource_2": "wood_farms_rice", "ironic_south_changsha_resource_3": "wood_farms_rice",
    "ironic_south_wuling_resource_2": "wood_tea", "ironic_south_lingling_resource_1": "wood_farms_rice",
    "ironic_south_lingling_resource_2": "wood_farms_rice", "ironic_south_lingling_resource_3": "wood_lumber_bamboo",
    "ironic_south_guiyang_resource_2": "metal_tools", "ironic_south_cangwu_resource_1": "wood_lumber_bamboo",
    "ironic_south_yulin_resource_2": "water_spice", "ironic_south_yizhou_c_resource_1": "metal_jade",
    # Steppe
    "ironic_nomad_wuhuan_shanggu_resource_1": "fire_northern_horses", "ironic_nomad_suli_resource_1": "fire_northern_horses",
    "ironic_nomad_suli_resource_3": "wood_livestock", "ironic_nomad_suli_resource_2": "wood_lumber_pine",
    "ironic_nomad_wuhuan_liaoxi_resource_1": "wood_livestock", "ironic_nomad_wuhuan_liaoxi_resource_2": "metal_copper",
    "ironic_nomad_wuhuan_liaoxi_resource_3": "wood_lumber_pine", "ironic_nomad_wuhuan_youbeiping_capital": "wood_lumber_pine",
    "ironic_nomad_kebineng_resource_1": "wood_livestock", "ironic_nomad_kebineng_resource_2": "wood_livestock",
    "ironic_nomad_kebineng_resource_4": "wood_livestock", "ironic_nomad_kebineng_resource_3": "wood_livestock",
    "ironic_nomad_budugen_resource_1": "fire_iron", "ironic_nomad_budugen_resource_2": "water_salt",
    # Hexi
    "ironic_hexi_dunhuang_resource_1": "water_silk",
    # Korea
    "ironic_region_buyeo_resource_1": "fire_northern_horses", "ironic_region_bukokjeo_resource_1": "wood_lumber_pine",
    "ironic_region_goguryeo_resource_1": "fire_iron", "ironic_region_fanhan_resource_1": "wood_lumber_pine",
    "ironic_region_dongye_resource_2": "wood_livestock", "ironic_region_hanseong_resource_3": "wood_farms_rice",
    "ironic_region_ye_resource_2": "wood_lumber_pine", "ironic_region_gyeongju_resource_2": "fire_iron",
    "ironic_region_kimhae_resource_2": "fire_iron",
}


def main():
    p = HERE / "regions_new.json"
    shutil.copy2(p, HERE / f"regions_new_pre_retheme_{time.strftime('%Y%m%d_%H%M%S')}.json")
    nj = json.load(open(p, encoding="utf-8"))
    rt = nj.setdefault("retemplate", {})
    assert not {"wood_fish", "water_trading_port"} & set(PLAN.values()), "coast-only resources need a coastal town"
    for reg, res in PLAN.items():
        rt[reg] = {"type": "resource", "resource": R + res}
    json.dump(nj, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    import collections
    print(f"retemplate entries: {len(rt)} ({len(PLAN)} resource re-themes)", collections.Counter(PLAN.values()).most_common())


if __name__ == "__main__":
    main()
