#!/usr/bin/env python3
"""The rest of a startpos pack, mirroring the user's working new_startpos_dlc08.pack table for table.

Adds to research/guandu/startpos_tables/db/:
  start_pos_factions_tables/guandu.tsv           Cao Cao (dlc08's major-faction values) + 3k_main_faction_cao_separatists + rebels
  start_pos_factions_tables/guandu_regional.tsv  one emergent regional faction per province on the Guandu map (dlc08 rows)
  province_to_emergent_faction_junctions         province -> that faction
  start_pos_diplomacy_deals / deal_orderings / simple_deals   Cao Cao -> each regional faction: hidden
                                                 "access to Han empire" treaty (as dlc08), keys prefixed 3k_guandu_
  start_pos_world_power_tokens                   emperor, no holder (as dlc08)
  the 12 tables dlc08 ships empty (header only), and db/victory_objectives.txt (dlc08's copy)
"""
import os, re, random, shutil, glob

HERE = os.path.dirname(os.path.abspath(__file__))
EX = os.path.join(HERE, "example_newcampaign", "db")
OUT = os.path.join(HERE, "startpos_tables", "db")
AKDB = r"C:/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/assembly_kit/raw_data/db"
CAMP, SRC = "3k_guandu_start_pos", "3k_dlc08_start_pos"
EMPTY = ["start_pos_captain_retinue_unit_modifiers", "start_pos_character_employment_history_entries",
         "start_pos_character_relationship_triggers", "start_pos_character_to_settlements",
         "start_pos_diplomacy_simple_deal_alliance_oath_parameters", "start_pos_diplomacy_simple_deal_alliance_parameters",
         "start_pos_family_relationships", "start_pos_historical_characters_past_experiences",
         "start_pos_non_commanding_captains", "start_pos_non_commanding_generals", "start_pos_past_events",
         "start_pos_victory_conditions"]


def read(table, name=None):
    f = sorted(glob.glob(os.path.join(EX, table + "_tables", (name or "*") + ".tsv")))[0]
    lines = open(f, encoding="utf-8").read().rstrip("\n").split("\n")
    cols = lines[0].split("\t"); ver = lines[1].split("\t")[0].split(";")[1]
    return cols, ver, [dict(zip(cols, l.split("\t"))) for l in lines[2:] if l.strip()]


def write(table, cols, ver, rows, name="guandu"):
    d = os.path.join(OUT, table + "_tables"); os.makedirs(d, exist_ok=True)
    meta = ["#%s_tables;%s;db/%s_tables/%s" % (table, ver, table, name)] + [""] * (len(cols) - 1)
    body = ["\t".join(cols), "\t".join(meta)] + ["\t".join(r.get(c, "") for c in cols) for r in rows]
    open(os.path.join(d, name + ".tsv"), "w", encoding="utf-8", newline="").write("\n".join(body) + "\n")
    return len(rows)


def main():
    rng = random.Random(CAMP + "extra")
    used = set()
    def new_id():
        while True:
            v = str(rng.randrange(10**9, 2**31 - 1))
            if v not in used: used.add(v); return v

    # our current factions (Cao Cao id, rebels) from build_startpos_tables output
    cur = os.path.join(OUT, "start_pos_factions_tables", "guandu.tsv")
    lines = open(cur, encoding="utf-8").read().rstrip("\n").split("\n"); fcols = lines[0].split("\t")
    ours = [dict(zip(fcols, l.split("\t"))) for l in lines[2:]]
    cao_id = next(r["ID"] for r in ours if r["faction"] == "3k_main_faction_cao_cao")
    used.update(r["ID"] for r in ours)

    # Cao Cao + separatists as in dlc08
    _, fver, ex_main = read("start_pos_factions", "new_cam")
    fac_rows = []
    for r in ex_main:
        if r["faction"] in ("3k_main_faction_cao_cao", "3k_main_faction_cao_separatists"):
            r = dict(r, campaign=CAMP, ID=cao_id if r["faction"] == "3k_main_faction_cao_cao" else new_id())
            fac_rows.append(r)
    # dlc08 ships no rebel / yellow turban factions (its regions still name them as rebels): landless factions
    # with no characters are left out, as there
    for i, r in enumerate(fac_rows):
        r["starting_order"] = str(i + 1)
        if r["faction"] != "3k_main_faction_cao_cao": r["playable"] = "false"     # Cao Cao is the only playable faction

    # provinces on our map
    regs = {l.split("\t")[0] for l in open(os.path.join(OUT, "start_pos_regions_tables", "guandu.tsv"), encoding="utf-8").read().split("\n")[2:] if l}
    xml = open(os.path.join(AKDB, "region_to_province_junctions.xml"), encoding="utf-8").read()
    provinces = {p for r, p in ((re.search(r"<region>([^<]*)<", x).group(1), re.search(r"<province>([^<]*)<", x).group(1))
                                for x in re.findall(r"<region_to_province_junctions .*?</region_to_province_junctions>", xml, re.S)) if r in regs}

    # regional (emergent) factions for those provinces, from dlc08
    _, ever, emergent = read("province_to_emergent_faction_junctions")
    pe = [e for e in emergent if e["province"] in provinces]
    _, rver, regional = read("start_pos_factions", "cam_regional")
    by_faction = {r["faction"]: r for r in regional}
    reg_rows, rid = [], {}
    for e in pe:
        f = e["faction_record"]
        if f in by_faction and f not in rid:
            rid[f] = new_id()
            reg_rows.append(dict(by_faction[f], ID=rid[f], campaign=CAMP, starting_order=str(len(fac_rows) + len(reg_rows) + 1)))
    pe = [dict(e, campaign=CAMP) for e in pe if e["faction_record"] in rid]

    # diplomacy: Cao Cao -> regional faction, hidden access-to-Han-empire treaty
    deals, orders, simple = [], [], []
    for i, f in enumerate(rid):
        key = "3k_guandu_deal_start_pos_access_to_han_empire__" + re.sub(r"^3k_(main|dlc\d+)_faction_", "", f)
        deals.append({"id": key, "negotiation_type": "hidden_treaties"})
        orders.append({"order": str(50 + i), "deal": key})
        simple.append({"id": key, "proposer": cao_id, "recipient": rid[f],
                       "component": "treaty_components_start_pos_access_to_han_empire",
                       "established_how_many_turns_before_start_of_game": "0"})

    print("start_pos_factions (main)", write("start_pos_factions", fcols, fver, fac_rows))
    print("start_pos_factions (regional)", write("start_pos_factions", fcols, rver, reg_rows, "guandu_regional"))
    c, v, _ = read("province_to_emergent_faction_junctions"); print("province_to_emergent", write("province_to_emergent_faction_junctions", c, v, pe))
    c, v, _ = read("start_pos_diplomacy_deals"); print("deals", write("start_pos_diplomacy_deals", c, v, deals))
    c, v, _ = read("start_pos_diplomacy_deal_orderings"); print("orderings", write("start_pos_diplomacy_deal_orderings", c, v, orders))
    c, v, _ = read("start_pos_diplomacy_simple_deals"); print("simple deals", write("start_pos_diplomacy_simple_deals", c, v, simple))
    c, v, _ = read("start_pos_world_power_tokens")
    print("world power tokens", write("start_pos_world_power_tokens", c, v, [{"id": new_id(), "start_pos_faction": "", "world_power_token": "emperor", "campaign": CAMP}]))
    for t in EMPTY:
        c, v, _ = read(t); write(t, c, v, [])
    print("empty tables:", len(EMPTY))
    shutil.copy2(os.path.join(EX, "victory_objectives.txt"), os.path.join(OUT, "victory_objectives.txt"))
    print(f"provinces on map {len(provinces)}; with a regional faction {len(pe)}")


if __name__ == "__main__":
    main()
