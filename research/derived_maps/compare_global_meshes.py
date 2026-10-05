"""Compare native global meshes with vanilla: tile position per number, triangle counts, covered area overlap,
max height difference against vanilla's surface at shared grid points."""
import glob
import re
import struct
import sys

import numpy as np

VAN = r"Z:\Claude\TerryClone\Vanilla\Map\terrain\campaigns\3k_dlc07_main_map\global_meshes"
OURS = sys.argv[1] if len(sys.argv) > 1 else r"Z:\Claude\TerryClone\output\native_build_test\terrain\campaigns\3k_dlc07_main_map\global_meshes"
CELL = 595.1 / 3568


def read(path):
    b = open(path, 'rb').read()
    vc, = struct.unpack_from('<I', b, 0xB4)
    io, ic = struct.unpack_from('<II', b, 0xB8)
    bb = struct.unpack_from('<6f', b, 0xC0)
    v = np.frombuffer(b, '<f4', count=vc * 4, offset=0x150).reshape(-1, 4)[:, :3].astype(np.float64)
    idx = np.frombuffer(b, '<u2', count=ic, offset=0xA8 + io).reshape(-1, 3)
    p = v[idx]
    area = (p[:, 1, 0] - p[:, 0, 0]) * (p[:, 2, 2] - p[:, 0, 2]) - (p[:, 2, 0] - p[:, 0, 0]) * (p[:, 1, 2] - p[:, 0, 2])
    return v, idx, bb, np.abs(area) > 1e-9


def coverage(v, idx, surf, bb):
    gi = np.round((v[:, 0] - bb[0]) / CELL).astype(int); gj = np.round((v[:, 2] - bb[2]) / CELL).astype(int)
    cov = np.zeros((224, 224), bool); hgt = np.full((224, 224), np.nan)
    for t in idx[surf]:
        a, b, c = t
        ia, ib, ic_ = gi[t]; ja, jb, jc = gj[t]
        d = (ib - ia) * (jc - ja) - (ic_ - ia) * (jb - ja)
        for j in range(min(ja, jb, jc), max(ja, jb, jc)):
            for i in range(min(ia, ib, ic_), max(ia, ib, ic_)):
                ci, cj = i + 0.5, j + 0.5
                u = ((ib - ci) * (jc - cj) - (ic_ - ci) * (jb - cj)) / d
                w = ((ic_ - ci) * (ja - cj) - (ia - ci) * (jc - cj)) / d
                if u >= -1e-9 and w >= -1e-9 and 1 - u - w >= -1e-9:
                    cov[j, i] = True
                    hgt[j, i] = u * v[a, 1] + w * v[b, 1] + (1 - u - w) * v[c, 1]
    return cov, hgt


for kind in ('land', 'sea'):
    files = sorted(glob.glob(VAN + rf"\{kind}_mesh_*.rigid_model_v2"), key=lambda f: int(re.search(r'_(\d+)\.rigid', f).group(1)))
    same_pos = 0; tri_v = tri_o = 0; iou = []; hmax = []
    for f in files:
        n = int(re.search(r'_(\d+)\.rigid', f).group(1))
        o = OURS + rf"\{kind}_mesh_{n}.rigid_model_v2"
        vv, iv, bv, sv = read(f)
        vo, io_, bo, so = read(o)
        same_pos += abs(bv[0] - bo[0]) < 1e-3 and abs(bv[2] - bo[2]) < 1e-3
        tri_v += int(sv.sum()); tri_o += int(so.sum())
        if n % 10 == 0:
            cv, hv = coverage(vv, iv, sv, bv); co, ho = coverage(vo, io_, so, bo)
            inter = (cv & co).sum(); union = (cv | co).sum()
            iou.append(inter / max(union, 1))
            both = cv & co
            if both.any(): hmax.append(np.nanmax(np.abs(hv[both] - ho[both])))
    print(f'{kind}: {len(files)} meshes, same tile position {same_pos}; surface triangles vanilla {tri_v} ours {tri_o} '
          f'({tri_o / tri_v:.2f}x); sampled coverage IoU mean {np.mean(iou):.4f} min {np.min(iou):.4f}; '
          f'max |height diff| median {np.median(hmax):.3f} max {np.max(hmax):.3f}')
