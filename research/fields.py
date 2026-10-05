import sys
import numpy as np
from hexmap import load, HEX_DIR

m = load(HEX_DIR + r"\map.hex")
rec = m["rec"]
w0, w1, w2, w3 = (rec[..., i] for i in range(4))


def field(w, lo, n):
    return (w >> lo) & ((1 << n) - 1)


def hist(name, v, labels=None):
    u, c = np.unique(v, return_counts=True)
    print(f"== {name}: {len(u)} values")
    for a, b in list(zip(u, c))[:40]:
        lab = labels[a] if labels is not None and 0 <= a < len(labels) else ""
        print(f"   {a:6d} {b:8d} {lab}")


region = field(w0, 3, 9)
allreg = m["lists"]["land_regions"] + m["lists"]["sea_regions"]
print("region range", region.min(), region.max(), "n regions", len(allreg))
bit0 = field(w0, 0, 1); bit19 = field(w0, 19, 1)
print("bit0 vs region is sea:")
is_sea_reg = region > len(m["lists"]["land_regions"])
for a in (0, 1):
    for b in (0, 1):
        print(f"  bit0={a} bit19={b}: n={((bit0==a)&(bit19==b)).sum()}  sea_reg={(is_sea_reg&(bit0==a)&(bit19==b)).sum()}  region0={((region==0)&(bit0==a)&(bit19==b)).sum()}")
hist("w0 bit1", field(w0, 1, 1)); hist("w0 bit2", field(w0, 2, 1))
hist("w0 12-18", field(w0, 12, 7)); hist("w0 20-23", field(w0, 20, 4))
hist("w0 24-31", field(w0, 24, 8))
types = m["lists"]["ground_types"] + m["lists"]["water_types"]
hist("w1 12-16 (ground+water?)", field(w1, 12, 5), types)
hist("w1 17-24", field(w1, 17, 8))
hist("w1 25-27 climate?", field(w1, 25, 3), m["lists"]["climates"])
hist("w1 28-31", field(w1, 28, 4))
hist("w1 0-5", field(w1, 0, 6)); hist("w1 6-11", field(w1, 6, 6))
hist("w2 full", w2)
hist("w3 0-25", field(w3, 0, 26)); hist("w3 26-31", field(w3, 26, 6))
