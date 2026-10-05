#!/usr/bin/env python3
"""Add 3k_guandu_map / 3k_guandu_start_pos records to the Steam AK raw_data/db XMLs, cloned from the 3k_dlc07
records. Idempotent: earlier guandu records are removed first. Insert-only: every other byte (incl. CRLF) is kept.
Backups: output/backups/ak_db_before_guandu_*.

  campaign_maps                3k_guandu_map, maxx/maxy from the hex grid rule
  campaign_map_regions         one row per region that still has hexes in the guandu map.hex
  campaign_map_playable_areas  clone of the 3k_main_campaign_map row: index/campaign_key/mapname/extents changed
  campaigns                    clone of 3k_dlc07_start_pos (Fates Divided): key/map/display_location changed
"""
import math, os, random, re, sys, uuid
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import hexmap

DB = r"C:/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/assembly_kit/raw_data/db"
HEX = r"C:/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/assembly_kit/raw_data/EmpireDesignData/campaign_maps/3k_guandu_map/map.hex"
MAP, CAMP, SRC_MAP = "3k_guandu_map", "3k_guandu_start_pos", "3k_dlc07_main_map"
# world extents = the raster world (vanilla: playable_areas maxx 595.1 = its raster width), same value everywhere:
# AK db, EmpireDesignData (BOB) and the pack (game, Terry)
from crop_scale_terrain import NW, NH, NWW as MAXX, NWH as MAXY
CR, LF = chr(13), chr(10)


def records(text, table):
    return list(re.finditer(rf'<{table} record_uuid="[^"]*"[^>]*>.*?</{table}>(?:{CR}?{LF})?', text, re.S))


def new_uuid(rec):
    return re.sub(r'record_uuid="\{[^}]*\}"', f'record_uuid="{{{uuid.uuid4()}}}"', rec, count=1)


def set_tag(rec, tag, value):
    rec, n = re.subn(rf"<{tag}>[^<]*</{tag}>", f"<{tag}>{value}</{tag}>", rec)
    assert n == 1, tag
    return rec


def is_ours(rec):
    return f'record_key="{MAP}' in rec or f'record_key="{CAMP}"' in rec or f"<campaign_key>{CAMP}<" in rec


def edit(table, build):
    path = os.path.join(DB, table + ".xml")
    text = open(path, encoding="utf-8", newline="").read()
    eol = CR + LF if CR + LF in text else LF
    for m in reversed(records(text, table)):
        if is_ours(m.group(0)):
            text = text[:m.start()] + text[m.end():]
    added = [r.rstrip(CR + LF) + eol for r in build(text)]
    end = text.rindex("</dataroot>")
    open(path, "w", encoding="utf-8", newline="").write(text[:end] + "".join(added) + text[end:])
    print(f"{table}: +{len(added)} records")


def empty_regions():
    log = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "val_regions.log"), encoding="utf-8").read()
    return set(re.findall(r"Region ([a-z0-9_]+) does not have any hexes", log))


def main():
    m = hexmap.load(HEX)
    # every region in the map.hex region lists, including ones the crop emptied: CAIME's lookup exporter needs a
    # DB row for each listed region, and CA's map-data builder accepts listed regions that have no hexes
    present = m["lists"]["land_regions"] + m["lists"]["sea_regions"]

    def maps(text):
        src = next(r.group(0) for r in records(text, "campaign_maps") if f'record_key="{SRC_MAP}"' in r.group(0))
        rec = new_uuid(src).replace(f'record_key="{SRC_MAP}"', f'record_key="{MAP}"')
        # campaign_maps holds whole numbers (vanilla 596 x 542 = ceil of 595.1 x 541.x)
        return [set_tag(set_tag(set_tag(rec, "mapname", MAP), "maxx", str(math.ceil(MAXX))), "maxy", str(math.ceil(MAXY)))]

    def regions(text):
        src = [r.group(0) for r in records(text, "campaign_map_regions") if f"<campaign_map>{SRC_MAP}</campaign_map>" in r.group(0)]
        known = {re.search(r"<region>([^<]*)</region>", r).group(1): r for r in src}
        missing = [r for r in present if r not in known]
        if missing:
            print("  not in dlc07 campaign_map_regions (skipped):", missing)
        return [set_tag(new_uuid(known[r]).replace(f'record_key="{SRC_MAP}{r}"', f'record_key="{MAP}{r}"'), "campaign_map", MAP)
                for r in present if r in known]

    def playable(text):
        src = next(r.group(0) for r in records(text, "campaign_map_playable_areas")
                   if "<campaign_key>3k_main_campaign_map</campaign_key>" in r.group(0))
        idx = str(random.Random(MAP).randrange(10**9, 2**31))
        rec = re.sub(r'record_key="\d+"', f'record_key="{idx}"', new_uuid(src))
        for tag, val in (("index", idx), ("campaign_key", CAMP), ("mapname", MAP), ("maxx", f"{MAXX:.3f}"), ("maxy", f"{MAXY:.3f}")):
            rec = set_tag(rec, tag, val)
        return [rec]

    def campaigns(text):
        src = next(r.group(0) for r in records(text, "campaigns") if 'record_key="3k_dlc07_start_pos"' in r.group(0))
        rec = new_uuid(src).replace('record_key="3k_dlc07_start_pos"', f'record_key="{CAMP}"')
        return [set_tag(set_tag(set_tag(rec, "campaign_name", CAMP), "map_name", MAP), "display_location", MAP)]

    edit("campaign_maps", maps)
    edit("campaign_map_regions", regions)
    edit("campaign_map_playable_areas", playable)
    edit("campaigns", campaigns)


if __name__ == "__main__":
    main()
