"""Compare body preambles (enum types, season codes) of matching entries in two global_props.bin files.
usage: preamble_compare.py <bob.bin> <native.bin>"""
import sys, collections
sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
from preambles import preambles

A, B = preambles(sys.argv[1]), preambles(sys.argv[2])
common = [n for n in A if n in B]
c = collections.Counter(); ex = []
for n in common:
    ta, sa, _ = A[n]; tb, sb, _ = B[n]
    tt = [t for t, _ in ta] == [t for t, _ in tb]; ss = sa == sb
    c[("types ok" if tt else "types differ", "seasons ok" if ss else "seasons differ")] += 1
    if (not tt or not ss) and len(ex) < 8: ex.append((n.split("bmd_objects.")[-1], [t for t, _ in ta], [t for t, _ in tb], sa, sb))
print(f"common bodies {len(common)}:", dict(c))
for e in ex: print("  ", e)
