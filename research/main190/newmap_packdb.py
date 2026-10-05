#!/usr/bin/env python3
"""Pack-side DB for the new map 3k_190e_expanded_map (see newmap_install.py for the AK side).

Writes TSVs to newmap_db/out/ (added to the copy pack with rpfm_cli -t schema):
  campaign_map_playable_areas_tables/data__   old rows back to 190E's maxx 595.1; new row (AK index) for NEW
  campaigns_tables/data_3k_main_campaign_map  map_name / display_location -> NEW
  campaign_map_regions_tables/ironic_190e_expanded_map   every header region of the new map.hex, campaign_map NEW
  campaign_camera_map_bounds_tables/ironic_edited_map    3k_main_campaign_map max_y for the taller map
Inputs: db_out playable TSV, newmap_db/db (extracted from the pack), newmap.json, hex/map_newname.hex.
"""
import json, os, sys
from pathlib import Path
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
import hexmap

NEW, CAMP = "3k_190e_expanded_map", "3k_main_campaign_map"
OLD_MAXX = "595.1000"
IN, OUT = HERE / "newmap_db" / "db", HERE / "newmap_db" / "out" / "db"
nm = json.load(open(HERE / "newmap.json"))


def read(p):
    lines = open(p, encoding="utf-8").read().splitlines()
    return lines[0].split("\t"), lines[1], [l.split("\t") for l in lines[2:] if l.strip()]


def write(table, name, cols, rows, version):
    d = OUT / table; d.mkdir(parents=True, exist_ok=True)
    tag = f"#{table};{version};db/{table}/{name}" + "\t" * (len(cols) - 1)
    open(d / f"{name}.tsv", "w", encoding="utf-8", newline="\n").write(
        "\n".join(["\t".join(cols), tag] + ["\t".join(r) for r in rows]) + "\n")
    print(f"{table}/{name}: {len(rows)} rows")


def main():
    # playable areas
    cols, tag, rows = read(HERE / "newmap_db" / "src" / "campaign_map_playable_areas_data__.tsv")   # (regions_db.py rebuilds db_out)
    ver = tag.split(";")[1]; c = {k: i for i, k in enumerate(cols)}
    rows = [r for r in rows if r[c["mapname"]] != NEW]
    for r in rows: r[c["maxx"]] = OLD_MAXX
    src = next(r for r in rows if r[c["index"]] == "1799249611")
    new = list(src); new[c["index"]] = str(nm["playable_index"]); new[c["mapname"]] = NEW
    new[c["campaign_key"]] = CAMP; new[c["maxx"]] = f"{nm['maxx']:.4f}"
    write("campaign_map_playable_areas_tables", "data__", cols, rows + [new], ver)
    # campaigns
    cols, tag, rows = read(IN / "campaigns_tables" / "data_3k_main_campaign_map.tsv")
    c = {k: i for i, k in enumerate(cols)}
    for r in rows:
        if r[c["campaign_name"]] == CAMP: r[c["map_name"]] = NEW; r[c["display_location"]] = NEW
    write("campaigns_tables", "data_3k_main_campaign_map", cols, rows, tag.split(";")[1])
    # campaign map regions
    cols, tag, _ = read(IN / "campaign_map_regions_tables" / "ironic_added_regions.tsv")
    lists = hexmap.load(str(HERE / "hex" / "map_newname.hex"))["lists"]
    regs = list(dict.fromkeys(lists["land_regions"] + lists["sea_regions"]))
    write("campaign_map_regions_tables", "ironic_190e_expanded_map", cols, [[NEW, r] for r in regs], tag.split(";")[1])
    # camera bounds for 3k_main_campaign_map on the new map
    cols, tag, rows = read(IN / "campaign_camera_map_bounds_tables" / "ironic_edited_map.tsv")
    c = {k: i for i, k in enumerate(cols)}
    for r in rows:
        if r[c["campaign"]] == CAMP:
            # Guandu's (working) convention: the playable world extents inset by 20 on every side
            r[c["max_x"]] = f"{nm['maxx'] - 20:.4f}"; r[c["max_y"]] = f"{nm['maxy'] - 20:.4f}"
            r[c["min_x"]] = "20.0000"; r[c["min_y"]] = "20.0000"
    write("campaign_camera_map_bounds_tables", "ironic_edited_map", cols, rows, tag.split(";")[1])


if __name__ == "__main__":
    main()
