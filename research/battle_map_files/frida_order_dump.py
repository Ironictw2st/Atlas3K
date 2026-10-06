"""Print BOB's database order and pass candidate orders (frida_tilemap.js output) around a name filter.
usage: frida_order_dump.py <jsonl> [kind] [pass] [grep]"""
import json, sys

rows = [json.loads(l) for l in open(sys.argv[1])]
kind = sys.argv[2] if len(sys.argv) > 2 else 'sort_after'
pas = int(sys.argv[3]) if len(sys.argv) > 3 else 0
grep = sys.argv[4] if len(sys.argv) > 4 else ''
for r in rows:
    if r['kind'] != kind or (kind.startswith('sort') and r.get('pass') != pas): continue
    print(kind, 'pass', r.get('pass'), len(r['tiles']))
    for i, t in enumerate(r['tiles']):
        if grep in t: print(' ', i, t)
    break
