#!/usr/bin/env python3
"""Previews of candidate Central Plains warps on 190E's region map (1 px per hex, north up, towns as dots):
band (new Runan-Dongjun box), radial push-out, hybrid (uniform 1.3 + gentle bubble). Prints size and skew."""
import sys, numpy as np
from PIL import Image, ImageDraw
sys.path[:0] = ['.', '../guandu', '..']
from regions_plan import load
import warp as WP
from warp2 import RadialWarp, BOX

f, names, w, h = load('Z:/Claude/TerryClone/output/backups/main190_originals_20260929_130639/190Expanded_map.hex')
rng = np.random.default_rng(3); pal = rng.integers(70, 230, (len(names) + 2, 3)).astype(np.uint8)
reg = f['region']; sea = f['terr'] == 1
MARK = {n: None for n in ('3k_main_runan_capital', '3k_main_dongjun_capital', '3k_main_luoyang_capital', '3k_main_weijun_capital',
                          '3k_dlc06_xiapi_capital', '3k_main_changan_capital', '3k_main_youzhou_capital', '3k_main_jianye_capital')}
for n in MARK:
    m = (reg == names.index(n)) & (f['slot'] == 0); r, c = np.nonzero(m); MARK[n] = (c.mean(), r.mean())

def skew(W):
    ys, xs = np.mgrid[0:h:3, 0:w:3].astype(float); e = 0.5
    ax = (W.forward(xs + e, ys)[0] - W.forward(xs - e, ys)[0]) / (2 * e); ay = (W.forward(xs + e, ys)[1] - W.forward(xs - e, ys)[1]) / (2 * e)
    bx = (W.forward(xs, ys + e)[0] - W.forward(xs, ys - e)[0]) / (2 * e); by = (W.forward(xs, ys + e)[1] - W.forward(xs, ys - e)[1]) / (2 * e)
    s = np.linalg.svd(np.stack([np.stack([ax, bx], -1), np.stack([ay, by], -1)], -2), compute_uv=False)
    an = s[..., 0] / s[..., 1]; land = ~sea[ys.astype(int), xs.astype(int)]
    c0, c1, r0, r1 = BOX; out = land & ~((xs >= c0) & (xs <= c1) & (ys >= r0) & (ys <= r1))
    return np.mean(an[out] > 1.15), np.mean(an[out] > 1.3), an[out].max(), np.median(np.sqrt(s[..., 0] * s[..., 1])[out])

def render(W, path, title):
    NW, NH = W.W, W.H; rr, cc = np.mgrid[0:NH, 0:NW].astype(float)
    ox, oy = W.inverse(cc, rr); oc, orr = np.rint(ox).astype(int), np.rint(oy).astype(int)
    ok = (oc >= 0) & (oc < w) & (orr >= 0) & (orr < h)
    img = np.full((NH, NW, 3), (225, 215, 190), np.uint8)       # padding: parchment
    occ, orc = np.clip(oc, 0, w - 1), np.clip(orr, 0, h - 1)
    col = pal[np.clip(reg[orc, occ], 0, None)]; col[sea[orc, occ]] = (60, 90, 140)
    img[ok] = col[ok]
    edge = np.zeros((NH, NW), bool); rg = np.where(ok, reg[orc, occ], -9)
    edge[:, 1:] |= rg[:, 1:] != rg[:, :-1]; edge[1:] |= rg[1:] != rg[:-1]; img[edge & ok] = (30, 30, 30)
    im = Image.fromarray(img[::-1]); d = ImageDraw.Draw(im)
    for n, (c, r) in MARK.items():
        x, y = W.forward(c, r); x, y = float(x), NH - 1 - float(y)
        d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=(255, 255, 255), outline=(0, 0, 0))
        d.text((x + 7, y - 6), n.split('_')[-2], fill=(0, 0, 0))
    d.text((8, 8), title, fill=(0, 0, 0)); im.save(path)

WP.CX0, WP.CX1, WP.CY0, WP.CY1 = BOX                      # band with the new Runan-Dongjun box
cands = {"band": WP.Warp("band"), "pushout": RadialWarp(1.6, 1.0), "hybrid": RadialWarp(1.6, 1.3)}
for k, W in cands.items():
    a, b, mx, sc = skew(W)
    t = f"{k}: {W.W}x{W.H} hexes | land outside CP skewed >15%: {a:.0%}, >30%: {b:.0%} (max {mx:.2f}); typical size x{sc:.2f}"
    print(t); render(W, f"previews/warp_{k}.png", t)
