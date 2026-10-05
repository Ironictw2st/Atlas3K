#!/usr/bin/env python3
"""Frontend + loc for 3k_guandu_start_pos, modelled on the user's working new_startpos_dlc08.pack.

Writes research/guandu/frontend_pack/:
  db/frontend_faction_to_frontend_faction_leaders_tables/guandu.tsv   Cao Cao selectable (default leader)
  db/faction_to_faction_groups_junctions_tables/guandu.tsv            Cao Cao -> 3k_Imperial_governors
  db/campaign_camera_map_bounds_tables/guandu.tsv                     camera bounds for the 730x606 map
  db/campaign_map_roads_tables/guandu.tsv                             road levels 1-3 for the campaign
  text/guandu.loc.tsv                                                 campaign name/description/bullets + settlement names
  ui/frontend ui/new_campaign.twui.xml                                campaign-select screen with a 3k_guandu_start_pos button

The twui is the user's dlc08 copy with the dlc08 button turned into the Guandu one: element names and id become
3k_guandu_start_pos, every GUID defined inside the button's component block (button + 5 children) and hierarchy
entry gets a fresh one (outside references such as the screen root are left alone), timeline offset -> 700.
"""
import os, re, random
from build_startpos_tables import records_for, g
from crop_scale_terrain import NWW, NWH

HERE = os.path.dirname(os.path.abspath(__file__))
EX = os.path.join(HERE, "example_newcampaign")
OUT = os.path.join(HERE, "frontend_pack")
CAMP = "3k_guandu_start_pos"


def tsv(path, table, ver, cols, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    head = ["\t".join(cols), "\t".join(["#%s;%s;%s" % (table, ver, path.split("frontend_pack" + os.sep)[1].replace(os.sep, "/")[:-4])] + [""] * (len(cols) - 1))]
    open(path, "w", encoding="utf-8", newline="").write("\n".join(head + ["\t".join(r) for r in rows]) + "\n")


def db_tables():
    d = os.path.join(OUT, "db")
    tsv(os.path.join(d, "frontend_faction_to_frontend_faction_leaders_tables", "guandu.tsv"),
        "frontend_faction_to_frontend_faction_leaders_tables", 0,
        ["campaign_key", "frontend_faction", "frontend_faction_leader", "is_default"],
        [[CAMP, "3k_main_faction_cao_cao", "3k_main_political_party_cao_cao_ruler", "true"]])
    tsv(os.path.join(d, "faction_to_faction_groups_junctions_tables", "guandu.tsv"),
        "faction_to_faction_groups_junctions_tables", 5, ["faction_key", "optional_campaign_key", "faction_group_key"],
        [["3k_main_faction_cao_cao", CAMP, "3k_Imperial_governors"]])
    tsv(os.path.join(d, "campaign_camera_map_bounds_tables", "guandu.tsv"),
        "campaign_camera_map_bounds_tables", 0, ["campaign", "max_x", "max_y", "min_x", "min_y"],
        [[CAMP, "%.4f" % (NWW - 20), "%.4f" % (NWH - 20), "20.0000", "20.0000"]])
    tsv(os.path.join(d, "campaign_map_roads_tables", "guandu.tsv"),
        "campaign_map_roads_tables", 0,
        ["key", "campaign", "movement_cost", "threshold", "turns_required_to_upgrade_to", "turns_required_to_downgrade_from"],
        [["3k_guandu_road_level_%d" % i, CAMP, c, t, "1", "1"] for i, c, t in ((1, "100", "0.0000"), (2, "75", "10.0000"), (3, "50", "40.0000"))])


def loc():
    rows = [["campaigns_onscreen_name_" + CAMP, "Battle of Guandu", "false"],
            ["campaigns_description_" + CAMP, "Cao Cao stands alone on the plains of the north.", "false"],
            ["campaigns_bullet_list_" + CAMP, "A zoomed-in map of northern China, from Hanzhong to the sea and the Yangtze to the Great Wall.", "false"]]
    # settlement names: start_pos_settlements_onscreen_name_<settlement_id><id>, names from the AK records
    from ak_db_add_guandu import DB, records
    s = open(os.path.join(DB, "start_pos_settlements.xml"), encoding="utf-8", newline="").read()
    regs = {g(r, "id") for r in records_for("start_pos_regions")}
    for m in records(s, "start_pos_settlements"):
        r = m.group(0)
        if g(r, "region") in regs:
            rows.append(["start_pos_settlements_onscreen_name_%s%s" % (g(r, "settlement_id"), g(r, "id")), g(r, "onscreen_name") or "", "false"])
    path = os.path.join(OUT, "text", "guandu.loc.tsv"); os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8", newline="").write("\n".join(["key\ttext\ttooltip", "#Loc;1;text/guandu.loc\t\t"] + ["\t".join(r) for r in rows]) + "\n")
    return len(rows)


def twui():
    CR, LF, TAB = chr(13), chr(10), chr(9)
    raw = open(os.path.join(EX, "ui", "frontend ui", "new_campaign.twui.xml"), encoding="utf-8", newline="").read()
    # the user's copy mixes CRLF (vanilla lines) and LF (hand-added dlc08 lines, one space-indented):
    # work on LF lines, fix that indentation to tabs, write CRLF throughout (the TWUI convention)
    lines = [l.rstrip(CR) for l in raw.split(LF)]
    for i, l in enumerate(lines):
        if l.strip().startswith("<_3k_dlc08_start_pos") and not l.startswith(TAB):
            lines[i] = TAB * (6 if "this=" in l else 2) + l.strip()
    eol = LF
    src = eol.join(lines)
    # component block: from the "<_3k_dlc08_start_pos" line to the end of the lock_icon component after it
    start = next(i for i, l in enumerate(lines) if l.strip() == "<_3k_dlc08_start_pos")
    lock_guid = re.search(r'<lock_icon this="([^"]+)"', src[src.index("<_3k_dlc08_start_pos this="):]).group(1)
    lock_def = next(i for i in range(start, len(lines)) if 'this="%s"' % lock_guid in lines[i])
    end = next(i for i in range(lock_def, len(lines)) if lines[i].strip() == "</lock_icon>")
    block = eol.join(lines[start:end + 1])
    hs = src.index("<_3k_dlc08_start_pos this=")
    he = src.index("</_3k_dlc08_start_pos>", hs) + len("</_3k_dlc08_start_pos>")
    hier = src[hs:he]
    defined = set(re.findall(r'(?:this|uniqueguid)="([0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{16})"', block + hier))
    used = set(re.findall(r"[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{16}", src))
    rng = random.Random(CAMP)
    def newg():
        while True:
            h = "%032X" % rng.getrandbits(128); v = "%s-%s-%s-%s" % (h[:8], h[8:12], h[12:16], h[16:])
            if v not in used: used.add(v); return v
    gmap = {o: newg() for o in sorted(defined)}
    def conv(t):
        for o, n in gmap.items(): t = t.replace(o, n)
        return t.replace("_3k_dlc08_start_pos", "_3k_guandu_start_pos").replace('id="3k_dlc08_start_pos"', 'id="%s"' % CAMP)
    nblock = conv(block).replace('offset="600.00,-11.00"', 'offset="700.00,-11.00"', 1)
    nhier = conv(hier)
    out = src[:hs] + nhier + src[he:]
    out = out.replace(block, nblock)
    assert "3k_dlc08_start_pos" not in out and out.count('id="%s"' % CAMP) == 1
    path = os.path.join(OUT, "ui", "frontend ui", "new_campaign.twui.xml"); os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8", newline="").write(out.replace(LF, CR + LF))
    import xml.dom.minidom; xml.dom.minidom.parseString(out.encode("utf-8"))
    return len(gmap)


if __name__ == "__main__":
    db_tables()
    print("loc rows:", loc())
    print("twui: guandu button with", twui(), "fresh GUIDs, xml ok")
