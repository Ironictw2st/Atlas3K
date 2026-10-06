"""Lines of a native placement trace whose location contains all the given substrings (slashes either way).
usage: trace_grep.py <trace.tsv> <substring> [...]"""
import sys

BS = chr(92)
subs = [s.replace('/', BS).lower() for s in sys.argv[2:]]
for i, line in enumerate(open(sys.argv[1])):
    if all(s in line.lower() for s in subs): print(i, line.rstrip())
