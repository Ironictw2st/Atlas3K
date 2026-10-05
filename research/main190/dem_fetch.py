#!/usr/bin/env python3
"""Fetch the Copernicus GLO-90 DEM tiles the current warp needs (padding + the Liang/Hexi zone) into dem/.

Tiles: s3 bucket copernicus-dem-90m (public, anonymous HTTPS). A 404 is open ocean (no tile) and is recorded in
dem/missing.txt, which dem_fill.mosaic() reads as sea. usage: dem_fetch.py   (reads the tile list it computes)
"""
import os, sys, glob, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
for p in (HERE, os.path.join(HERE, "..", "guandu"), os.path.join(HERE, "..")): sys.path.insert(0, p)
DEM = os.path.join(HERE, "dem")
URL = "https://copernicus-dem-90m.s3.amazonaws.com/{n}/{n}.tif"


def name(lat, lon):
    return f"Copernicus_DSM_COG_30_{'N' if lat >= 0 else 'S'}{abs(lat):02d}_00_{'E' if lon >= 0 else 'W'}{abs(lon):03d}_00_DEM"


def needed():
    from warp import current, WarpMapping
    import rubber
    from hexgrid import centre
    from dem_fill import liang_weight
    W = current(); m = WarpMapping(W)
    rr, cc = np.mgrid[0:W.H:2, 0:W.W:2]; x, z = centre(cc, rr); xo, zo = m.inv_world(x, z)
    outside = (xo < -0.668) | (xo > 892 * 0.668) | (zo < -0.772) | (zo > 702 * 0.772)
    need = outside | (liang_weight(xo, zo) > 0.01)
    lon, lat = rubber.to_lonlat(xo[need], zo[need])
    return sorted({(int(a), int(b)) for a, b in zip(np.floor(lat), np.floor(lon))})


def have():
    h = set()
    for f in glob.glob(os.path.join(DEM, "*.tif")):
        b = os.path.basename(f).split("_"); h.add((int(b[4][1:]), int(b[6][1:])))
    for line in open(os.path.join(DEM, "missing.txt")):
        b = line.split()[0].split("_"); h.add((int(b[4][1:]), int(b[6][1:])))
    return h


def fetch(t):
    n = name(*t); dst = os.path.join(DEM, n + ".tif")
    try:
        with urllib.request.urlopen(URL.format(n=n), timeout=120) as r: data = r.read()
        open(dst + ".part", "wb").write(data); os.replace(dst + ".part", dst); return n, len(data)
    except urllib.error.HTTPError as e:
        return n, -e.code


if __name__ == "__main__":
    todo = [t for t in needed() if t not in have()]
    print(f"{len(todo)} tiles to fetch")
    miss, got, size = [], 0, 0
    with ThreadPoolExecutor(8) as ex:
        for n, s in ex.map(fetch, todo):
            if s == -404: miss.append(n)
            elif s < 0: print("error", n, s)
            else: got += 1; size += s
    with open(os.path.join(DEM, "missing.txt"), "a") as f:
        for n in miss: f.write(f"{n} 404\n")
    print(f"downloaded {got} tiles ({size / 1e6:.0f} MB), {len(miss)} ocean (404)")
