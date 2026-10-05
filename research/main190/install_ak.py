#!/usr/bin/env python3
"""Install the reworked 190E map into assembly_kit_190E (backup first, insert-only for the DB).

 - raw_data/db and raw_data/EmpireDesignData (BOB's copy): the new-region records from ak_db/ are appended to each
   file separately (their start_pos_region_slot_templates copies differ); earlier copies of ours are removed first
 - campaign_map_playable_areas (all 7 rows): maxx/maxy = the new raster world (Guandu rule; vanilla maxx 595.1 =
   raster width); campaign_maps 3k_dlc07_main_map: maxx/maxy = ceil((hex-1) * 0.668 / 0.772)
 - EmpireDesignData/campaign_maps/3k_dlc07_main_map/map.hex
 - raw_data/terrain/campaigns/3k_dlc07_main_map: the warped AK project (ak_main.py) copied over
Backups: output/backups/main190_install_<timestamp>/ (same relative layout).
"""
import json, math, os, re, shutil, sys, time
from pathlib import Path
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
from terrain_main import NWW, NWH
from warp import Warp, current

AK = Path(r"C:/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/assembly_kit_190E")
DB, EDD = AK / "raw_data" / "db", AK / "raw_data" / "EmpireDesignData"
TER = AK / "raw_data" / "terrain" / "campaigns" / "3k_dlc07_main_map"
HEXDST = EDD / "campaign_maps" / "3k_dlc07_main_map" / "map.hex"
TABLES = ["regions", "provinces", "region_to_province_junctions", "campaign_map_regions", "campaign_map_settlements",
          "start_pos_regions", "start_pos_settlements", "start_pos_region_slot_templates"]
CR, LF = chr(13), chr(10)
W = current()


def records(text, table):
    return list(re.finditer(rf'<{table} record_uuid="[^"]*"[^>]*>.*?</{table}>(?:{CR}?{LF})?', text, re.S))


def main(db_only=False):
    """db_only: only the new-region tables (the map itself is now 3k_190e_expanded_map, installed by
    newmap_install.py; the old map's playable areas / map.hex / terrain must stay 190E's originals)."""
    prov = json.load(open(HERE / "regions_new.json", encoding="utf-8")); prov = prov.get("provinces", prov)   # round 6 format
    keys = [r for p in prov.values() for r in p["regions"]] + [p["province"] for p in prov.values()]
    # also every region / province of earlier rounds (their keys may not be in this round's set): our region prefixes,
    # and the round 3-5 province keys (190E's own ironic_region_* / 3k_ironic_province_<190E> rows are not ours)
    from regions_carve import PROVINCES as OLD
    keys += [f"3k_ironic_province_{k}" for k in OLD]
    pat = re.compile(r"ironic_(?:central|hexi|nomad|south)_[a-z0-9_]+|" +
                     "|".join(re.escape(k) + r"(?![a-z0-9_])" for k in sorted(keys, key=len, reverse=True)))
    ours = lambda rec: bool(pat.search(rec))
    bk = Path(r"Z:/Claude/TerryClone/output/backups") / ("main190_install_" + time.strftime("%Y%m%d_%H%M%S"))
    def backup(p):
        dst = bk / p.relative_to(AK); dst.parent.mkdir(parents=True, exist_ok=True)
        (shutil.copytree if p.is_dir() else shutil.copy2)(p, dst)
    for t in TABLES + ([] if db_only else ["campaign_map_playable_areas", "campaign_maps"]):
        backup(DB / f"{t}.xml"); backup(EDD / f"{t}.xml")
    if not db_only: backup(HEXDST); backup(TER)
    print("backup ->", bk)

    for t in TABLES:
        new = [m.group(0) for m in records(open(HERE / "ak_db" / f"{t}.xml", encoding="utf-8", newline="").read(), t) if ours(m.group(0))]
        for base in (DB, EDD):
            p = base / f"{t}.xml"; text = open(p, encoding="utf-8", newline="").read()
            eol = CR + LF if CR + LF in text else LF
            removed = 0
            for m in reversed(records(text, t)):
                if ours(m.group(0)): text = text[:m.start()] + text[m.end():]; removed += 1
            end = text.rindex("</dataroot>")
            text = text[:end] + "".join(r.rstrip(CR + LF) + eol for r in new) + text[end:]
            open(p, "w", encoding="utf-8", newline="").write(text)
            print(f"  {base.name}/{t}.xml: +{len(new)} (replaced {removed})")
    if db_only: return
    cmx, cmy = math.ceil((W.W - 1) * 0.668), math.ceil((W.H - 1) * 0.772)
    for base in (DB, EDD):
        p = base / "campaign_map_playable_areas.xml"; text = open(p, encoding="utf-8", newline="").read()
        text, n1 = re.subn(r"<maxx>[^<]*</maxx>", f"<maxx>{NWW:.3f}</maxx>", text)
        text, n2 = re.subn(r"<maxy>[^<]*</maxy>", f"<maxy>{NWH:.3f}</maxy>", text)
        open(p, "w", encoding="utf-8", newline="").write(text)
        p = base / "campaign_maps.xml"; text = open(p, encoding="utf-8", newline="").read()
        def fix(m):
            r = re.sub(r"<maxx>[^<]*</maxx>", f"<maxx>{cmx}</maxx>", m.group(0)); return re.sub(r"<maxy>[^<]*</maxy>", f"<maxy>{cmy}</maxy>", r)
        text, n3 = re.subn(r'<campaign_maps [^>]*record_key="3k_dlc07_main_map".*?</campaign_maps>', fix, text, flags=re.S)
        open(p, "w", encoding="utf-8", newline="").write(text)
        print(f"  {base.name}: playable areas {n1}/{n2} rows -> {NWW:.3f} x {NWH:.3f}; campaign_maps 3k_dlc07_main_map ({n3}) -> {cmx} x {cmy}")
    shutil.copy2(HERE / "hex" / "map.hex", HEXDST); print("  map.hex ->", HEXDST)
    n = 0
    for f in (HERE / "ak" / "3k_dlc07_main_map").iterdir():
        shutil.copy2(f, TER / f.name); n += 1
    print(f"  terrain project: {n} files -> {TER}")


if __name__ == "__main__":
    main(db_only="--db-only" in sys.argv)
