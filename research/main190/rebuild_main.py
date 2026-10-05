#!/usr/bin/env python3
"""Build the warped 190E map.hex: the warp in warp.current() (round 6: north x1.4), +west (Hexi) and +north (Xianbei) padding.
Uses research/guandu/rebuild_hex.rebuild with a mapping (same pipeline as Guandu: world sampling, settlements at
original size, redrawn lines, one-ring coast, region clean-up, region edges). Output: research/main190/hex/map.hex
(+ map_prekorea.hex); run korea_fix.py afterwards."""
import sys
from pathlib import Path
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "guandu")); sys.path.insert(0, str(HERE.parent))
from warp import Warp, WarpMapping, current
import rebuild_hex
from trade_rebuild import rebuild as trade_rebuild

SRC = r"Z:/Claude/190Expanded/campaign_maps/map.hex"

if __name__ == "__main__":
    m = WarpMapping(Warp(sys.argv[1]) if len(sys.argv) > 1 else current())      # default: warp.MODE
    # new land (padding) takes land/sea from the DEM (rubber-sheet georef) - round 6: the north x1.4 warp opens
    # southern corners (Gulf of Tonkin, South China Sea, Burma) where edge extrusion would put land on sea
    import numpy as np
    from dem_fill import mosaic, sample
    mos = mosaic()
    def padding_sea(xo, zo):
        v = sample(mos, xo, zo); return np.where(np.isfinite(v), (v <= 0).astype(int), -1)
    res, (w, h) = rebuild_hex.rebuild(name="3k_dlc07_main_map", src_path=SRC, mapping=m, crop=False, guandu_drops=False,
                                      fill_holes=True, padding_sea=padding_sea)
    res = trade_rebuild(res)                                  # clean trade graph (CAIME hangs on rebuild_hex's)
    out = HERE / "hex"; out.mkdir(exist_ok=True)
    (out / "map.hex").write_bytes(res)
    (out / "map_prekorea.hex").write_bytes(res)            # korea_fix.py's input (it rewrites map.hex from this)
    print(f"{w}x{h} -> {out / 'map.hex'} ({len(res):,} bytes)")
