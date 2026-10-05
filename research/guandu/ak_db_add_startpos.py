#!/usr/bin/env python3
"""Minimal 3k_guandu_start_pos in the Steam AK raw_data/db XMLs: Cao Cao only, cloned from 3k_dlc07_start_pos.

 start_pos_calendars              1 row (start year 198)
 start_pos_factions               Cao Cao + the rebel factions regions name as rebels (no land, no characters)
 start_pos_regions                regions on the Guandu map (hexes); Cao Cao keeps his dlc07 regions, rest unowned
 start_pos_settlements / region_slot_templates / region_religions / region_pooled_resources   for those regions
 start_pos_characters             Cao Cao only, at his dlc07 hex moved onto the Guandu hex grid
 start_pos_character_retinue_unit_modifiers, start_pos_technologies   Cao Cao's
 campaigns                        3k_guandu_start_pos script_path -> script/campaign/three_kingdoms_early

IDs are seeded (same on every run); a rerun first removes every record carrying one of our IDs or the campaign
key, then inserts. Insert-only otherwise: other bytes (CRLF) untouched. Backups: output/backups/ak_db_before_startpos_*.
"""
import os, random, re, shutil, sys, time, uuid
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from ak_db_add_guandu import DB, CR, LF, records, new_uuid, set_tag
import crop_scale_map_hex as C
from rebuild_hex import unpack
from hexgrid import centre, nearest_hex, neighbour

SRC, CAMP, MAP = "3k_dlc07_start_pos", "3k_guandu_start_pos", "3k_guandu_map"
HEX = r"C:/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/assembly_kit/raw_data/EmpireDesignData/campaign_maps/3k_guandu_map/map.hex"
TABLES = ["campaigns", "start_pos_calendars", "start_pos_factions", "start_pos_regions", "start_pos_settlements",
          "start_pos_region_slot_templates", "start_pos_region_religions", "start_pos_region_pooled_resources",
          "start_pos_characters", "start_pos_character_retinue_unit_modifiers", "start_pos_technologies"]

g = lambda r, f: (re.search(r"<%s>([^<]*)</%s>" % (f, f), r) or [None, None])[1]


def load(t):
    return open(os.path.join(DB, t + ".xml"), encoding="utf-8", newline="").read()


def main():
    bk = os.path.join(r"Z:/Claude/TerryClone/output/backups", "ak_db_before_startpos_" + time.strftime("%Y%m%d_%H%M%S"))
    os.makedirs(bk)
    for t in TABLES: shutil.copy2(os.path.join(DB, t + ".xml"), bk)
    print("backup:", bk)

    text = {t: load(t) for t in TABLES}
    R = {t: [m.group(0) for m in records(text[t], t)] for t in TABLES}
    used = set()
    for t in TABLES:
        for r in R[t]: used.update(re.findall(r">(\d{6,11})<", r))
    rng = random.Random(CAMP)
    def new_id():
        while True:
            v = str(rng.randrange(10**9, 2**31 - 1))
            if v not in used: used.add(v); return v

    # regions present on the Guandu map
    mh = open(HEX, "rb").read(); P, w, h = C.locate_dims(mh)
    N = unpack(np.frombuffer(mh, np.uint8, 16 * w * h, P + 8).reshape(h, w, 16))
    sys.path.insert(0, os.path.join(HERE, "..")); import hexmap
    L = hexmap.load(HEX)["lists"]; names = L["land_regions"] + L["sea_regions"]
    present = {names[i] for i in np.unique(N["region"]) if i >= 0}

    fac = {g(r, "ID"): r for r in R["start_pos_factions"] if g(r, "campaign") == SRC}
    cao_old = next(k for k, r in fac.items() if g(r, "faction") == "3k_main_faction_cao_cao")
    reg = [r for r in R["start_pos_regions"] if g(r, "campaign") == SRC and g(r, "region") in present]
    rebels = {g(r, "rebel_faction") for r in reg} | {g(r, "alternative_rebel_faction") for r in reg}
    keep_fac = [cao_old] + [k for k, r in fac.items() if g(r, "faction") in rebels]
    fmap = {k: new_id() for k in keep_fac}
    idmap = dict(fmap)                                   # old id -> new id, for every cloned keyed record

    def clone(r, extra=()):
        r = new_uuid(r)
        for old, new in list(idmap.items()) + list(extra):
            r = r.replace(">%s<" % old, ">%s<" % new).replace('record_key="%s' % old, 'record_key="%s' % new)
            r = re.sub(r'(record_key="[^"]*)%s' % old, lambda m: m.group(1) + new, r)
        r = r.replace(SRC, CAMP)
        return r

    out = {t: [] for t in TABLES}
    # factions
    for k in keep_fac:
        out["start_pos_factions"].append(clone(fac[k]))
    # regions (+ settlements etc. keyed by region id)
    rmap = {}
    for r in reg:
        rmap[g(r, "id")] = new_id(); idmap[g(r, "id")] = rmap[g(r, "id")]
    owned = 0
    for r in reg:
        nr = clone(r)
        if g(r, "owning_faction") == cao_old: owned += 1
        else:
            nr = set_tag(nr, "owning_faction", ""); nr = set_tag(nr, "faction_capital", "0")
        out["start_pos_regions"].append(nr)
    for t, fld in (("start_pos_settlements", "region"), ("start_pos_region_religions", "region"),
                   ("start_pos_region_pooled_resources", "region")):
        for r in R[t]:
            if g(r, fld) in rmap:
                if t == "start_pos_settlements":
                    sid = new_id(); idmap[g(r, "id")] = sid
                out[t].append(clone(r))
    for r in R["start_pos_region_slot_templates"]:
        if g(r, "campaign") == SRC and g(r, "region") in present:
            out["start_pos_region_slot_templates"].append(clone(r, [(g(r, "id"), new_id())]))
    # calendar
    cal = next(r for r in R["start_pos_calendars"] if g(r, "campaign") == SRC)
    out["start_pos_calendars"].append(set_tag(clone(cal), "start_year", "198"))
    # Cao Cao
    cc = next(r for r in R["start_pos_characters"] if g(r, "faction") == cao_old and "cao_cao_hero" in (g(r, "template") or ""))
    cc_old = g(cc, "ID"); idmap[cc_old] = new_id()
    col, row = int(g(cc, "startx")), int(g(cc, "starty"))
    NW, NH = w, h; cw, ch = C.COL1 - C.COL0, C.ROW1 - C.ROW0
    x, z = centre(col - C.COL0, row - C.ROW0)
    nc, nr = (int(v) for v in nearest_hex(x * NW / cw, z * NH / ch, NW, NH))
    for rad in range(0, 12):                             # nearest passable land hex that is not a town
        cand = [(c, r_) for c in range(nc - rad, nc + rad + 1) for r_ in range(nr - rad, nr + rad + 1)
                if 0 <= c < NW and 0 <= r_ < NH and N["terr"][r_, c] != 1 and not N["imp"][r_, c] and N["slot"][r_, c] < 0]
        if cand: nc, nr = min(cand, key=lambda p: (p[0] - nc) ** 2 + (p[1] - nr) ** 2); break
    ncc = clone(cc)
    ncc = set_tag(set_tag(ncc, "startx", str(nc)), "starty", str(nr))
    out["start_pos_characters"].append(ncc)
    for r in R["start_pos_character_retinue_unit_modifiers"]:
        if g(r, "character") == cc_old: out["start_pos_character_retinue_unit_modifiers"].append(clone(r))
    for r in R["start_pos_technologies"]:
        if g(r, "faction") == cao_old: out["start_pos_technologies"].append(clone(r))
    # campaign script
    camp = next(r for r in R["campaigns"] if 'record_key="%s"' % CAMP in r)

    # write: drop any earlier guandu startpos records (campaign key or any of our ids), then insert
    ours = set(idmap.values())
    for t in TABLES:
        s = text[t]; eol = CR + LF if CR + LF in s else LF
        for m in reversed(list(records(s, t))):
            rec = m.group(0)
            if t == "campaigns": continue
            if ("<campaign>%s<" % CAMP) in rec or any((">%s<" % v) in rec for v in re.findall(r">(\d{6,11})<", rec) if v in ours):
                s = s[:m.start()] + s[m.end():]
        if t == "campaigns":
            m = next(m for m in records(s, t) if 'record_key="%s"' % CAMP in m.group(0))
            rec = set_tag(m.group(0), "script_path", "script/campaign/three_kingdoms_early")
            s = s[:m.start()] + rec + s[m.end():]
        else:
            add = "".join(r.rstrip(CR + LF) + eol for r in out[t])
            end = s.rindex("</dataroot>"); s = s[:end] + add + s[end:]
        open(os.path.join(DB, t + ".xml"), "w", encoding="utf-8", newline="").write(s)
        print(f"{t:45s} +{len(out[t])}")
    print(f"Cao Cao: dlc07 hex ({col},{row}) -> guandu hex ({nc},{nr}); regions {len(reg)} ({owned} his); factions {len(keep_fac)}")


if __name__ == "__main__":
    main()
