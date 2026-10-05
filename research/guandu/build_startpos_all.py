#!/usr/bin/env python3
"""Run the whole startpos table chain in order. The steps depend on each other's IDs (ak_db_add_startpos gives new
record IDs each run), so never run one on its own:

 ak_db_add_guandu      campaign_maps / campaign_map_regions / playable_areas / campaigns in the AK XMLs (from map.hex)
 ak_db_add_startpos    3k_guandu_start_pos records in the AK XMLs
 build_startpos_tables AK records -> startpos_tables/db TSVs
 build_startpos_extra  dlc08-style factions, regional factions, diplomacy, tokens, empty tables (overwrites factions)
 build_frontend        frontend tables, loc (settlement names keyed by the new settlement IDs), twui
 campaign_map_regions  pack TSV of the AK campaign_map_regions rows for 3k_guandu_map
"""
import os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
AKDB = r"C:/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/assembly_kit/raw_data/db/"


def run(script):
    print("==", script)
    subprocess.run([sys.executable, os.path.join(HERE, script)], check=True, cwd=HERE)


def campaign_map_regions():
    s = open(AKDB + "campaign_map_regions.xml", encoding="utf-8").read()
    rows = [re.search(r"<region>([^<]*)<", r).group(1)
            for r in re.findall(r"<campaign_map_regions[ >].*?</campaign_map_regions>", s, re.S)
            if "<campaign_map>3k_guandu_map</campaign_map>" in r]
    d = os.path.join(HERE, "startpos_tables", "db", "campaign_map_regions_tables"); os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "guandu.tsv"), "w", encoding="utf-8", newline="").write("\n".join(
        ["campaign_map\tregion", "#campaign_map_regions_tables;0;db/campaign_map_regions_tables/guandu\t"]
        + ["3k_guandu_map\t" + r for r in rows]) + "\n")
    print("campaign_map_regions", len(rows))


def playable_area():
    """Pack campaign_map_playable_areas row, from the AK record (same index, which map_data.esf stores, and the same
    raster-world maxx that Terry and the game use for tile scale). Layout as the user's dlc08 pack (v10)."""
    s = open(AKDB + "campaign_map_playable_areas.xml", encoding="utf-8").read()
    r = next(x for x in re.findall(r"<campaign_map_playable_areas[ >].*?</campaign_map_playable_areas>", s, re.S)
             if "<mapname>3k_guandu_map</mapname>" in x)
    g = lambda f: re.search(rf"<{f}>([^<]*)</{f}>", r).group(1)
    cols = ["index", "sea_trade", "map_file", "overlay_file", "radar_file", "meaningful_id", "preview_width",
            "preview_height", "minx", "maxx", "mapname", "minimap_lookup_file", "is_available_in_custom_battle",
            "terrain_folder", "campaign_key", "frontend_image", "video", "campaign_overlay_lookup",
            "campaign_overlay_map", "game_mode", "dlc_key"]
    row = [g("index"), "false", "three_kingdoms_china_map.tga", "3k_main_lookup.tga", "3k_main_minimap.png",
           "main_rome_map", "750", "600", "0.0000", "%.4f" % float(g("maxx")), "3k_guandu_map",
           "3k_main_lookup_minimap.tga", "true", "terrain/battles/3k_main_map/", "3k_guandu_start_pos",
           "ui/skins/default/campaign_select_grand_campaign.png", "startup_movie_01", "3k_main_lookup.dds",
           "3K_overlay_map.dds", "romance", "TW_3K_MAIN"]
    d = os.path.join(HERE, "startpos_tables", "db", "campaign_map_playable_areas_tables"); os.makedirs(d, exist_ok=True)
    meta = ["#campaign_map_playable_areas_tables;10;db/campaign_map_playable_areas_tables/guandu"] + [""] * (len(cols) - 1)
    open(os.path.join(d, "guandu.tsv"), "w", encoding="utf-8", newline="").write(
        "\n".join(["\t".join(cols), "\t".join(meta), "\t".join(row)]) + "\n")
    print("campaign_map_playable_areas index", row[0], "maxx", row[9])


if __name__ == "__main__":
    for s in ("ak_db_add_guandu.py", "ak_db_add_startpos.py", "build_startpos_tables.py", "build_startpos_extra.py",
              "build_frontend.py"):
        run(s)
    campaign_map_regions()
    playable_area()
    run("mirror_empiredesign.py")
