"""Sizes of the tile / climate maps in a kit map folder. usage: kit_sizes.py <map folder>"""
import sys
from pathlib import Path
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
d = Path(sys.argv[1])
for f in sorted(d.glob("*.png")):
    print(f.name, Image.open(f).size, Image.open(f).mode, f.stat().st_size)
