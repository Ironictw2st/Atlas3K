#!/usr/bin/env python3
"""Mirror our 3k_guandu_map / 3k_guandu_start_pos records from raw_data/db into raw_data/EmpireDesignData.

BOB reads the DB from EmpireDesignData (not raw_data/db): without a campaign_map_playable_areas row for the map it
never creates the "Global Mesh" action, and global_props needs campaign_maps etc. Insert-only (old copies of our
records are replaced), CRLF kept. Backups: output/backups/empiredesign_before_guandu_<ts>/.
"""
import os, shutil, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ak_db_add_guandu import DB, CR, LF, records, is_ours

EDD = os.path.join(os.path.dirname(DB), "EmpireDesignData")
TABLES = ["campaign_maps", "campaign_map_playable_areas", "campaign_map_regions", "campaigns"]


def main():
    bk = os.path.join(r"Z:/Claude/TerryClone/output/backups", "empiredesign_before_guandu_" + time.strftime("%Y%m%d_%H%M%S"))
    os.makedirs(bk)
    for t in TABLES:
        src = open(os.path.join(DB, t + ".xml"), encoding="utf-8", newline="").read()
        ours = [m.group(0) for m in records(src, t) if is_ours(m.group(0))]
        dst_path = os.path.join(EDD, t + ".xml")
        shutil.copy2(dst_path, bk)
        text = open(dst_path, encoding="utf-8", newline="").read()
        eol = CR + LF if CR + LF in text else LF
        for m in reversed(records(text, t)):
            if is_ours(m.group(0)):
                text = text[:m.start()] + text[m.end():]
        end = text.rindex("</dataroot>")
        text = text[:end] + "".join(r.rstrip(CR + LF) + eol for r in ours) + text[end:]
        open(dst_path, "w", encoding="utf-8", newline="").write(text)
        print(f"{t}: {len(ours)} records mirrored")
    print("backup:", bk)


if __name__ == "__main__":
    main()
