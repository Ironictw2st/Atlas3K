"""compare_packs.py <test pack> <reference pack> <prefix>: which files of the test pack override the reference, and
which reference files under <prefix> the test pack leaves alone."""
import sys

sys.path.insert(0, r"Z:\Claude\TerryClone\tools\bob_mcp")
import packindex

test_pack, ref_pack, prefix = sys.argv[1], sys.argv[2], sys.argv[3].lower().replace('/', '\\')
ref = {e[0].lower() for e in packindex.index(ref_pack)}
test = [e[0].lower() for e in packindex.index(test_pack)]
print('test entries', len(test), '- also in reference:', sum(x in ref for x in test))
print('test-only:', [x for x in test if x not in ref][:10])
under = sorted(x for x in ref if x.startswith(prefix))
tset = set(test)
kept = [x for x in under if x not in tset]
print(f'reference files under {prefix}: {len(under)}, not replaced by the test pack: {len(kept)}')
for x in kept[:40]:
    print('   ', x)
