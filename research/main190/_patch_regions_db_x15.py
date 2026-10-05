"""one-off: extend regions_db.py for the x15 export (carve_x15.py regions_new.json)."""
p = 'regions_db.py'; s = open(p, encoding='utf-8').read()


def rep(old, new):
    global s
    assert s.count(old) == 1, old[:80]
    s = s.replace(old, new, 1)


rep('''def info6(p):''', '''# x15 (carve_x15.py, 2026-10-01): flavour by Han zhou (190E's ironic_province_* templates), steppe by group
FLAVOUR_X15 = {"Sili": "ironic_province_sili_standard", "Yuzhou": "ironic_province_yu_standard", "Yanzhou": "ironic_province_yan_standard",
               "Jizhou": "ironic_province_ji_standard", "Qingzhou": "ironic_province_qing_standard", "Xuzhou": "ironic_province_xu_standard",
               "Youzhou": "ironic_province_you_wuhuan", "Bingzhou": "ironic_province_bing_standard", "Liangzhou": "ironic_province_liang_standard",
               "Yizhou": "ironic_province_yi_standard", "Jingzhou": "ironic_province_jing_standard", "Yangzhou": "ironic_province_yang_standard",
               "Jiaozhou": "ironic_province_jiao_standard", "Yongzhou": "ironic_province_yong_standard"}
FLAVOUR_STEPPE = {"xiongnu": "ironic_province_bing_xiongnu", "wuhuan": "ironic_province_you_wuhuan"}     # else Xianbei
OWNER_CAMPAIGNS = {"3k_dlc04_start_pos", "3k_main_campaign_map", "8p_start_pos"}   # where the steppe factions exist (AK start_pos_factions)


def flavour_x15(p):
    if p.get("zhou") == "steppe":
        k = p["province"]
        return next((v for g, v in FLAVOUR_STEPPE.items() if g in k), "ironic_province_you_xianbei")
    return FLAVOUR_X15.get(p.get("zhou"), FLAVOUR6.get(p.get("zhou"), "ironic_province_yu_standard"))


def info6(p):
    if "owners" in p:                                         # x15: names per region, flavour by zhou
        fl = flavour_x15(p); steppe = p.get("zhou") == "steppe"
        rt = "3k_resource_fire_northern_horses" if steppe else "3k_resource_wood_farms_grain"
        res = [(RESOURCE6.get(p["names"][n], rt), p["names"][n]) for n in p["regions"]]
        return p["label"], fl, res, None''')

rep('''    for key, p in prov.items():
        onscreen, flavour, res, capname = info6(p) if "names" in p else INFO[key]
        for j, rk in enumerate(p["regions"]):''', '''    for key, p in prov.items():
        onscreen, flavour, res, capname = info6(p) if "names" in p else INFO[key]
        if "owners" in p:                                     # x15
            for j, rk in enumerate(p["regions"]):
                c, r = p["towns"][rk]; cl = climates[f["climate"][r, c]] if f["climate"][r, c] >= 0 else "temperate"
                cap = rk == p.get("capital")
                regions.append(dict(key=rk, province=p["province"], prov_name=onscreen, cap=cap, climate=cl,
                                    name=p["names"][rk], res=None if cap else res[j][0], flavour=flavour, owner=p["owners"].get(rk),
                                    colour=new_colour(), layout=LAYOUTS[len(regions) % 3]))
            continue
        for j, rk in enumerate(p["regions"]):''')

rep('''    newprov = {k: p for k, p in prov.items() if not p.get("attach")}        # attached regions join an existing province''',
    '''    newprov = {k: p for k, p in prov.items() if not p.get("attach")}        # attached regions join an existing province
    if X15:                                                   # x15: every new province of the export (capital may be an existing region)
        newprov = {np_["key"]: dict(province=np_["key"], label=np_["label"], names={}, owners={}, regions=[], zhou=np_.get("zhou"))
                   for np_ in X15["new_provinces"]}''')

rep('''[{"key": f"provinces_onscreen_{p['province']}", "text": (info6(p) if "names" in p else INFO[k])[0], "tooltip": "false"} for k, p in newprov.items()])''',
    '''[{"key": f"provinces_onscreen_{p['province']}", "text": p["label"] if X15 else (info6(p) if "names" in p else INFO[k])[0], "tooltip": "false"} for k, p in newprov.items()])''')

rep('''        lambda t: [clone(t["p"], p["province"], key=p["province"], onscreen=(info6(p) if "names" in p else INFO[k])[0]) for k, p in newprov.items()])''',
    '''        lambda t: [clone(t["p"], p["province"], key=p["province"], onscreen=p["label"] if X15 else (info6(p) if "names" in p else INFO[k])[0]) for k, p in newprov.items()])''')

rep('''            spr.append(dict(region=r["key"], campaign=camp, id=rid, owning_faction="", faction_capital="false",''',
    '''            spr.append(dict(region=r["key"], campaign=camp, id=rid, owning_faction=(r.get("owner") or "") if camp in OWNER_CAMPAIGNS else "", faction_capital="false",''')

rep('''                rec = re.sub(r"<owning_faction>[^<]*</owning_faction>", "<owning_faction></owning_faction>", rec)''',
    '''                own_ = (r.get("owner") or "") if camp in OWNER_CAMPAIGNS else ""
                rec = re.sub(r"<owning_faction>[^<]*</owning_faction>", f"<owning_faction>{own_}</owning_faction>", rec)''')

rep('''def r7_changes():
    """Round 7 (candidates.json): on-screen renames of existing regions, existing regions moving province, province renames."""
    c = json.load(open(HERE / "research_r6" / "candidates.json", encoding="utf-8"))''', '''X15 = None                  # x15: regions_new.json from carve_x15.py (set in main)


def x15_junctions():
    """region -> (province, is_capital) for EVERY region of the export (authoritative membership by identity)."""
    out = {}
    for pv in X15["all_provinces"]:
        for m in pv["members"]: out[m] = (pv["key"], m == pv["capital"])
    return out


def r7_changes():
    """Round 7 (candidates.json): on-screen renames of existing regions, existing regions moving province, province renames.
    x15: the same three from regions_new.json (carve_x15.py, the proposal export)."""
    if X15: return X15.get("renames", {}), X15.get("province_moves", {}), X15.get("province_renames", {})
    c = json.load(open(HERE / "research_r6" / "candidates.json", encoding="utf-8"))''')

rep('''        if len(a_) >= 3 and a_[1] in pmove: a_[0] = pmove[a_[1]]; a_[2] = "false"; lines[i_] = TAB.join(a_); hit += 1''',
    '''        if X15:
            J = x15_junctions()
            if len(a_) >= 3 and a_[1] in J and (a_[0], a_[2]) != (J[a_[1]][0], "true" if J[a_[1]][1] else "false"):
                a_[0] = J[a_[1]][0]; a_[2] = "true" if J[a_[1]][1] else "false"; lines[i_] = TAB.join(a_); hit += 1
            continue
        if len(a_) >= 3 and a_[1] in pmove: a_[0] = pmove[a_[1]]; a_[2] = "false"; lines[i_] = TAB.join(a_); hit += 1''')

rep('''        rec = mm.group(0); rg = re.search(r"<region>([^<]*)</region>", rec)
        if not rg or rg.group(1) not in pmove: return rec''', '''        rec = mm.group(0); rg = re.search(r"<region>([^<]*)</region>", rec)
        if X15:
            J = x15_junctions()
            if not rg or rg.group(1) not in J: return rec
            old = re.search(r"<province>([^<]*)</province>", rec).group(1); new, cap = J[rg.group(1)]
            was_cap = re.search(r"<is_capital>([^<]*)</is_capital>", rec).group(1) in ("1", "true")
            if (old, was_cap) == (new, cap): return rec
            hit += 1
            rec = rec.replace(f'record_key="{rg.group(1)}{old}"', f'record_key="{rg.group(1)}{new}"')
            rec = re.sub(r"<province>[^<]*</province>", f"<province>{new}</province>", rec)
            return re.sub(r"<is_capital>[^<]*</is_capital>", f"<is_capital>{int(cap)}</is_capital>", rec)
        if not rg or rg.group(1) not in pmove: return rec''')

rep('''def main():
    prov = json.load(open(HERE / "regions_new.json", encoding="utf-8")); prov = prov.get("provinces", prov)   # round 6 format''',
    '''def main():
    global X15
    nj = json.load(open(HERE / "regions_new.json", encoding="utf-8")); prov = nj.get("provinces", nj)   # round 6 format
    if "all_provinces" in nj: X15 = nj; print("x15 mode:", len(prov), "provinces with new regions;", len(nj["new_provinces"]), "new provinces")''')

open(p, 'w', encoding='utf-8').write(s); print('regions_db patched')
