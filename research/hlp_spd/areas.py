import pickle, numpy as np
from esf_tree import find
def area_map(root, W, H):
    m = find(root, "MASKED_REGIONS_DATA")[0]
    a = [c for c in m[3][0] if c[0] == "ARR"][1][2]
    u = np.frombuffer(a, np.uint16)
    vals = np.repeat(u[0::2], u[1::2].astype(np.int64))
    assert len(vals) == W * H
    return vals.reshape(H, W)
def region_areas(root):
    out = []
    for rd in find(root, "REGION_DATA"):
        areas = []
        for g in [x for x in rd[3][0] if x[0] == "REC" and x[1] == "REGION_AREAS"][0][3]:
            ad = g[0]; v = [c[2] for c in ad[3][0] if c[0] == "VAL"]
            areas.append(dict(type=v[0], id=v[3], box=tuple(v[4:8]), centre=(v[8], v[9]), count=v[10]))
        si = [x for x in rd[3][0] if x[0] == "REC" and x[1] == "SETTLEMENT_INFO"]
        settle = None; slots = []
        if si:
            sv = [c[2] for c in si[0][3][0] if c[0] == "VAL"]
            if sv[0] != 0xFFFF: settle = (sv[0], sv[1])
            for name in ("PRIMARY_SLOT_AREA_BLOCK", "PORT_SLOT_AREA_BLOCK"):
                for blk in [x for x in si[0][3][0] if x[0] == "REC" and x[1] == name]:
                    for g in blk[3]: slots.append((g[0][2], g[1][2]))
        out.append(dict(areas=areas, settlement=settle, slots=slots))
    return out
