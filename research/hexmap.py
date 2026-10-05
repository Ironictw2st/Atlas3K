"""Research parser for 3K map.hex (Twitch) files. Mirrors the C# HexMap reader."""
import struct, sys
import numpy as np

AK = r"C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\assembly_kit_190E"
HEX_DIR = AK + r"\raw_data\EmpireDesignData\campaign_maps\3k_dlc07_main_map"

LIST_NAMES = ["land_regions", "sea_regions", "ground_types", "water_types",
              "climates", "attrition", "areas_of_interest"]


class R:
    def __init__(self, b):
        self.b, self.p = b, 0

    def u32(self):
        v = struct.unpack_from("<I", self.b, self.p)[0]; self.p += 4; return v

    def s(self):
        n = self.u32(); v = self.b[self.p:self.p + n]; self.p += n
        return v.decode("utf-8", "replace")


def load(path):
    b = open(path, "rb").read()
    r = R(b)
    hdr = [r.u32() for _ in range(4)]
    game, mapname = r.s(), r.s()
    lists = {}
    for name in LIST_NAMES:
        lists[name] = [r.s() for _ in range(r.u32())]
    tables = []
    for _ in range(2):
        n = r.u32()
        tables.append(np.frombuffer(b, np.uint8, n * 4, r.p).reshape(n, 4)); r.p += n * 4
    w, h = r.u32(), r.u32()
    rec = np.frombuffer(b, "<u4", w * h * 4, r.p).reshape(h, w, 4); r.p += w * h * 16
    trailer = b[r.p:]
    return dict(hdr=hdr, game=game, map=mapname, lists=lists, tables=tables,
                w=w, h=h, rec=rec, trailer=trailer, body_off=r.p - w * h * 16)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else HEX_DIR + r"\map.hex"
    m = load(path)
    print("hdr", m["hdr"], m["game"], m["map"], "grid", m["w"], m["h"], "trailer", m["trailer"].hex())
    for k, v in m["lists"].items():
        print(k, len(v), v[:8])
    for i, t in enumerate(m["tables"]):
        print("table", i, len(t), t[:6].tolist())
    rec = m["rec"]
    for word in range(4):
        col = rec[..., word].ravel()
        print(f"--- word {word}: unique={len(np.unique(col))}")
        for bit in range(32):
            f = ((col >> bit) & 1).mean()
            if f > 0:
                print(f"  bit {bit:2d}: {f:.4f}")
