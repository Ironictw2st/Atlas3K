"""Compare BOB's database / pass orders (frida_tilemap.js jsonl) with the native ones (<trace>.db, <trace>.passN).
usage: order_cmp.py <frida jsonl> <trace prefix>"""
import json, sys

rows = [json.loads(l) for l in open(sys.argv[1])]
pre = sys.argv[2]
f = lambda s: s.split('|')[0].lower()
n = lambda s: s.split(' ')[0].lower()
db = next(r for r in rows if r['kind'] == 'db_after')
mine = [n(l) for l in open(pre + '.db')]
bob = [f(t) for t in db['tiles']]
first = next((i for i, (a, b) in enumerate(zip(bob, mine)) if a != b), None)
print('db', len(bob), len(mine), 'first diff', first)
if first is not None:
    for i in range(first, first + 6): print('  ', i, bob[i], '|', mine[i])
before = next(r for r in rows if r['kind'] == 'db_before')
print('db_before first 5:', [f(t) for t in before['tiles'][:5]])
for p in range(6):
    r = next((r for r in rows if r['kind'] in ('sort_after', 'sort_junction_after') and r['pass'] == p), None)
    if r is None: continue
    bob = [f(t) for t in r['tiles']]
    mine = [n(l) for l in open(pre + f'.pass{p}')]
    first = next((i for i, (a, b) in enumerate(zip(bob, mine)) if a != b), None)
    print('pass', p, len(bob), len(mine), 'first diff', first)
    if first is not None:
        for i in range(first, min(first + 5, len(bob), len(mine))): print('  ', i, bob[i], '|', mine[i])
