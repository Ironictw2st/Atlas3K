import numpy as np, sys
sys.path.insert(0, '..')
import hexmap
def load_slots(path):
    m = hexmap.load(path)
    b = m["rec"].view(np.uint8).reshape(m["h"], m["w"], 16)
    slot = (b[:, :, 2] >> 4).astype(int) - 1
    region = ((b[:, :, 0] >> 3) & 0x1f).astype(int) | (b[:, :, 1].astype(int) << 5)
    return slot, region, b
