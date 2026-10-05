#!/usr/bin/env python3
"""User-requested prop removals (korea_ref/prop_removals.json), applied by the build so they stay removed:
  ids        - stock entity ids (ak_main.do_entity drops them)
  generated  - north_dress / village_dress props matched by model substring + position (within r units)."""
import json, re
from pathlib import Path
HERE = Path(__file__).parent
_R = None


def _rules():
    global _R
    if _R is None:
        p = HERE / "korea_ref" / "prop_removals.json"
        _R = json.load(open(p, encoding="utf-8")) if p.exists() else {"ids": {}, "generated": []}
    return _R


def removed(entity_text, x, z):
    R = _rules()
    m = re.search(r'<entity id="([0-9a-f]+)"', entity_text)
    if m and m.group(1) in R["ids"]: return True
    mp = re.search(r'model_path="([^"]*)"', entity_text)
    mp = mp.group(1).lower() if mp else ""
    return any(g["model"] in mp and (x - g["x"]) ** 2 + (z - g["z"]) ** 2 <= g["r"] ** 2 for g in R["generated"])
