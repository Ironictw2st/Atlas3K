"""Summarise CAIME tool.log lines from line N on: count by level + message template (hex coords stripped)."""
import re, sys, collections
lines = open(r"Z:/CAIME/CAIME/tool.log", encoding="utf-8", errors="replace").read().splitlines()[int(sys.argv[1]):]
c = collections.Counter(); ex = {}
for l in lines:
    if re.search(r"Auto Saves|Auto Backups|Saved map_|successfully saved|Backup finished", l): continue
    t = re.sub(r"Hex\(\d+, \d+\)", "Hex(*)", l); t = re.sub(r"\d+", "#", t)
    c[t] += 1; ex.setdefault(t, l)
for t, n in c.most_common(40): print(f"{n:6d}  {ex[t][:220]}")
