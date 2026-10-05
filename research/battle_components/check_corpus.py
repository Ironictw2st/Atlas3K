"""Check the decompiled constructor fields (ctor_fields.py output) against what Terry actually wrote in the corpus.

Two sources of .layer/.terry evidence:
  * Atlas3K's embedded component_schema.json (every .layer/.terry under the vanilla kit's raw_data);
  * an extra scan of given roots (other kits' battle projects, BattleMaps extracts) for the battle components.

For every component it reports whether the constructor's attribute names (display name -> lower_snake) and order
equal the corpus, which corpus attributes the constructor does not register, and value statistics for the battle
components from the extra roots.

usage: check_corpus.py <ctor_fields.json> [--root <dir>]... [--out report.json]
"""
import argparse, collections, json, sys
from pathlib import Path
import xml.etree.ElementTree as ET

SCHEMA = Path(__file__).resolve().parents[2] / "src/Atlas3K.Formats/Terry/Data/component_schema.json"
BATTLE = {"ECCaptureLocation", "ECDeploymentZone", "ECDeploymentZoneRegion", "ECBuilding", "ECWall", "ECSiegeAINode",
          "ECSiegeAIEdge", "ECSiegeAIBoundary", "ECBattleProperties", "ECPlayableArea", "ECBattlefieldZone",
          "ECTerryBattlefieldZone", "ECCamera", "ECCameraZone", "ECCameraBounds", "ECBuildingSlot",
          "ECBuildingSlotPreview", "ECLiteBuildingOutline", "ECProceduralExclusionZone2", "ECCivilianDeployment",
          "ECCivilianShelter", "ECBattleXML", "ECBattleCatchmentArea", "ECBattleCatchmentAreaBoundary",
          "ECBattleCatchmentAreaInTile", "ECPlayerDeploymentLocations", "ECBuildingDestructionLevel",
          "ECBuildingProjectileEmitter", "ECAIHint", "ECAISeparator", "ECEFLine", "ECGoRegion", "ECNoGoRegion",
          "ECUnit", "ECLineOfSight", "ECTileAlignment", "ECTileCellAlignment"}


def scan(roots):
    """{component: {"count", "files", "attrs": {name: Counter(values)}, "children": Counter}} over the roots."""
    out = collections.defaultdict(lambda: {"count": 0, "files": set(), "attrs": collections.defaultdict(collections.Counter),
                                           "children": collections.Counter(), "order": collections.Counter()})
    n = 0
    for root in roots:
        for f in Path(root).rglob("*"):
            if f.suffix.lower() not in (".layer", ".terry") or not f.is_file(): continue
            try: tree = ET.parse(f)
            except Exception: continue
            n += 1
            for ent in tree.iter("entity"):
                for c in ent:
                    if c.tag not in BATTLE: continue
                    r = out[c.tag]; r["count"] += 1; r["files"].add(str(f))
                    for k, v in c.attrib.items(): r["attrs"][k][v] += 1
                    r["order"][",".join(c.attrib)] += 1
                    for ch in c: r["children"][ch.tag] += 1
    return out, n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fields")
    ap.add_argument("--root", action="append", default=[])
    ap.add_argument("--out")
    a = ap.parse_args()
    ctor = json.load(open(a.fields, encoding="utf-8"))
    schema = json.load(open(SCHEMA, encoding="utf-8"))["Components"]
    extra, nfiles = scan(a.root)
    report = {"extra_files_scanned": nfiles, "components": {}}
    exact = partial = 0
    for comp in sorted(set(ctor) | set(schema)):
        c_attrs = [f["attribute"] for f in ctor.get(comp, {}).get("fields", [])]
        s_attrs = [f["Name"] for f in schema.get(comp, {}).get("Fields", [])]
        e = extra.get(comp)
        e_attrs = list(e["order"].most_common(1)[0][0].split(",")) if e and e["order"] else []
        e_attrs = [x for x in e_attrs if x]
        corpus = s_attrs or e_attrs
        status = ("no corpus" if not corpus else "match" if corpus == c_attrs else
                  "ctor subset of corpus" if set(c_attrs) < set(corpus) else "differs")
        if corpus and comp in ctor:
            if corpus == c_attrs: exact += 1
            else: partial += 1
        report["components"][comp] = {
            "ctor": c_attrs, "kit_corpus": s_attrs, "extra_corpus": e_attrs, "status": status,
            "corpus_only": [x for x in corpus if x not in c_attrs], "ctor_only": [x for x in c_attrs if x not in corpus],
            "extra_count": e["count"] if e else 0, "extra_files": len(e["files"]) if e else 0,
            "extra_values": {k: dict(v.most_common(12)) for k, v in e["attrs"].items()} if e else {},
            "extra_children": dict(e["children"]) if e else {},
        }
    report["summary"] = {"exact_order_matches": exact, "mismatches": partial}
    text = json.dumps(report, indent=1, ensure_ascii=False)
    if a.out: Path(a.out).write_text(text, encoding="utf-8")
    for comp, r in report["components"].items():
        if comp in BATTLE or r["status"] != "match":
            print(f'{comp:32s} {r["status"]:14s} ctor={r["ctor"]} corpus_only={r["corpus_only"]} extra={r["extra_count"]}')
    print(report["summary"], "extra files", nfiles)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
