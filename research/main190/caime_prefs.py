#!/usr/bin/env python3
"""Point CAIME's Three Kingdoms Assembly Kit at assembly_kit_190E (arg 'set') or back to the saved original ('restore')."""
import json, os, shutil, sys
P = os.path.join(os.environ["APPDATA"], "CampaignMapToolkit", "Caime", "preferences.json")
BK = r"Z:\Claude\TerryClone\output\backups\caime_preferences_before_upscale.json"
if sys.argv[1] == "set":
    d = json.load(open(P, encoding="utf-8-sig"))
    d["AssemblyKitPaths"]["Three_Kingdoms_AssKitPath"] = r"C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\assembly_kit_190E"
    json.dump(d, open(P, "w", encoding="utf-8"), indent=2)
else:
    shutil.copy2(BK, P)
print("CAIME 3K kit:", json.load(open(P, encoding="utf-8-sig"))["AssemblyKitPaths"]["Three_Kingdoms_AssKitPath"])
