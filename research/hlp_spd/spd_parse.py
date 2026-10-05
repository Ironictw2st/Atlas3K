"""Parse spd_data.esf (CAI_SIMPLE_PATH_DIRECTORY): header (x0,y0,x1,y1,unk), grid of 16-value entries, landmarks."""
import sys
import numpy as np
from esf_flat import header, tokens


def parse(path):
    b = open(path, "rb").read()
    h = header(b)
    toks, _ = tokens(b, h["body"], h["end"])
    x0, y0, x1, y1, unk = [v for _, _, v in toks[:5]]
    W, H = x1 - x0 + 1, y1 - y0 + 1
    i = 5
    grid = np.zeros((H * W, 16), dtype=np.uint32)
    types = np.zeros((H * W, 16), dtype=np.uint8)
    for c in range(W * H):
        assert toks[i][2] == 16
        for k in range(16):
            grid[c, k] = toks[i + 1 + k][2]
            types[c, k] = toks[i + 1 + k][1]
        i += 17
    n = toks[i][2]; i += 1
    lm = [(toks[i + 2 * k][2], toks[i + 2 * k + 1][2]) for k in range(n)]
    i += 2 * n
    assert i == len(toks), (i, len(toks))
    return dict(x0=x0, y0=y0, x1=x1, y1=y1, unk=unk, W=W, H=H, grid=grid.reshape(H, W, 16),
                types=types.reshape(H, W, 16), landmarks=lm, header=h)


if __name__ == "__main__":
    d = parse(sys.argv[1])
    print({k: d[k] for k in ("x0", "y0", "x1", "y1", "unk", "W", "H", "landmarks")})
