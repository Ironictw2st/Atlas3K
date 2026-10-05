"""Dump campaign tile-database entries (FASTBIN0) from the game packs: per tile the header fields up to the variation
list and the tail bytes, to locate use_alt_lf. usage: tile_bins.py [substring]"""
import glob, os, sys, struct
sys.path.insert(0, r"Z:\Claude\TerryClone\tools\bob_mcp")
import packindex
D = r"C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\data"
want = sys.argv[1] if len(sys.argv) > 1 else ''


def entries():
    seen = set()
    for pack in sorted(glob.glob(os.path.join(D, "*.pack"))):
        try: es = packindex.index(pack)
        except Exception: continue
        for e in es:
            k = e[0].lower().replace(chr(92), '/')
            if '_tile_database/tiles/' in k and 'campaign' in k and k not in seen:
                seen.add(k); yield k, packindex.read(pack, e)


if __name__ == "__main__":
    for k, b in entries():
        if want and want not in k: continue
        ver = struct.unpack_from('<H', b, 8)[0]
        print(k, 'ver', ver, 'len', len(b))
        print('  head', b[:120].hex(' '))
        print('  tail', b[-48:].hex(' '))
