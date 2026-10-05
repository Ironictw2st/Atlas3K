#!/usr/bin/env python3
"""Hexi west zone for the terrain build (warp MODE "scale1.5w140", user 2026-10-01: map only, the other session's
corridor layout). Inside the zone (hexi_zone.npz: the 140-column west pad + corridor / Qilian / desert / lakes /
Xiping / the old Hexi land) lon/lat come from the Guzang-anchored projection (2.6 km/hex) instead of the rubber-sheet
georef, so dem_fill / class_fill paint the real corridor there. Both functions take 190E-source world coords
(the dem_fill / class_fill convention) and blend smoothly across a RAMP-hex seam."""
from pathlib import Path
import numpy as np
from scipy import ndimage as ndi
HERE = Path(__file__).parent
RAMP = 12                       # hexes: weight ramps 0 -> 1 over this distance into the zone
LAT_MIN = 34.0                  # deg: pad rows south of this are not in the zone

_Z = None


def _zone():
    global _Z
    if _Z is None:
        z = np.load(HERE / "research_r6" / "hexi_zone.npz")
        H_, W_ = z["corr"].shape
        rr = np.arange(H_)[:, None] * 0.772
        lat = float(z["anchor_lat"]) + (rr - float(z["zg"])) / (111.2 * float(z["kw"]))
        # the projection covers the Hexi / Xiping band only; the pad further south keeps the plain (rubber) padding
        cols = np.arange(W_)[None, :] * 0.668
        west = (cols <= float(z["xg"]) - 2 * 0.668) & (lat >= LAT_MIN)        # everything west of Guzang, north of 34N
        m = z["corr"] | z["qilian"] | z["desert"] | z["lakes"] | z["cleared"] | west
        m = ndi.binary_closing(m, iterations=3)
        d_in = ndi.distance_transform_edt(m)                       # hexes from the zone edge, inside
        wgt = np.clip(d_in / RAMP, 0, 1); wgt = wgt * wgt * (3 - 2 * wgt)
        from warp import current as _cur
        Hn = _cur().H
        if Hn > wgt.shape[0]:                     # north pad rows (added at the top, row 0 = south): continue the top row
            wgt = np.vstack([wgt, np.repeat(wgt[-1:], Hn - wgt.shape[0], 0)])
        _Z = dict(w=wgt.astype(np.float32), xg=float(z["xg"]), zg=float(z["zg"]), kw=float(z["kw"]), cl=float(z["cl"]),
                  lat0=float(z["anchor_lat"]), lon0=float(z["anchor_lon"]), H=int(wgt.shape[0]), W=int(z["W2"]), H0=int(z["h"]))
    return _Z


def _new_world(wx, wz):
    from warp import current
    W = current()
    nx, ny = W.forward(np.asarray(wx, float) / 0.668, np.asarray(wz, float) / 0.772)    # new hex units
    return nx, ny


def weight(wx, wz):
    """0..1: how much of the Hexi projection applies at 190E-source world (wx, wz).
    Bilinear between hex centres (2026-10-04, new_areas_lookover H1 root cause): the old nearest-hex lookup (np.rint)
    made the weight constant per hex, so to_lonlat jumped between two projections at every hex border of the RAMP band
    and the DEM came out as 1-px steps / waffles (Xiping, Longxi, Ordos). Only matters if the terrain chain is rerun;
    callers that threshold it (regions_carve6 / class_fill liang > 0.5) move by under half a hex at the zone edge."""
    Z = _zone(); nx, ny = _new_world(wx, wz)
    nx = np.clip(np.asarray(nx, float), 0, Z["W"] - 1); ny = np.clip(np.asarray(ny, float), 0, Z["H"] - 1)
    return ndi.map_coordinates(Z["w"], [ny.ravel(), nx.ravel()], order=1, mode="nearest").reshape(nx.shape)


def proj_lonlat(wx, wz):
    Z = _zone(); nx, ny = _new_world(wx, wz)
    x, z = nx * 0.668, ny * 0.772
    lon = Z["lon0"] + (x - Z["xg"]) / (Z["cl"] * 111.2 * Z["kw"])
    lat = Z["lat0"] + (z - Z["zg"]) / (111.2 * Z["kw"])
    return lon, lat


def to_lonlat(wx, wz):
    """rubber georef outside the zone, the Guzang projection inside, blended across the seam."""
    import rubber
    lo0, la0 = rubber.to_lonlat(wx, wz)
    w = weight(wx, wz)
    if not np.any(w > 0): return lo0, la0
    lo1, la1 = proj_lonlat(wx, wz)
    return lo0 * (1 - w) + lo1 * w, la0 * (1 - w) + la1 * w
