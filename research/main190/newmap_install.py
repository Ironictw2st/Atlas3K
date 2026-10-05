#!/usr/bin/env python3
"""Install the reworked 190E map as its OWN map, 3k_190e_expanded_map, in assembly_kit_190E (user decision 2026-09-29).

Overriding 3k_dlc07_main_map left vanilla files loading (land_mesh_168/169, sea_mesh_98-124, patches, probes) - the
slab / missing river water. A new map name has no vanilla files. Campaign 3k_main_campaign_map is pointed at it.

 - EmpireDesignData/campaign_maps/<NEW>/map.hex        our map.hex, header map name renamed, crc32 recomputed
 - raw_data/terrain/campaigns/<NEW>/                   ak_main.py's project, files + .terry renamed
 - DB (raw_data/db AND raw_data/EmpireDesignData, each file edited separately; earlier <NEW> records replaced):
     campaign_maps                <NEW> (clone of 3k_dlc07_main_map, maxx/maxy = ceil of the hex rule)
     campaign_map_regions         <NEW> + every region in the map.hex lists (clones of their 3k_dlc07_main_map rows)
     campaign_map_playable_areas  new row (clone of index 1799249611): mapname <NEW>, fresh index, raster-world extents
     campaigns                    3k_main_campaign_map: map_name / display_location -> <NEW>
 - the kit's own 3k_dlc07_main_map (map.hex + terrain project) is restored to 190E's originals (other campaigns)
Backups: output/backups/main190_newmap_<ts>/.
"""
import math, os, random, re, shutil, struct, sys, time, uuid, zlib, json
from pathlib import Path
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
import crop_scale_map_hex as C, hexmap
from terrain_main import NWW, NWH
# playable-area extents: the user's rule (hex_max_x - 1) * 0.668, (hex_max_y - 1) * 0.772 (campaign_maps: ceil of these)
from warp import Warp, current

NEW, OLD = "3k_190e_expanded_map", "3k_dlc07_main_map"
CAMP = "3k_main_campaign_map"
AK = Path(r"C:/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/assembly_kit_190E")
DB, EDD = AK / "raw_data" / "db", AK / "raw_data" / "EmpireDesignData"
ORIG = Path(r"Z:/Claude/TerryClone/output/backups/main190_originals_20260929_130639")
CR, LF = chr(13), chr(10)
W = current()
PMX, PMY = NWW, NWH                   # user (round 8 test): playable area = the raster world size (vanilla/Guandu way)


def records(text, table):
    return list(re.finditer(rf'<{table} record_uuid="[^"]*"[^>]*>.*?</{table}>(?:{CR}?{LF})?', text, re.S))


def set_tag(rec, tag, value):
    rec, n = re.subn(rf"(<{tag}(?: [^>]*)?>)[^<]*(</{tag}>)", lambda m: f"{m.group(1)}{value}{m.group(2)}", rec)
    assert n == 1, tag
    return rec


def new_uuid(rec):
    return re.sub(r'record_uuid="\{[^}]*\}"', f'record_uuid="{{{uuid.uuid4()}}}"', rec, count=1)


def edit(base, table, is_ours, build, modify=None):
    p = base / f"{table}.xml"; text = open(p, encoding="utf-8", newline="").read()
    eol = CR + LF if CR + LF in text else LF
    for m in reversed(records(text, table)):
        if is_ours(m.group(0)): text = text[:m.start()] + text[m.end():]
    if modify: text = modify(text)
    added = build(text)
    end = text.rindex("</dataroot>")
    open(p, "w", encoding="utf-8", newline="").write(text[:end] + "".join(r.rstrip(CR + LF) + eol for r in added) + text[end:])
    return len(added)


def main():
    bk = Path(r"Z:/Claude/TerryClone/output/backups") / ("main190_newmap_" + time.strftime("%Y%m%d_%H%M%S"))
    for base in (DB, EDD):
        for t in ("campaign_maps", "campaign_map_regions", "campaign_map_playable_areas", "campaigns"):
            d = bk / base.name; d.mkdir(parents=True, exist_ok=True); shutil.copy2(base / f"{t}.xml", d)
    old_hex = EDD / "campaign_maps" / OLD / "map.hex"; old_ter = AK / "raw_data" / "terrain" / "campaigns" / OLD
    shutil.copy2(old_hex, bk / "old_map.hex"); shutil.copytree(old_ter, bk / "old_terrain")
    print("backup ->", bk)

    # --- map.hex under the new name ---
    src = (HERE / "hex" / "map.hex").read_bytes(); P, w, h = C.locate_dims(src)
    body = C.rename(src[:P], NEW) + src[P:-4]
    out = body + struct.pack("<I", zlib.crc32(body) & 0xFFFFFFFF)
    (HERE / "hex" / "map_newname.hex").write_bytes(out)
    assert hexmap.load(str(HERE / "hex" / "map_newname.hex"))["map"] == NEW
    d = EDD / "campaign_maps" / NEW; d.mkdir(parents=True, exist_ok=True); (d / "map.hex").write_bytes(out)
    print("map.hex ->", d / "map.hex")

    # --- terrain project under the new name ---
    ter = AK / "raw_data" / "terrain" / "campaigns" / NEW
    if ter.exists(): shutil.rmtree(ter)
    ter.mkdir(parents=True)
    for f in (HERE / "ak" / OLD).iterdir():
        dst = ter / f.name.replace(OLD, NEW)
        if f.suffix == ".terry" or f.name.endswith(".terry.user"):
            dst.write_text(f.read_text(encoding="utf-8").replace(f"terrain/campaigns/{OLD}/", f"terrain/campaigns/{NEW}/"), encoding="utf-8")
        else:
            shutil.copy2(f, dst)
    print("terrain project ->", ter, len(list(ter.iterdir())), "files")

    # --- restore the kit's 3k_dlc07_main_map to 190E's originals (the other campaigns still use it) ---
    shutil.copy2(ORIG / "190Expanded_map.hex", old_hex)
    for f in (ORIG / "ak190E_terrain_3k_dlc07_main_map").iterdir():
        shutil.copy2(f, old_ter / f.name)
    print("kit 3k_dlc07_main_map restored to 190E originals")

    # --- DB rows ---
    lists = hexmap.load(str(HERE / "hex" / "map_newname.hex"))["lists"]; present = lists["land_regions"] + lists["sea_regions"]
    cmx, cmy = math.ceil((W.W - 1) * 0.668), math.ceil((W.H - 1) * 0.772)
    idx = str(random.Random(NEW).randrange(10**9, 2**31))
    for base in (DB, EDD):
        n1 = edit(base, "campaign_maps", lambda r: f'record_key="{NEW}"' in r, lambda text: [
            set_tag(set_tag(set_tag(new_uuid(next(m.group(0) for m in records(text, "campaign_maps") if f'record_key="{OLD}"' in m.group(0)))
                                    .replace(f'record_key="{OLD}"', f'record_key="{NEW}"'), "mapname", NEW), "maxx", cmx), "maxy", cmy)])
        def regions(text):
            known = {}
            for m in records(text, "campaign_map_regions"):
                if f"<campaign_map>{OLD}</campaign_map>" in m.group(0):
                    known[re.search(r"<region>([^<]*)</region>", m.group(0)).group(1)] = m.group(0)
            miss = [r for r in present if r not in known]
            if miss: print("   regions without a 3k_dlc07_main_map row (skipped):", miss[:8], len(miss))
            return [set_tag(new_uuid(known[r]).replace(f'record_key="{OLD}{r}"', f'record_key="{NEW}{r}"'), "campaign_map", NEW) for r in present if r in known]
        n2 = edit(base, "campaign_map_regions", lambda r: f"<campaign_map>{NEW}</campaign_map>" in r, regions)
        def playable(text):
            src = next(m.group(0) for m in records(text, "campaign_map_playable_areas") if "<index>1799249611</index>" in m.group(0))
            rec = re.sub(r'record_key="\d+"', f'record_key="{idx}"', new_uuid(src))
            for tag, val in (("index", idx), ("campaign_key", CAMP), ("mapname", NEW), ("maxx", f"{PMX:.3f}"), ("maxy", f"{PMY:.3f}")):
                rec = set_tag(rec, tag, val)
            return [rec]
        n3 = edit(base, "campaign_map_playable_areas", lambda r: f"<mapname>{NEW}</mapname>" in r, playable)
        def camp_mod(text):
            m = next(m for m in records(text, "campaigns") if f'record_key="{CAMP}"' in m.group(0))
            rec = set_tag(m.group(0), "map_name", NEW)
            if "<display_location>" in rec: rec = set_tag(rec, "display_location", NEW)
            return text[:m.start()] + rec + text[m.end():]
        edit(base, "campaigns", lambda r: False, lambda text: [], modify=camp_mod)
        print(f"  {base.name}: campaign_maps +{n1}, campaign_map_regions +{n2}, playable areas +{n3} (index {idx}), campaigns {CAMP} -> {NEW}")
    json.dump({"map": NEW, "playable_index": idx, "maxx": PMX, "maxy": PMY}, open(HERE / "newmap.json", "w"), indent=1)


if __name__ == "__main__":
    main()
