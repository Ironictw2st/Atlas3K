#!/usr/bin/env python3
"""DB rows for the new main190 regions (regions_new.json from regions_carve.py), in the user's ironic_added_regions
pattern. Nothing live is modified:
  db_out/   pack side: the source/ TSVs (the region-test pack's tables + loc) with the new rows appended
  ak_db/    AK side: copies of assembly_kit_190E raw_data/db XMLs with new records cloned from the ironic Xiping /
            Wuyuan records (installed with a backup in Phase 4)
All 5 campaigns get every new region, unowned (the pattern's unowned Xiping rows: 3k_city_0, no buildings).
Capitals: primary 3k_city + secondary 3k_districts. Resources: a themed primary resource + the secondary
ironic_province_<han province>_<culture> template of the historical province. Population 15 (capital) / 12.
"""
import csv, json, os, random, re, shutil, sys, uuid
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
import crop_scale_map_hex as C, hexmap
from rebuild_hex import unpack

SRC = HERE / "source"; OUT = HERE / "db_out"; AKOUT = HERE / "ak_db"
# 190E ORIGINAL db (the kit copy gets our rows appended by install_ak.py - re-reading it would duplicate them)
AKDB = Path(r"Z:/Claude/TerryClone/output/backups/main190_originals_20260929_130639/ak190E_db")
CAMPAIGNS = {"3k_dlc04_start_pos": "data_3k_dlc04_start_pos", "3k_dlc05_start_pos": "data_3k_dlc05_start_pos",
             "3k_dlc07_start_pos": "data_3k_dlc07_start_pos", "3k_main_campaign_map": "data_3k_main_campaign_map",
             "8p_start_pos": "data_8p_start_pos"}
# province key -> (onscreen, flavour template, [(resource template, name) per resource], capital name)
INFO = {
    "chenliu": ("Chenliu", "ironic_province_yan_standard", [("3k_resource_water_silk", "Xiangyi")], "Chenliu"),
    "liang": ("Liang", "ironic_province_yu_standard", [("3k_resource_wood_farms_grain", "Xiayi")], "Suiyang"),
    "pei": ("Pei", "ironic_province_yu_standard", [("3k_resource_wood_farms_grain", "Qiao")], "Xiang"),
    "jiyin": ("Jiyin", "ironic_province_yan_standard", [("3k_resource_wood_farms_grain", "Chengwu")], "Dingtao"),
    "shanyang": ("Shanyang", "ironic_province_yan_standard", [("3k_resource_wood_fish", "Juye")], "Changyi"),
    "lu": ("Lu", "ironic_province_yu_standard", [("3k_resource_earth_temple", "Zou")], "Lu"),
    "dongping": ("Dongping", "ironic_province_yan_standard", [("3k_resource_wood_livestock", "Shouzhang")], "Wuyan"),
    "hongnong": ("Hongnong", "ironic_province_sili_standard", [("3k_resource_metal_copper", "Lushi")], "Hongnong"),
    "juyan": ("Juyan", "ironic_province_liang_xiliang", [("3k_resource_fire_northern_horses", "Ruoshui")], "Juyan"),
    "jiuquan": ("Jiuquan", "ironic_province_liang_standard", [("3k_resource_wood_livestock", "Biaoshi")], "Lufu"),
    "dunhuang": ("Dunhuang", "ironic_province_liang_standard", [("3k_resource_metal_jade", "Yumen")], "Dunhuang"),
    "yunzhong": ("Yunzhong", "ironic_province_bing_xiongnu",
                 [("3k_resource_fire_northern_horses", "Xianling"), ("3k_resource_wood_livestock", "Shanan")], "Yunzhong"),
    "dingxiang": ("Dingxiang", "ironic_province_bing_xiongnu",
                  [("3k_resource_wood_livestock", "Chengle"), ("3k_resource_water_salt", "Wucheng")], "Shanwu"),
    "danhan": ("Danhan", "ironic_province_you_xianbei",
               [("3k_resource_fire_northern_horses", "Chuoqiu"), ("3k_resource_wood_livestock", "Yinshan")], "Danhan"),
    "shanggu": ("Shanggu", "ironic_province_you_wuhuan",
                [("3k_resource_wood_lumber_pine", "Zhuolu"), ("3k_resource_fire_northern_horses", "Ning")], "Juyong"),
    "liaoxi": ("Liaoxi", "ironic_province_you_wuhuan",
               [("3k_resource_wood_livestock", "Liucheng"), ("3k_resource_fire_northern_horses", "Linyu")], "Yangle"),
    # Hebei plain around Ye (round 5)
    "zhao": ("Zhao", "ironic_province_ji_standard", [("3k_resource_fire_iron", "Xiangguo")], "Handan"),
    "julu": ("Julu", "ironic_province_ji_standard", [("3k_resource_wood_farms_grain", "Julu")], "Yingtao"),
    "changshan": ("Changshan", "ironic_province_ji_standard", [("3k_resource_metal_tools", "Zhending")], "Yuanshi"),
    "hejian": ("Hejian", "ironic_province_ji_standard", [("3k_resource_wood_farms_grain", "Gaoyang")], "Lecheng"),
    "qinghe": ("Qinghe", "ironic_province_ji_standard", [("3k_resource_water_silk", "Dongwucheng")], "Ganling"),
}
# round 6 (regions_carve6.py): names come with the province; flavour by Han province, resource by town
FLAVOUR6 = {"Jizhou": "ironic_province_ji_standard", "Youzhou": "ironic_province_you_wuhuan", "Qingzhou": "ironic_province_qing_standard",
            "Yanzhou": "ironic_province_yan_standard", "Yuzhou": "ironic_province_yu_standard", "Bingzhou (frontier)": "ironic_province_bing_xiongnu"}
RESOURCE6 = {"Guandu": "3k_resource_wood_farms_grain", "Xiangguo": "3k_resource_fire_iron", "Zhending": "3k_resource_metal_tools", "Juye": "3k_resource_wood_fish",
             "Zou": "3k_resource_earth_temple", "Fanyang": "3k_resource_wood_livestock", "Mao": "3k_resource_water_silk"}


# x15 (carve_x15.py, 2026-10-01): flavour by Han zhou (190E's ironic_province_* templates), steppe by group
FLAVOUR_X15 = {"Sili": "ironic_province_sili_standard", "Yuzhou": "ironic_province_yu_standard", "Yanzhou": "ironic_province_yan_standard",
               "Jizhou": "ironic_province_ji_standard", "Qingzhou": "ironic_province_qing_standard", "Xuzhou": "ironic_province_xu_standard",
               "Youzhou": "ironic_province_you_wuhuan", "Bingzhou": "ironic_province_bing_standard", "Liangzhou": "ironic_province_liang_standard",
               "Yizhou": "ironic_province_yi_standard", "Jingzhou": "ironic_province_jing_standard", "Yangzhou": "ironic_province_yang_standard",
               "Jiaozhou": "ironic_province_jiao_standard", "Yongzhou": "ironic_province_yong_standard",
               # Korea rework (korea_x15.py, 2026-10-02): 190E's own Korean flavours
               "KoreaNorth": "ironic_province_korea_standard", "KoreaSouth": "ironic_province_southern_korea_standard",
               "KoreaNE": "ironic_province_southern_korea_northern_korea"}
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
        return p["label"], fl, res, None
    if p.get("attach"):                                         # one resource region in an existing province
        n = p["regions"][0]; return p["label"], FLAVOUR6.get(p.get("zhou"), "ironic_province_yu_standard"), [(RESOURCE6.get(p["names"][n], "3k_resource_wood_farms_grain"), p["names"][n])], None
    res = [(RESOURCE6.get(p["names"][n], "3k_resource_wood_farms_grain"), p["names"][n]) for n in p["regions"][1:]]
    return p["label"], FLAVOUR6.get(p.get("zhou"), "ironic_province_yan_standard"), res, p["names"][p["regions"][0]]


# name a new town takes -> (old region using it, the old region's new name) - Jinan's seat Dongpingling is vanilla's
# name for the Taishan capital; Taishan's own Han seat was Fenggao
RENAMES = {}                # round 7: Jinan/Dongpingling is not a new region any more (Taishan capital keeps Dongpingling)


X15 = None                  # x15: regions_new.json from carve_x15.py (set in main)


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
    c = json.load(open(HERE / "research_r6" / "candidates.json", encoding="utf-8"))
    return c.get("renames_r7", {}), c.get("province_r7", {}), c.get("province_renames_r7", {})


def loc_set(path, rows):
    """Set (or insert) key -> text rows of a loc TSV."""
    lines = open(path, encoding="utf-8", newline="").read().split(LF); done = set()
    for i_, line in enumerate(lines):
        a_ = line.split(TAB)
        if a_[0] in rows: a_[1] = rows[a_[0]]; lines[i_] = TAB.join(a_); done.add(a_[0])
    for k, v in rows.items():
        if k not in done: lines.insert(2, TAB.join([k, v, "false"]))
    open(path, "w", encoding="utf-8", newline="").write(LF.join(lines)); return len(rows)


def pack_r7(n):
    ren, pmove, pren = r7_changes()
    jp = OUT / "db" / "region_to_province_junctions_tables" / "data__.tsv"
    lines = open(jp, encoding="utf-8", newline="").read().split(LF); hit = 0
    for i_, line in enumerate(lines):
        a_ = line.split(TAB)
        if X15:
            J = x15_junctions()
            if len(a_) >= 3 and a_[1] in J and (a_[0], a_[2]) != (J[a_[1]][0], "true" if J[a_[1]][1] else "false"):
                a_[0] = J[a_[1]][0]; a_[2] = "true" if J[a_[1]][1] else "false"; lines[i_] = TAB.join(a_); hit += 1
            continue
        if len(a_) >= 3 and a_[1] in pmove: a_[0] = pmove[a_[1]]; a_[2] = "false"; lines[i_] = TAB.join(a_); hit += 1
    open(jp, "w", encoding="utf-8", newline="").write(LF.join(lines)); n["r7 province moves (pack)"] = hit
    rows = {}
    for k, v in ren.items(): rows[f"regions_onscreen_{k}"] = v; rows[f"regions_battle_name_{k}"] = v
    n["r7 region renames (pack loc)"] = loc_set(OUT / "text" / "db" / "regions.loc.tsv", rows)
    n["r7 province renames (pack loc)"] = loc_set(OUT / "text" / "db" / "provinces.loc.tsv", {f"provinces_onscreen_{k}": v for k, v in pren.items()})


def ak_r7(m):
    ren, pmove, pren = r7_changes()
    p = AKOUT / "region_to_province_junctions.xml"; t = open(p, encoding="utf-8", newline="").read(); hit = 0
    def fix(mm):
        nonlocal hit
        rec = mm.group(0); rg = re.search(r"<region>([^<]*)</region>", rec)
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
        if not rg or rg.group(1) not in pmove: return rec
        old = re.search(r"<province>([^<]*)</province>", rec).group(1); new = pmove[rg.group(1)]; hit += 1
        rec = rec.replace(f'record_key="{rg.group(1)}{old}"', f'record_key="{rg.group(1)}{new}"')
        rec = re.sub(r"<province>[^<]*</province>", f"<province>{new}</province>", rec)
        return re.sub(r"<is_capital>[^<]*</is_capital>", "<is_capital>0</is_capital>", rec)
    t = re.sub(r"<region_to_province_junctions .*?</region_to_province_junctions>", fix, t, flags=re.S)
    open(p, "w", encoding="utf-8", newline="").write(t); m["r7 province moves (AK)"] = hit
    for table, names_, fields in (("regions", ren, ("onscreen", "battle_name")), ("provinces", pren, ("onscreen",))):
        p = AKOUT / f"{table}.xml"; t = open(p, encoding="utf-8", newline="").read(); hit = 0
        for k, v in names_.items():
            mm = re.search(rf'<{table} [^>]*record_key="{re.escape(k)}".*?</{table}>', t, re.S)
            if not mm: continue
            rec = mm.group(0)
            for fld in fields: rec = re.sub(rf"<{fld}>[^<]*</{fld}>", f"<{fld}>{v}</{fld}>", rec)
            t = t[:mm.start()] + rec + t[mm.end():]; hit += 1
        open(p, "w", encoding="utf-8", newline="").write(t); m[f"r7 renames (AK {table})"] = hit


LAYOUTS = ["settlement_land_layout_a", "settlement_land_layout_b", "settlement_land_layout_c"]
CR, LF, TAB = chr(13), chr(10), chr(9)
rng = random.Random(190)


# ---------------- TSV (pack side) ----------------
def read_tsv(path):
    lines = open(path, encoding="utf-8", newline="").read().split("\n")
    return lines[0].split("\t"), lines[1], [l for l in lines[2:] if l.strip()]


def append_tsv(rel, rows):
    src = SRC / rel; dst = OUT / rel; dst.parent.mkdir(parents=True, exist_ok=True)
    hdr, meta, body = read_tsv(src)
    out = [("\t".join(str(r.get(h, "")) for h in hdr)) for r in rows]
    open(dst, "w", encoding="utf-8", newline="").write("\n".join([ "\t".join(hdr), meta] + body + out) + "\n")
    return len(out)


# ---------------- XML (AK side) ----------------
def records(text, table):
    return list(re.finditer(rf'<{table} record_uuid="[^"]*"[^>]*>.*?</{table}>(?:{CR}?{LF})?', text, re.S))


def set_tag(rec, tag, value):
    rec, n = re.subn(rf"(<{tag}(?: [^>]*)?>)[^<]*(</{tag}>)", lambda m: f"{m.group(1)}{value}{m.group(2)}", rec)
    assert n == 1, tag
    return rec


def clone(rec, record_key, **tags):
    rec = re.sub(r'record_uuid="\{[^}]*\}"', f'record_uuid="{{{uuid.uuid4()}}}"', rec, count=1)
    rec = re.sub(r'record_key="[^"]*"', f'record_key="{record_key}"', rec, count=1)
    for k, v in tags.items(): rec = set_tag(rec, k, v)
    return rec


def ak_append(table, pick, make):
    """Copy AK table XML to ak_db/, append records built by make(template_record)."""
    path = AKDB / f"{table}.xml"; text = open(path, encoding="utf-8", newline="").read()
    eol = CR + LF if CR + LF in text else LF
    recs = records(text, table)
    new = make({k: next(m.group(0) for m in recs if f(m.group(0))) for k, f in pick.items()})
    end = text.rindex("</dataroot>")
    AKOUT.mkdir(exist_ok=True)
    open(AKOUT / f"{table}.xml", "w", encoding="utf-8", newline="").write(text[:end] + "".join(r.rstrip(CR + LF) + eol for r in new) + text[end:])
    return len(new)


def main():
    global X15
    nj = json.load(open(HERE / "regions_new.json", encoding="utf-8")); prov = nj.get("provinces", nj)   # round 6 format
    if "all_provinces" in nj: X15 = nj; print("x15 mode:", len(prov), "provinces with new regions;", len(nj["new_provinces"]), "new provinces")
    if OUT.exists(): shutil.rmtree(OUT)
    shutil.copytree(SRC / "db", OUT / "db"); shutil.copytree(SRC / "text", OUT / "text")
    # used ids / colours
    blob = "".join(open(p, encoding="utf-8", errors="replace").read() for p in list(SRC.rglob("*.tsv")) +
                   [AKDB / f"{t}.xml" for t in ("start_pos_regions", "start_pos_settlements", "start_pos_region_slot_templates")])
    used = set(int(x) for x in re.findall(r"\b(\d{6,10})\b", blob))
    def new_id():
        while True:
            v = rng.randrange(100_000_000, 2_147_483_647)
            if v not in used: used.add(v); return v
    ak_regions = open(AKDB / "regions.xml", encoding="utf-8").read()
    cols = set()
    for rec in re.findall(r"<regions .*?</regions>", ak_regions, re.S):
        r_, g_, b_ = (int(re.search(rf"<{t}>(\d+)</{t}>", rec).group(1)) for t in "rgb"); cols.add((r_, g_, b_))
    def new_colour():
        while True:
            c = tuple(rng.randrange(16, 240) for _ in range(3))
            if all(sum(abs(a - b) for a, b in zip(c, o)) > 24 for o in cols): cols.add(c); return c
    # climate at each town from map.hex
    mh = HERE / "hex" / "map.hex"; src = mh.read_bytes(); P, w, h = C.locate_dims(src)
    f = unpack(np.frombuffer(src, np.uint8, 16 * w * h, P + 8).reshape(h, w, 16)); climates = hexmap.load(str(mh))["lists"]["climates"]

    regions = []            # dicts: key, province, capital?, name, colour, climate, resource template, flavour
    for key, p in prov.items():
        onscreen, flavour, res, capname = info6(p) if "names" in p else INFO[key]
        if "owners" in p:                                     # x15
            for j, rk in enumerate(p["regions"]):
                c, r = p["towns"][rk]; cl = climates[f["climate"][r, c]] if f["climate"][r, c] >= 0 else "temperate"
                cap = rk == p.get("capital")
                regions.append(dict(key=rk, province=p["province"], prov_name=onscreen, cap=cap, climate=cl,
                                    name=p["names"][rk], res=None if cap else res[j][0], flavour=flavour, owner=p["owners"].get(rk),
                                    colour=new_colour(), layout=LAYOUTS[len(regions) % 3]))
            continue
        for j, rk in enumerate(p["regions"]):
            c, r = p["towns"][rk]; cl = climates[f["climate"][r, c]] if f["climate"][r, c] >= 0 else "temperate"
            att = p.get("attach", False); jj = j + 1 if att else j        # attached region: a resource, no capital
            regions.append(dict(key=rk, province=p["province"], prov_name=onscreen, cap=jj == 0, climate=cl,
                                name=capname if jj == 0 else res[jj - 1][1], res=None if jj == 0 else res[jj - 1][0],
                                flavour=flavour, colour=new_colour(), layout=LAYOUTS[len(regions) % 3]))
    ids = {(r["key"], c): (new_id(), new_id()) for r in regions for c in CAMPAIGNS}   # (region id, settlement id)

    # ---- pack TSVs ----
    n = {}
    n["regions"] = append_tsv("db/regions_tables/ironic_added_regions.tsv",
                              [{"key": r["key"], "unnamed colour group_1": "%02X%02X%02X" % r["colour"]} for r in regions])
    newprov = {k: p for k, p in prov.items() if not p.get("attach")}        # attached regions join an existing province
    if X15:                                                   # x15: every new province of the export (capital may be an existing region)
        newprov = {np_["key"]: dict(province=np_["key"], label=np_["label"], names={}, owners={}, regions=[], zhou=np_.get("zhou"))
                   for np_ in X15["new_provinces"]}
    n["provinces"] = append_tsv("db/provinces_tables/ironic_added_regions.tsv", [{"key": p["province"]} for p in newprov.values()])
    n["campaign_map_regions"] = append_tsv("db/campaign_map_regions_tables/ironic_added_regions.tsv",
                                           [{"campaign_map": "3k_dlc07_main_map", "region": r["key"]} for r in regions])
    n["campaign_map_settlements"] = append_tsv("db/campaign_map_settlements_tables/ironic_added_regions.tsv",
        [{"settlement_id": f"settlement:{r['key']}", "climate_type": r["climate"], "citybar_height_offset": 0} for r in regions])
    n["layouts"] = append_tsv("db/campaign_settlement_display_settlement_layouts_tables/ironic_added_regions.tsv",
        [{"settlement": f"settlement:{r['key']}", "layout": r["layout"]} for r in regions if r["cap"]])
    n["rotations"] = append_tsv("db/campaign_settlement_display_settlement_rotations_tables/ironic_added_regions.tsv",
        [{"settlement": f"settlement:{r['key']}", "rotation": "0.0000"} for r in regions])
    for camp, fn in CAMPAIGNS.items():
        spr, sps, slt, pool, rel = [], [], [], [], []
        for r in regions:
            rid, sid = ids[(r["key"], camp)]
            spr.append(dict(region=r["key"], campaign=camp, id=rid, owning_faction=(r.get("owner") or "") if camp in OWNER_CAMPAIGNS else "", faction_capital="false",
                            base_population=100000, base_max_population=500000, population=100000, base_gdp=0, town_wealth=0,
                            rebel_faction="3k_main_faction_yellow_turban_anding", cultural_originator="3k_main_chinese",
                            settler_rebellions_enabled="false", capture_prestige=0, alternative_rebel_faction="3k_main_faction_rebels",
                            development_points=5, base_fertility=0, slot_cap=9 if r["cap"] else 2, initial_faction_support_value=100))
            sps.append({"settlement_id": f"settlement:{r['key']}", "region": rid, "wealth": 3, "id": sid,
                        "primary_building": "3k_city_0" if r["cap"] else r["res"] + "_1", "startpos_slave_points": 0, "razed": "false"})
            if r["cap"]:
                slt += [dict(campaign=camp, id=new_id(), region=r["key"], slot_template="3k_city", slot_type="primary"),
                        dict(campaign=camp, id=new_id(), region=r["key"], slot_template="3k_districts", slot_type="secondary")]
            else:
                slt += [dict(campaign=camp, id=new_id(), region=r["key"], slot_template=r["res"], slot_type="primary"),
                        dict(campaign=camp, id=new_id(), region=r["key"], slot_template=r["flavour"], slot_type="secondary")]
            pool.append({"pooled_resource": "3k_main_pooled_resource_population", "region": rid, "amount": 15 if r["cap"] else 12})
            rel.append({"region": rid, "religion": "3k_main_taoist", "percentage": "100.0000"})
        n[f"startpos {camp}"] = sum([
            append_tsv(f"db/start_pos_regions_tables/{fn}.tsv", spr), append_tsv(f"db/start_pos_settlements_tables/{fn}.tsv", sps),
            append_tsv(f"db/start_pos_region_slot_templates_tables/{fn}.tsv", slt),
            append_tsv(f"db/start_pos_region_pooled_resources_tables/{fn}.tsv", pool),
            append_tsv(f"db/start_pos_region_religions_tables/{fn}.tsv", rel)])
    # pack junctions (a full data__ override of vanilla's): without these the new regions have no province and the
    # startpos build crashes creating the WORLD (null province pointer; round 5, 2026-09-30)
    n["region_to_province_junctions"] = append_tsv("db/region_to_province_junctions_tables/data__.tsv",
        [{"province": r["province"], "region": r["key"], "is_capital": "true" if r["cap"] else "false"} for r in regions])
    loc_r = []
    for r in regions:
        loc_r += [{"key": f"regions_onscreen_{r['key']}", "text": r["name"], "tooltip": "false"},
                  {"key": f"regions_battle_name_{r['key']}", "text": r["name"], "tooltip": "false"},
                  {"key": f"regions_name_with_icon_path_{r['key']}", "text": "/ui/skins/default/placeholder.png", "tooltip": "false"}]
    n["regions.loc"] = append_tsv("text/db/regions.loc.tsv", loc_r)
    n["provinces.loc"] = append_tsv("text/db/provinces.loc.tsv",
                                    [{"key": f"provinces_onscreen_{p['province']}", "text": p["label"] if X15 else (info6(p) if "names" in p else INFO[k])[0], "tooltip": "false"} for k, p in newprov.items()])
    n["start_pos_regions.loc"] = append_tsv("text/db/start_pos_regions.loc.tsv",
        [{"key": f"start_pos_regions_long_description_{r['key']}{c}", "text": "PLACEHOLDER", "tooltip": "false"} for r in regions for c in CAMPAIGNS])
    n["start_pos_settlements.loc"] = append_tsv("text/db/start_pos_settlements.loc.tsv",
        [{"key": f"start_pos_settlements_onscreen_name_settlement:{r['key']}{ids[(r['key'], c)][0]}", "text": r["name"], "tooltip": "false"}
         for r in regions for c in CAMPAIGNS])
    # renames (user: a new region may take a name an old region uses - the old region gets a new name)
    placed_names = {r["name"] for r in regions}
    for new_name, (old_key, old_new_name) in RENAMES.items():
        if new_name not in placed_names: continue
        lp = OUT / "text" / "db" / "regions.loc.tsv"; lines = open(lp, encoding="utf-8", newline="").read().split(LF)
        hit = 0
        for i_, line in enumerate(lines):
            a_ = line.split(TAB)
            if a_[0] in (f"regions_onscreen_{old_key}", f"regions_battle_name_{old_key}"):
                a_[1] = old_new_name; lines[i_] = TAB.join(a_); hit += 1
        if not hit:
            lines.insert(2, TAB.join([f"regions_onscreen_{old_key}", old_new_name, "false"]))
        open(lp, "w", encoding="utf-8", newline="").write(LF.join(lines)); n[f"rename {old_key}"] = old_new_name
    if not os.environ.get("TERRAIN_ONLY"): pack_r7(n)
    print("pack TSVs ->", OUT); [print(f"  {k:32s} +{v}") for k, v in n.items()]

    # ---- AK XMLs ----
    m = {}
    m["regions"] = ak_append("regions", {"cap": lambda s: 'record_key="ironic_region_wuyuan_capital"' in s},
        lambda t: [clone(t["cap"], r["key"], key=r["key"], onscreen=r["name"], battle_name=r["name"],
                         r=r["colour"][0], g=r["colour"][1], b=r["colour"][2]) for r in regions])
    m["provinces"] = ak_append("provinces", {"p": lambda s: 'record_key="3k_ironic_province_wuyuan"' in s},
        lambda t: [clone(t["p"], p["province"], key=p["province"], onscreen=p["label"] if X15 else (info6(p) if "names" in p else INFO[k])[0]) for k, p in newprov.items()])
    m["region_to_province_junctions"] = ak_append("region_to_province_junctions",
        {"j": lambda s: 'record_key="ironic_region_wuyuan_capital3k_ironic_province_wuyuan"' in s},
        lambda t: [clone(t["j"], r["key"] + r["province"], region=r["key"], province=r["province"], is_capital=int(r["cap"])) for r in regions])
    m["campaign_map_regions"] = ak_append("campaign_map_regions", {"c": lambda s: "<region>ironic_region_wuyuan_capital<" in s},
        lambda t: [clone(t["c"], "3k_dlc07_main_map" + r["key"], region=r["key"]) for r in regions])
    m["campaign_map_settlements"] = ak_append("campaign_map_settlements",
        {"s": lambda s: 'record_key="settlement:ironic_region_wuyuan_capital"' in s},
        lambda t: [clone(t["s"], f"settlement:{r['key']}", settlement_id=f"settlement:{r['key']}", climate_type=r["climate"]) for r in regions])
    def spr_make(t):
        out = []
        for camp in CAMPAIGNS:
            for r in regions:
                rid, _ = ids[(r["key"], camp)]
                rec = clone(t[camp + ("c" if r["cap"] else "r")], r["key"] + camp, region=r["key"], campaign=camp, id=rid,
                            faction_capital=0, slot_cap=9 if r["cap"] else 2)
                own_ = (r.get("owner") or "") if camp in OWNER_CAMPAIGNS else ""
                rec = re.sub(r"<owning_faction>[^<]*</owning_faction>", f"<owning_faction>{own_}</owning_faction>", rec)
                out.append(rec)
        return out
    pick = {}
    for camp in CAMPAIGNS:
        pick[camp + "c"] = lambda s, camp=camp: 'record_key="ironic_region_xiping_capital' + camp + '"' in s
        pick[camp + "r"] = lambda s, camp=camp: 'record_key="ironic_region_xiping_resource_1' + camp + '"' in s
    m["start_pos_regions"] = ak_append("start_pos_regions", pick, spr_make)
    def sps_make(t):
        out = []
        for camp in CAMPAIGNS:
            for r in regions:
                rid, sid = ids[(r["key"], camp)]
                rec = clone(t[camp + ("c" if r["cap"] else "r")], f"settlement:{r['key']}{rid}", settlement_id=f"settlement:{r['key']}",
                            region=rid, id=sid, primary_building="3k_city_0" if r["cap"] else r["res"] + "_1", onscreen_name=r["name"])
                for b in range(1, 6): rec = set_tag(rec, f"building{b}", "")
                out.append(set_tag(rec, "port_building", ""))
        return out
    region_ids = {}
    for camp in CAMPAIGNS:
        txt = open(AKDB / "start_pos_regions.xml", encoding="utf-8").read()
        for kind, rk in (("c", "ironic_region_xiping_capital"), ("r", "ironic_region_xiping_resource_1")):
            rec = re.search(rf'<start_pos_regions [^>]*record_key="{rk}{camp}".*?</start_pos_regions>', txt, re.S).group(0)
            region_ids[camp + kind] = re.search(r"<id>(\d+)</id>", rec).group(1)
    pick_s = {k: (lambda s, v=v: f"<region>{v}</region>" in s) for k, v in region_ids.items()}
    m["start_pos_settlements"] = ak_append("start_pos_settlements", pick_s, sps_make)
    tsl = {}
    for camp in CAMPAIGNS:
        tsl[camp] = lambda s, camp=camp: f"<campaign>{camp}</campaign>" in s and "<region>ironic_region_xiping_capital<" in s and "<slot_type>primary<" in s
    def slt_make(t):
        out = []
        for camp in CAMPAIGNS:
            for r in regions:
                pairs = [("3k_city", "primary"), ("3k_districts", "secondary")] if r["cap"] else [(r["res"], "primary"), (r["flavour"], "secondary")]
                for tmpl, typ in pairs:
                    i = new_id()
                    out.append(clone(t[camp], f"{i}{camp}{r['key']}{typ}{tmpl}", campaign=camp, id=i, region=r["key"], slot_template=tmpl, slot_type=typ))
        return out
    m["start_pos_region_slot_templates"] = ak_append("start_pos_region_slot_templates", tsl, slt_make)
    if not os.environ.get("TERRAIN_ONLY"): ak_r7(m)
    print("AK XMLs ->", AKOUT); [print(f"  {k:32s} +{v}") for k, v in m.items()]
    json.dump({f"{k}|{c}": v for (k, c), v in ids.items()}, open(HERE / "regions_ids.json", "w"), indent=0)
    import retemplate_x15; retemplate_x15.main()             # regions_new.json "retemplate": city <-> resource for existing regions


if __name__ == "__main__":
    main()
