"""Survey the campaign tile hf maps extracted to research/trees/tile_hf (terrain2.pack terrain/tiles/campaign):
which tile sets carry a non-zero hf range (compressed map header lo/hi) and which use the old .data path."""
import collections, glob, os, struct
from pathlib import Path
HERE = Path(__file__).parent
rows = []
for p in glob.glob(str(HERE / "tile_hf/terrain/tiles/campaign/*/*/hf_height_map.compressed_map")):
    b = open(p, "rb").read(50); w, h = struct.unpack_from("<II", b, 10); hd = struct.unpack_from("<6f", b, 26)
    parts = Path(p).parts; rows.append((parts[-3], parts[-2], w, h, hd[1], hd[4]))
nz = [r for r in rows if r[4] != 0 or r[5] != 0]
print("compressed hf maps", len(rows), "with non-zero range", len(nz))
print("non-zero by set:", collections.Counter(r[0] for r in nz).most_common(25))
print("zero by set:", collections.Counter(r[0] for r in rows if not (r[4] or r[5])).most_common(25))
d = [Path(p).parts[-3] for p in glob.glob(str(HERE / "tile_hf/terrain/tiles/campaign/*/*/hf_height_map.data"))]
print(".data (old path) by set:", collections.Counter(d))
