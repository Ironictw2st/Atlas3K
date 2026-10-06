"""Print the unique element paths (with attribute names and counts) of BOB bmd debug XMLs. usage: skel.py <xml>..."""
import sys, collections
import xml.etree.ElementTree as ET
seen = collections.OrderedDict()
def walk(e, path):
    p = path + "/" + e.tag
    k = seen.setdefault(p, [0, list(e.attrib.keys()), bool((e.text or "").strip())])
    k[0] += 1
    for c in e: walk(c, p)
for f in sys.argv[1:]:
    walk(ET.parse(f).getroot(), "")
for p, (n, a, t) in seen.items():
    print(f"{n:6d} {p}  {' '.join(a)}{'  #text' if t else ''}")
