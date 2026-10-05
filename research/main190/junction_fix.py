#!/usr/bin/env python3
"""Round 7: after install_ak.py --db-only, put the staged junction rows (ak_db/) of existing regions that changed
province (candidates.json province_r7) into the kit's raw_data/db and raw_data/EmpireDesignData junction tables.

install_ak only replaces records that mention this round's keys: a region moving OUT of a province that is not in
that key set kept its old row, one moving INTO such a province lost its new row (Lanling, Buji in round 7).
Every moved region ends with exactly the staged row; the whole table is then checked against ak_db."""
import json, re, collections
from pathlib import Path
HERE = Path(__file__).parent
AK = Path(r"C:/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/assembly_kit_190E/raw_data")
RX = r"<region_to_province_junctions .*?</region_to_province_junctions>"


def region_of(rec): return re.search(r"<region>([^<]*)</region>", rec).group(1)


def table(text):
    out = collections.defaultdict(list)
    for m in re.finditer(RX, text, re.S): out[region_of(m.group(0))].append(re.search(r"<province>([^<]*)</province>", m.group(0)).group(1))
    return out


ORIG = Path(r"Z:/Claude/TerryClone/output/backups/main190_originals_20260929_130639")


def main(restore=False):
    """restore=True (TERRAIN_ONLY builds): the moved regions get 190E's ORIGINAL junction rows back."""
    pm = json.load(open(HERE / "research_r6" / "candidates.json", encoding="utf-8")).get("province_r7", {})
    src = open((ORIG / "ak190E_db" / "region_to_province_junctions.xml") if restore else (HERE / "ak_db" / "region_to_province_junctions.xml"),
               encoding="utf-8", newline="").read()
    want = [m.group(0) for m in re.finditer(RX, src, re.S) if region_of(m.group(0)) in pm]
    staged = table(src)
    for base in (AK / "db", AK / "EmpireDesignData"):
        p = base / "region_to_province_junctions.xml"; t = open(p, encoding="utf-8", newline="").read()
        eol = "\r\n" if "\r\n" in t else "\n"
        for m in reversed(list(re.finditer(RX + r"\s*", t, re.S))):
            if region_of(m.group(0)) in pm: t = t[:m.start()] + t[m.end():]
        end = t.rindex("</dataroot>"); t = t[:end] + "".join(r + eol for r in want) + t[end:]
        open(p, "w", encoding="utf-8", newline="").write(t)
        kit = table(t)
        diff = [k for k in (set(pm) if restore else set(kit) | set(staged)) if sorted(kit.get(k, [])) != sorted(staged.get(k, []))]
        multi = [k for k, v in kit.items() if len(v) > 1]
        print(f"{base.name}: {len(want)} moved-region rows set; differs from staged: {len(diff)} {diff[:6]}; multi: {multi[:6]}")


if __name__ == "__main__":
    import sys as _s
    main(restore="--restore" in _s.argv)
