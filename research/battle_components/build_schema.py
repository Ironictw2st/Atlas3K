"""Turn the decompiled constructor fields into (1) research/battle_components/battle_components.json, the derived
field table (names, kinds, defaults, ranges, enum value lists, custom value types), and (2) additive entries in
Atlas3K's component_schema.json for components the kit corpus never showed with attributes.

Existing schema entries are left untouched: only components whose "Fields" list is empty get fields, marked
Source = "decompile" with Count 0 (never seen in the corpus).

usage: build_schema.py <ctor_fields.json> [--write-schema]
"""
import argparse, json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEMA = HERE.parents[1] / "src/Atlas3K.Formats/Terry/Data/component_schema.json"

# Terry-side components (tweak_terrainmetadataeditor.modder.x64.dll, Terry::EC*), read from their constructors
# (FUN_180052390, FUN_180051d20, FUN_180051f30 in that DLL; constants DAT_1805bf258 = 3, DAT_1805bf2a8 = 100,
# DAT_1805bf2c4 = 5000).
TERRY = {
    "ECTerryBattlefieldZone": {"address": "tweak:180052390", "fields": [
        {"display": "Locked", "kind": "PROPERTY_BOOL", "default": False},
        {"display": "Rank Distance", "kind": "PROPERTY_RANGED_FLOAT", "default": 3.0, "min": 0.0, "max": 100.0},
        {"display": "Zone Skirt Distance", "kind": "PROPERTY_RANGED_FLOAT", "default": 3.0, "min": 0.0, "max": 100.0}]},
    "ECLineOfSight": {"address": "tweak:180051d20", "fields": [
        {"display": "Active", "kind": "PROPERTY_BOOL", "default": True},
        {"display": "Range", "kind": "PROPERTY_RANGED_FLOAT", "default": 0.0, "min": 0.0, "max": 5000.0}]},
    "ECBuildingSlotPreview": {"address": "tweak:180051f30", "fields": [
        {"display": "Level", "kind": "PROPERTY_STRING", "default": "",
         "attributes": {"CUSTOM_TYPE_ATTRIBUTE": "BuildingSlotLevel"}}]},
}

KIND_TYPE = {"PROPERTY_BOOL": "Bool", "PROPERTY_INT": "Int", "PROPERTY_RANGED_INT": "Int", "PROPERTY_FLOAT": "Float",
             "PROPERTY_RANGED_FLOAT": "Float", "PROPERTY_STRING": "String", "PROPERTY_FILENAME": "Path",
             "PROPERTY_VECTOR2": "Vec2", "PROPERTY_VECTOR3": "Vec3", "PROPERTY_COLOUR_RGBO": "Colour",
             "PropertyEnum": "Enum", "PropertyEnumFlags": "String"}
NEUTRAL = {"Vec2": "0 0", "Vec3": "0 0 0", "Colour": "255 255 255 255", "String": "", "Path": ""}


def attribute(display):
    """Terry's attribute name: display name in lower case, spaces -> '_', a leading digit gets '_' (XML names can't
    start with a digit; ECTapeMeasure "3D View Render" is written _3d_view_render)."""
    a = display.lower().replace(" ", "_")
    return "_" + a if a[:1].isdigit() else a


def fmt(v, typ):
    if v is None: return NEUTRAL.get(typ)
    if isinstance(v, bool): return "true" if v else "false"
    if isinstance(v, float): return str(int(v)) if v == int(v) else repr(v)
    return str(v)


def table(ctor):
    out = {}
    for comp, r in sorted(ctor.items()):
        out[comp] = {"source": f'qttoolutility:{r["address"]}', "fields": []}
        for f in r["fields"]:
            out[comp]["fields"].append(entry(f))
    for comp, r in TERRY.items():
        out[comp] = {"source": r["address"], "fields": [entry(f) for f in r["fields"]]}
    return out


def entry(f):
    typ = KIND_TYPE.get(f["kind"], "String")
    e = {"attribute": attribute(f["display"]), "display": f["display"], "kind": f["kind"], "type": typ,
         "default": fmt(f.get("default"), typ)}
    for k in ("min", "max"):
        if f.get(k) is not None: e[k] = f[k]
    if f.get("values"): e["values"] = f["values"]
    if f.get("value_labels"): e["value_labels"] = f["value_labels"]
    if f.get("enum_type"): e["enum_type"] = f["enum_type"]
    if f.get("attributes"): e["attributes"] = f["attributes"]
    return e


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fields")
    ap.add_argument("--write-schema", action="store_true")
    a = ap.parse_args()
    ctor = json.load(open(a.fields, encoding="utf-8"))
    t = table(ctor)
    (HERE / "battle_components.json").write_text(json.dumps(t, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    added = {}
    for comp, r in t.items():
        c = schema["Components"].get(comp)
        if c is None or c["Fields"] or not r["fields"]: continue   # unknown component, or the corpus already has it
        c["Fields"] = [{"Name": f["attribute"], "Type": f["type"], "Count": 0, "Default": f["default"],
                        **({"Values": f["values"]} if f["type"] == "Enum" and f.get("values") else {}),
                        "Source": "decompile"} for f in r["fields"]]
        added[comp] = [f["attribute"] for f in r["fields"]]
    print(json.dumps(added, indent=1))
    if a.write_schema:
        SCHEMA.write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
