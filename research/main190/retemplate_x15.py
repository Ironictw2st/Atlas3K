#!/usr/bin/env python3
"""Retemplate EXISTING regions between city and resource (2026-10-02; written for the CAIME web painter's province
editor). Runs after regions_db.py (which only flips is_capital for existing regions), on its outputs:
regions_new.json "retemplate": {"<region>": {"type": "city"} | {"type": "resource", "resource": "<3k_resource_*>"}}

For every listed region, in all 5 campaigns, pack TSVs (db_out/) and AK XMLs (ak_db/):
  start_pos_region_slot_templates  city: 3k_city (primary) + 3k_districts (secondary)
                                   resource: <resource> (primary) + the province's flavour (secondary: the most common
                                   secondary of the province's other resource regions in that campaign, else the
                                   region's own resource secondary, else ironic_province_yu_standard)
  start_pos_regions.slot_cap       9 / 2
  start_pos_settlements.primary_building   3k_city_0 / <resource>_1
  start_pos_region_pooled_resources        population 15 / 12 (pack only; the AK copy is not built by regions_db)
  campaign_settlement_display_settlement_layouts   city: a layout row if the settlement has none in the pack
Passes (3k_dlc06_*_pass, gate templates) are refused. Regions whose stock type already matches are reported and skipped.
The map.hex footprint (capital 33 hexes / resource 16) is NOT changed here - the painter re-stamps it."""
import collections, glob, json, re, sys
from pathlib import Path
HERE = Path(__file__).parent
OUT = HERE / "db_out" / "db"; AKOUT = HERE / "ak_db"
TAB = "\t"
LAYOUTS = ["settlement_land_layout_a", "settlement_land_layout_b", "settlement_land_layout_c"]
FALLBACK_FLAVOUR = "ironic_province_yu_standard"


def read_tsv(path):
    lines = open(path, encoding="utf-8", newline="").read().split("\n")
    return lines


def write_tsv(path, lines):
    open(path, "w", encoding="utf-8", newline="").write("\n".join(lines))


def rows(table):
    """[(path, lines, header cols)] for every TSV of a pack table in db_out."""
    out = []
    for p in sorted(glob.glob(str(OUT / f"{table}_tables" / "*.tsv"))):
        ls = read_tsv(p); out.append((p, ls, ls[0].rstrip("\r").split(TAB)))
    return out


def main():
    nj = json.load(open(HERE / "regions_new.json", encoding="utf-8"))
    req = nj.get("retemplate") or {}
    if not req:
        print("retemplate: nothing requested"); return
    prov_of = {m: pv for pv in nj["all_provinces"] for m in pv["members"]}
    # current slot templates: (campaign, region) -> {slot_type: template}
    cur = collections.defaultdict(dict)
    slt = rows("start_pos_region_slot_templates")
    for _, ls, H in slt:
        for l in ls[1:]:
            a = l.rstrip("\r").split(TAB)
            if len(a) == len(H) and not a[0].startswith("#"):
                d = dict(zip(H, a)); cur[(d["campaign"], d["region"])][d["slot_type"]] = d["slot_template"]
    camps = sorted({c for c, _ in cur})
    plan = {}
    for reg, spec in req.items():
        if "_pass" in reg or any(v.startswith("3k_dlc06_gate") for (c, r), t in cur.items() if r == reg for v in t.values()):
            print(f"retemplate: {reg} is a pass - refused"); continue
        typ = spec.get("type")
        if typ not in ("city", "resource") or (typ == "resource" and not spec.get("resource", "").startswith("3k_")):
            print(f"retemplate: {reg} bad spec {spec} - skipped"); continue
        for camp in camps:
            t = cur.get((camp, reg))
            if not t: continue
            if typ == "city":
                if t.get("primary") == "3k_city": continue
                plan[(camp, reg)] = {"primary": "3k_city", "secondary": "3k_districts", "cap": 9, "bld": "3k_city_0", "pop": 15}
            else:
                res = spec["resource"]
                if t.get("primary") == res: continue
                pv = prov_of.get(reg)
                secs = collections.Counter(cur[(camp, m)].get("secondary") for m in (pv["members"] if pv else [])
                                           if m != reg and cur.get((camp, m), {}).get("primary") not in (None, "3k_city"))
                secs.pop(None, None); secs.pop("3k_districts", None)
                own = t.get("secondary") if t.get("secondary") != "3k_districts" else None
                flav = secs.most_common(1)[0][0] if secs else (own or FALLBACK_FLAVOUR)
                plan[(camp, reg)] = {"primary": res, "secondary": flav, "cap": 2, "bld": f"{res}_1", "pop": 12}
    if not plan:
        print("retemplate: all requested regions already match - nothing to do"); return
    regs = sorted({r for _, r in plan})
    # region ids per campaign (start_pos_regions.id) - settlements / pooled resources reference them
    rid = {}
    for _, ls, H in rows("start_pos_regions"):
        for l in ls[1:]:
            a = l.rstrip("\r").split(TAB)
            if len(a) == len(H):
                d = dict(zip(H, a))
                if (d.get("campaign"), d.get("region")) in plan: rid[(d["campaign"], d["region"])] = d["id"]
    by_id = {v: k for k, v in rid.items()}
    n = collections.Counter()
    # ---- pack TSVs
    for p, ls, H in slt:
        ch = False
        for i, l in enumerate(ls[1:], 1):
            a = l.rstrip("\r").split(TAB)
            if len(a) != len(H): continue
            d = dict(zip(H, a)); k = (d["campaign"], d["region"])
            if k in plan and d["slot_type"] in ("primary", "secondary"):
                a[H.index("slot_template")] = plan[k][d["slot_type"]]; ls[i] = TAB.join(a) + ("\r" if l.endswith("\r") else ""); ch = True; n["slot_templates"] += 1
        if ch: write_tsv(p, ls)
    for table, key, col, val in (("start_pos_regions", "region", "slot_cap", "cap"),
                                 ("start_pos_settlements", "region_id", "primary_building", "bld"),
                                 ("start_pos_region_pooled_resources", "region_id", "amount", "pop")):
        for p, ls, H in rows(table):
            ch = False
            for i, l in enumerate(ls[1:], 1):
                a = l.rstrip("\r").split(TAB)
                if len(a) != len(H): continue
                d = dict(zip(H, a))
                k = (d.get("campaign"), d.get("region")) if key == "region" else by_id.get(d.get("region"))
                if not k or k not in plan: continue
                if table == "start_pos_region_pooled_resources" and d.get("pooled_resource") != "3k_main_pooled_resource_population": continue
                a[H.index(col)] = str(plan[k][val]); ls[i] = TAB.join(a) + ("\r" if l.endswith("\r") else ""); ch = True; n[table] += 1
            if ch: write_tsv(p, ls)
    lay = rows("campaign_settlement_display_settlement_layouts")
    have = {l.split(TAB)[0] for _, ls, _ in lay for l in ls[1:]}
    p, ls, H = lay[0]
    for r in regs:
        if any(plan[(c, r)]["primary"] == "3k_city" for c in camps if (c, r) in plan) and f"settlement:{r}" not in have:
            ls.insert(len(ls) - 1 if ls[-1] == "" else len(ls), f"settlement:{r}{TAB}{LAYOUTS[len(have) % 3]}"); have.add(f"settlement:{r}"); n["layouts"] += 1
    write_tsv(p, ls)
    # ---- AK XMLs (ak_db/, installed by install_ak.py --db-only)
    def ak_edit(table, fn):
        path = AKOUT / f"{table}.xml"
        if not path.exists(): print(f"  AK {table}.xml missing in ak_db - run regions_db.py first"); return
        t = open(path, encoding="utf-8", newline="").read()
        t2, k = re.subn(rf"<{table} .*?</{table}>", fn, t, flags=re.S)
        open(path, "w", encoding="utf-8", newline="").write(t2)
    def slt_fn(m):
        rec = m.group(0); g = lambda tag: (re.search(rf"<{tag}>([^<]*)</{tag}>", rec) or [None, None])[1]
        k = (g("campaign"), g("region")); st = g("slot_type")
        if k not in plan or st not in ("primary", "secondary"): return rec
        old, new = g("slot_template"), plan[k][st]
        n["AK slot_templates"] += 1
        rec = rec.replace(f"<slot_template>{old}</slot_template>", f"<slot_template>{new}</slot_template>")
        return re.sub(r'record_key="([^"]*)"', lambda mm: f'record_key="{mm.group(1)[:len(mm.group(1)) - len(old)] + new if mm.group(1).endswith(old) else mm.group(1)}"', rec, 1)
    def spr_fn(m):
        rec = m.group(0); k = (re.search(r"<campaign>([^<]*)<", rec).group(1), re.search(r"<region>([^<]*)<", rec).group(1))
        if k not in plan: return rec
        n["AK start_pos_regions"] += 1
        return re.sub(r"<slot_cap>[^<]*</slot_cap>", f"<slot_cap>{plan[k]['cap']}</slot_cap>", rec)
    def sps_fn(m):
        rec = m.group(0); k = by_id.get(re.search(r"<region>([^<]*)<", rec).group(1))
        if not k or k not in plan: return rec
        n["AK start_pos_settlements"] += 1
        return re.sub(r"<primary_building>[^<]*</primary_building>", f"<primary_building>{plan[k]['bld']}</primary_building>", rec)
    ak_edit("start_pos_region_slot_templates", slt_fn); ak_edit("start_pos_regions", spr_fn); ak_edit("start_pos_settlements", sps_fn)
    print(f"retemplate: {len(regs)} regions ({', '.join(regs)}); rows changed {dict(n)}")


if __name__ == "__main__":
    main()
