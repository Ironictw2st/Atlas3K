"""Rebuild the Terry river splines (ECRiverSpline) from the finished, BOB-baked river meshes.

Calibrated against CA's example battle map, which ships both a river spline and the mesh BOB built from it
(CampaignMaps/Example/...407d7c83.../river_mesh.wsmodel.rigid_model_v2):
  - RMV2 v8, one group; 48-byte vertices: f32 x,y,z,1 | f32 v (across, -h..+h) | f32 u (0.1 * arc length from
    the spline start) | f32 world uv | packed normal/tangent/bitangent | 4 zero bytes.
  - Vertex x/z map linearly onto the group bounding box (1:1 on the campaign map, 2:1 on the battle example).
  - Spline segments are cubic Beziers: control points p + tangent_out and next + tangent_in (fits to 0.16 units).
  - Mesh edge-to-edge width equals the spline width (width 4 -> 4.03).
  - terrain_relative="false" makes the point y an absolute water height, so the baked height can be reproduced
    exactly without depending on the (already river-carved) low-frequency height map.
Flow speed, foam and alpha fade are not stored in the mesh; they are kept from the existing layer.

usage: rivers_from_meshes.py <models dir> <existing rivers .layer> <output .layer>
"""
import struct
import sys
import numpy as np
import xml.etree.ElementTree as ET

U_PER_UNIT = 0.1          # u advances 0.1 per world unit of arc length
MAX_CENTRE_ERROR = 0.2    # knot refinement target (vertex positions are quantised to 1/8 unit)
MAX_WIDTH_SHORTFALL = 0.15  # refine until the interpolated width is at most this much narrower than the mesh


def read_river_mesh(path):
    """Return world-space vertices as rows (x, y, z, v, u)."""
    b = open(path, "rb").read()
    assert b[:4] == b"RMV2", path
    g = 0xA8
    _, _, voff, vc, ioff, _ = struct.unpack("<6I", b[g:g + 24])
    mn = np.array(struct.unpack("<3f", b[g + 24:g + 36]))
    mx = np.array(struct.unpack("<3f", b[g + 36:g + 48]))
    stride = (ioff - voff) // vc
    raw = np.frombuffer(b[g + voff:g + voff + vc * stride], np.uint8).reshape(vc, stride)
    f = raw[:, :24].copy().view("<f4").astype(np.float64)
    out = np.empty((vc, 5))
    for a in (0, 2):
        lo, hi = f[:, a].min(), f[:, a].max()
        out[:, a] = mn[a] + (f[:, a] - lo) / (hi - lo) * (mx[a] - mn[a]) if hi > lo else f[:, a]
    out[:, 1] = f[:, 1] + (mn[1] + mx[1]) / 2 - (f[:, 1].min() + f[:, 1].max()) / 2
    out[:, 3] = f[:, 4]
    out[:, 4] = f[:, 5]
    return out


def cross_sections(verts):
    """One row per distinct u: (arc length, centre x, y, z, width), sorted along the river."""
    rows = []
    u = np.round(verts[:, 4], 4)
    for k in np.unique(u):
        s = verts[u == k]
        s = s[np.argsort(s[:, 3])]
        a, b = s[0, :3], s[-1, :3]
        if np.allclose(a, b):
            continue
        rows.append((k / U_PER_UNIT, *((a + b) / 2), np.hypot(a[0] - b[0], a[2] - b[2])))
    return np.array(rows)


def smooth(s, values, sigma):
    """Gaussian smoothing over arc length (sections are uneven: dense on bends, sparse on straights).
    The end points stay put so the river still reaches its junctions."""
    out = values.copy()
    for i in range(1, len(s) - 1):
        w = np.exp(-0.5 * ((s - s[i]) / sigma) ** 2)
        out[i] = (w * values).sum() / w.sum()
    return out


def bezier(p0, c1, c2, p3, t):
    t = t[:, None]
    return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * c1 + 3 * (1 - t) * t * t * c2 + t ** 3 * p3


def build_knots(sec, idx):
    """Knot positions, symmetric Bezier tangents (Terry stores tangent_in = -tangent_out) and widths."""
    s = sec[:, 0]
    P = sec[idx, 1:4]
    tangents = np.zeros_like(P)
    for i in range(len(idx)):
        prev, nxt = P[max(i - 1, 0)], P[min(i + 1, len(idx) - 1)]
        d = nxt - prev
        n = np.linalg.norm(d[[0, 2]])
        if n == 0:
            continue
        d = d / n
        # handle length: a third of the shorter neighbouring chord keeps the curve from overshooting
        chords = [np.linalg.norm((P[j] - P[i])[[0, 2]]) for j in (i - 1, i + 1) if 0 <= j < len(idx)]
        tangents[i] = d * min(chords) / 3
    # the largest width in the knot's immediate neighbourhood: a mesh slightly too wide only overlaps the bank,
    # while one too narrow leaves the land-mesh river hole showing through (widths carry +-1/8 grid noise)
    widths = np.array([sec[max(j - 1, 0):j + 2, 4].max() for j in idx])
    return P, tangents, widths, s[idx]


def width_error(sec, idx, W):
    """Per segment: the worst shortfall of the linearly interpolated spline width against the mesh width."""
    s = sec[:, 0]
    out = []
    for k, (a, b) in enumerate(zip(idx, idx[1:])):
        interp = np.interp(s[a:b + 1], [s[a], s[b]], [W[k], W[k + 1]])
        out.append((sec[a:b + 1, 4] - interp).max())
    return out


def evaluate(P, T, n=80):
    pts = []
    for i in range(len(P) - 1):
        pts.append(bezier(P[i], P[i] + T[i], P[i + 1] - T[i + 1], P[i + 1], np.linspace(0, 1, n, endpoint=False)))
    pts.append(P[-1:])
    return np.vstack(pts)


def xz_distance(a, b):
    return np.hypot(a[:, None, 0] - b[None, :, 0], a[:, None, 2] - b[None, :, 2]).min(1)


def fit_river(sec):
    # vertex positions are quantised to 1/8 unit; smooth the centreline before fitting
    s = sec[:, 0]
    for col in (1, 2, 3):
        sec[:, col] = smooth(s, sec[:, col], 0.5)
    # start with a knot every ~8 units of arc, then split any segment whose fit is poor
    idx = sorted({0, len(s) - 1, *np.searchsorted(s, np.arange(0, s[-1], 8.0)).tolist()})
    idx = [i for i in idx if i < len(s)]
    for _ in range(16):
        P, T, W, _ = build_knots(sec, idx)
        worst = []
        werr = width_error(sec, idx, W)
        for k, (a, b) in enumerate(zip(idx, idx[1:])):
            seg = sec[a:b + 1, 1:4]
            curve = bezier(P[k], P[k] + T[k], P[k + 1] - T[k + 1], P[k + 1], np.linspace(0, 1, 60))
            err = xz_distance(seg, curve).max()
            if b - a < 2:
                continue
            if err > MAX_CENTRE_ERROR:
                worst.append((a + b) // 2)
            elif werr[k] > MAX_WIDTH_SHORTFALL:
                # split where the width is furthest above the interpolation
                s = sec[:, 0]
                interp = np.interp(s[a:b + 1], [s[a], s[b]], [W[k], W[k + 1]])
                worst.append(a + 1 + int(np.argmax((sec[a:b + 1, 4] - interp)[1:-1])))
        if not worst:
            break
        idx = sorted(set(idx) | set(worst))
    return build_knots(sec, idx)


def fmt(v):
    return ",".join(f"{x:.6g}" for x in v)


def main(models_dir, layer_in, layer_out):
    tree = ET.parse(layer_in)
    report = []
    for e in tree.getroot().iter("entity"):
        spline_el = e.find("ECRiverSpline")
        if spline_el is None:
            continue
        name = e.get("name")
        verts = read_river_mesh(f"{models_dir}/{name}.wsmodel.rigid_model_v2")
        raw = cross_sections(verts)
        P, T, W, _ = fit_river(raw.copy())

        old = spline_el.find("spline").find("point")
        keep = {k: old.get(k) for k in ("alpha_fade", "flow_speed", "foam_amount")}
        # CA's example keeps the entity at y=0 and puts the absolute water height in each point, so the result
        # doesn't depend on whether Terry adds the entity y to terrain_relative="false" points.
        origin = np.array([P[0][0], 0.0, P[0][2]])

        e.find("ECTransform").set("position", " ".join(f"{x:.6g}" for x in origin))
        spline_el.set("terrain_relative", "false")
        spline_el.set("reverse_direction", "false")
        sp = spline_el.find("spline")
        for p in list(sp):
            sp.remove(p)
        for i, (p, t, w) in enumerate(zip(P, T, W)):
            ET.SubElement(sp, "point", {
                "position": fmt(p - origin),
                "tangent_in": fmt(-t if i > 0 else np.zeros(3)),
                "tangent_out": fmt(t),
                "width": f"{w:.3g}",
                "terrain_offset": "0",
                **keep,
            })

        # validate against the raw (unsmoothed) mesh
        curve = evaluate(P, T)
        d = np.hypot(raw[:, None, 1] - curve[None, :, 0], raw[:, None, 3] - curve[None, :, 2])
        centre_err = d.min(1)
        y_err = np.abs(curve[d.argmin(1), 1] - raw[:, 2])
        vert_cover = xz_distance(verts[:, :3], curve)
        knot_s = np.array([raw[np.argmin(np.hypot(raw[:, 1] - p[0], raw[:, 3] - p[2])), 0] for p in P])
        width_short = (raw[:, 4] - np.interp(raw[:, 0], knot_s, W)).max()
        report.append((name, len(P), raw[-1, 0], np.median(W), np.median(centre_err), centre_err.max(),
                       vert_cover.max(), y_err.max(), width_short))

    ET.indent(tree, "  ")
    body = ET.tostring(tree.getroot(), encoding="unicode").replace(" />", "/>")  # Terry's self-closing style
    with open(layer_out, "w", encoding="utf-8", newline="\n") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n' + body + "\n")
    print(f"{'river':9s} knots  length  width  centre err med/max  max vert->centre  max y err  width shortfall")
    for n, k, L, w, med, mx, cov, yerr, ws in sorted(report, key=lambda r: int(r[0].split("_")[1])):
        print(f"{n:9s} {k:5d} {L:7.1f} {w:6.2f}   {med:6.3f} {mx:6.3f}      {cov:6.2f}          {yerr:6.3f}     {ws:6.3f}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
