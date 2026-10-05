import re, os, glob, sys
K = r"C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\assembly_kit\binaries"
rx = re.compile(sys.argv[1], re.I)
pat = re.compile(rb'[\x20-\x7e]{6,}')
for f in glob.glob(K + r"\*.dll"):
    b = open(f, 'rb').read()
    hits = sorted({m.group().decode() for m in pat.finditer(b) if rx.search(m.group().decode())})
    if hits:
        print('==', os.path.basename(f), len(hits))
        for h in hits[:int(sys.argv[2]) if len(sys.argv) > 2 else 60]:
            print('  ', h[:240])
