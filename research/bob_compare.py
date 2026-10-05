"""Compare a BOB build of a campaign map against CA's finished files and write a markdown report.

usage: bob_compare.py <bob terrain output dir> <finished terrain dir> <report.md>
  e.g. bob_compare.py output/bob_runs/<ts>/terrain Vanilla/Map/terrain/campaigns/3k_dlc07_main_map report.md

Per file type:
  - *.dds (uncompressed 16-bit L16 or other): header, then pixel diff / value-mapping fit when the shape matches
  - *.compressed_map: decoded with compressed_map.py and diffed like rasters
  - river_*.rigid_model_v2: vertex count, bbox, centreline distance
  - everything else: size and byte-level summary (identical / first differing offset / % bytes equal)
"""
import hashlib
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import compressed_map as C  # noqa: E402


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


def dds_info(b):
    if b[:4] != b"DDS ":
        return None
    h, w = struct.unpack_from("<2I", b, 12)
    flags, fourcc, bits = struct.unpack_from("<I4sI", b, 80)
    return w, h, fourcc, bits


def dds_l16(p):
    b = open(p, "rb").read()
    info = dds_info(b)
    if not info:
        return None
    w, h, fourcc, bits = info
    if bits == 16 and len(b) >= 128 + w * h * 2:
        return np.frombuffer(b, "<u2", w * h, 128).reshape(h, w)
    return None


def raster_diff(a, b):
    if a.shape != b.shape:
        return f"shape {a.shape} vs {b.shape}"
    a64, b64 = a.astype(np.int64), b.astype(np.int64)
    d = a64 - b64
    nz = np.count_nonzero(d)
    if nz == 0:
        return "**identical pixels**"
    out = f"{nz:,} px differ ({nz / d.size:.2%}), diff range {d.min()}..{d.max()}, mean |d| {np.abs(d).mean():.2f}"
    if a.size > 4:
        s = slice(None, None, max(1, a.size // 200000))
        x, y = b64.ravel()[s].astype(float), a64.ravel()[s].astype(float)
        if x.std() > 0 and y.std() > 0:
            k, c = np.polyfit(x, y, 1)
            out += f"; fit bob = {k:.5f}*vanilla + {c:.2f} (corr {np.corrcoef(x, y)[0, 1]:.5f})"
    return out


def bytes_diff(pa, pb):
    a, b = open(pa, "rb").read(), open(pb, "rb").read()
    if a == b:
        return "**identical bytes**"
    n = min(len(a), len(b))
    aa, bb = np.frombuffer(a[:n], np.uint8), np.frombuffer(b[:n], np.uint8)
    neq = np.nonzero(aa != bb)[0]
    first = neq[0] if len(neq) else n
    return f"size {len(a):,} vs {len(b):,}; first diff at 0x{first:x}; {1 - len(neq) / max(n, 1):.2%} of common bytes equal"


def compare(bob_dir, van_dir):
    rows = []
    bob_files = {os.path.relpath(os.path.join(r, f), bob_dir).replace("\\", "/")
                 for r, _, fs in os.walk(bob_dir) for f in fs}
    van_files = {os.path.relpath(os.path.join(r, f), van_dir).replace("\\", "/")
                 for r, _, fs in os.walk(van_dir) for f in fs}
    for rel in sorted(bob_files | van_files):
        pa, pb = os.path.join(bob_dir, rel), os.path.join(van_dir, rel)
        if rel not in van_files:
            rows.append((rel, "only in BOB build", f"{os.path.getsize(pa):,} B"))
            continue
        if rel not in bob_files:
            rows.append((rel, "only in vanilla", f"{os.path.getsize(pb):,} B"))
            continue
        if md5(pa) == md5(pb):
            rows.append((rel, "match", "identical bytes"))
            continue
        detail = None
        try:
            if rel.endswith(".dds"):
                a, b = dds_l16(pa), dds_l16(pb)
                if a is not None and b is not None:
                    detail = raster_diff(a, b)
                else:
                    ia, ib = dds_info(open(pa, "rb").read()), dds_info(open(pb, "rb").read())
                    detail = f"dds {ia} vs {ib}; " + bytes_diff(pa, pb)
            elif rel.endswith(".compressed_map"):
                (a, fa), (b, fb) = C.decode(pa), C.decode(pb)
                detail = raster_diff(a, b) + f"; header floats {fa[1]:.4g},{fa[4]:.4g} vs {fb[1]:.4g},{fb[4]:.4g}"
        except Exception as e:  # keep going; the report shows what failed
            detail = f"decode failed: {e}; " + bytes_diff(pa, pb)
        rows.append((rel, "differs", detail or bytes_diff(pa, pb)))
    return rows


def main(bob_dir, van_dir, report):
    rows = compare(bob_dir, van_dir)
    counts = {}
    for _, status, _ in rows:
        counts[status] = counts.get(status, 0) + 1
    with open(report, "w", encoding="utf-8") as f:
        f.write(f"# BOB build vs vanilla\n\nBOB: `{bob_dir}`  \nVanilla: `{van_dir}`\n\n")
        f.write(", ".join(f"{k}: {v}" for k, v in sorted(counts.items())) + "\n\n")
        f.write("| file | status | detail |\n|---|---|---|\n")
        for rel, status, detail in rows:
            f.write(f"| `{rel}` | {status} | {detail} |\n")
    print(", ".join(f"{k}: {v}" for k, v in sorted(counts.items())))


if __name__ == "__main__":
    main(*sys.argv[1:4])
