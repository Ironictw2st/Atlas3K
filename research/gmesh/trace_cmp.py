"""BOB's merger trace (frida_gmerge_trace.js) vs the native one (ATLAS3K_GMESH_TRACE): first differing line per call.
usage: trace_cmp.py <merge call> <native key>"""
import json, sys
JL = 'Z:/Claude/TerryClone/research/bob_re/frida_out/frida_gtrace_main190.jsonl'
call, key = int(sys.argv[1]), sys.argv[2]
bob = []
for l in open(JL, encoding='utf-8'):
    m = json.loads(l)
    if m.get('kind') == 'trace' and m.get('call') == call: bob += m['text'].split('\n')
nat = open(f'Z:/Claude/TerryClone/output/mesh_parity/gmesh_native_dump/{key}.trace.txt').read().split('\n')
print('bob lines', len(bob), 'native', len(nat)); print('bob head', bob[:3]); print('bob tail', bob[-3:])
b2 = [x for x in bob if x.startswith(('rem', 'cand', 'pass'))]
def norm(x):
    if x.startswith('pass'): p = x.split(); return f'pass {float(p[2]):.6g} tris {p[-1]}'
    return x
b2 = [norm(x) for x in b2]; n2 = [norm(x) for x in nat if x]
for i, (a, b) in enumerate(zip(b2, n2)):
    if a != b:
        print('first diff at line', i); print('  bob   ', a); print('  native', b)
        print('  context bob', b2[max(0, i - 3):i + 2]); print('  context nat', n2[max(0, i - 3):i + 2]); break
else:
    print('identical over', min(len(b2), len(n2)), 'lines')
