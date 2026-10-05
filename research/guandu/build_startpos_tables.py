#!/usr/bin/env python3
"""Pack-ready DB TSVs for the minimal 3k_guandu_start_pos (what RPFM's startpos builder reads from the mod pack).

Rows come from the 3k_guandu_start_pos records ak_db_add_startpos.py wrote into the AK raw_data/db XMLs; columns,
table versions and value formats follow the user's working new_startpos_dlc08.pack (research/guandu/example_newcampaign):
booleans as true/false, float columns with 4 decimals. Output: research/guandu/startpos_tables/db/<table>_tables/guandu.tsv
"""
import os, re, glob
from ak_db_add_guandu import DB, records

HERE = os.path.dirname(os.path.abspath(__file__))
EXAMPLE = os.path.join(HERE, "example_newcampaign", "db")
OUT = os.path.join(HERE, "startpos_tables", "db")
CAMP, MAP = "3k_guandu_start_pos", "3k_guandu_map"
g = lambda r, f: (re.search(r"<%s(?: [^>]*)?>([^<]*)</%s>" % (f, f), r) or [None, None])[1]   # localised fields carry attributes

# column formats seen in the example pack (and the RPFM schema): flags and floats
BOOL = {"campaigns": {"FIXME", "exportable", "is_tutorial", "available_for_mp"},
        "start_pos_factions": {"playable", "is_major", "can_ever_convert_religion"},
        "start_pos_regions": {"faction_capital", "settler_rebellions_enabled"},
        "start_pos_settlements": {"razed"},
        "start_pos_characters": {"immortal", "is_in_generals_pool", "progenitor", "start_on_map",
                                 "undercover_character_enabler", "starting_force_retreated_this_turn"}}
FLOAT = {"start_pos_region_religions": {"percentage"},
         "start_pos_characters": {"startx", "starty", "start_facing_angle"}}


def header(table):
    f = sorted(glob.glob(os.path.join(EXAMPLE, table + "_tables", "*.tsv")))[0]
    cols, meta = open(f, encoding="utf-8").read().split("\n")[:2]
    return cols.split("\t"), meta.split("\t")[0].split(";")[1]


def rows_for(table):
    s = open(os.path.join(DB, table + ".xml"), encoding="utf-8", newline="").read()
    R = [m.group(0) for m in records(s, table)]
    fac = {g(r, "ID") for r in (records_for("start_pos_factions"))}
    reg = {g(r, "id") for r in records_for("start_pos_regions")}
    if table == "campaigns": return [r for r in R if 'record_key="%s"' % CAMP in r]
    if "<campaign>" in (R[0] if R else ""): return [r for r in R if g(r, "campaign") == CAMP]
    if table in ("start_pos_settlements", "start_pos_region_religions", "start_pos_region_pooled_resources"):
        return [r for r in R if g(r, "region") in reg]
    if table == "start_pos_characters": return [r for r in R if g(r, "faction") in fac]
    if table == "start_pos_character_retinue_unit_modifiers":
        ch = {g(r, "ID") for r in rows_for("start_pos_characters")}
        return [r for r in R if g(r, "character") in ch]
    if table == "start_pos_technologies": return [r for r in R if g(r, "faction") in fac]
    raise ValueError(table)


_cache = {}
def records_for(table):
    if table not in _cache:
        s = open(os.path.join(DB, table + ".xml"), encoding="utf-8", newline="").read()
        _cache[table] = [m.group(0) for m in records(s, table) if g(m.group(0), "campaign") == CAMP]
    return _cache[table]


def fmt(table, col, v):
    v = "" if v is None else v
    if col in BOOL.get(table, ()): return "true" if v in ("1", "true") else "false"
    if col in FLOAT.get(table, ()) and v != "": return "%.4f" % float(v)
    return v


def main():
    tables = ["campaigns", "start_pos_calendars", "start_pos_factions", "start_pos_regions", "start_pos_settlements",
              "start_pos_region_slot_templates", "start_pos_region_religions", "start_pos_region_pooled_resources",
              "start_pos_characters", "start_pos_character_retinue_unit_modifiers", "start_pos_technologies"]
    for t in tables:
        cols, ver = header(t)
        rows = rows_for(t)
        lines = ["\t".join(cols), "\t".join(["#%s_tables;%s;db/%s_tables/guandu" % (t, ver, t)] + [""] * (len(cols) - 1))]
        for r in rows:
            vals = []
            for c in cols:
                if t == "campaigns" and c == "FIXME": vals.append("false"); continue
                vals.append(fmt(t, c, g(r, c)))
            lines.append("\t".join(vals))
        if t == "start_pos_region_pooled_resources":
            # every region needs its population pooled resource (dlc08 has one per region); a missing one crashes the build
            have = {g(r, "region") for r in rows}
            for r in records_for("start_pos_regions"):
                if g(r, "id") not in have:
                    lines.append("	".join({"pooled_resource": "3k_main_pooled_resource_population", "region": g(r, "id"),
                                            "amount": "120" if g(r, "region").endswith("_capital") else "12"}[c] for c in cols))
        if t == "start_pos_character_retinue_unit_modifiers": lines = lines[:2]   # empty, as in dlc08
        os.makedirs(os.path.join(OUT, t + "_tables"), exist_ok=True)
        open(os.path.join(OUT, t + "_tables", "guandu.tsv"), "w", encoding="utf-8", newline="").write("\n".join(lines) + "\n")
        print(f"{t:45s} v{ver:>3s} {len(rows):4d} rows")


if __name__ == "__main__":
    main()
