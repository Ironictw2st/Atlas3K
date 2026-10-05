"""16-bit greyscale TIFF writer matching TerryClone's TiffMap.WriteGray16 (the layout Terry reads correctly):
little-endian, uncompressed, one row per strip, SamplesPerPixel=1, SampleFormat=UINT, PlanarConfig=contig.
PIL's writer (one big strip, no SampleFormat/SamplesPerPixel) made Terry read the heights wrongly."""
import struct
import numpy as np


def write_gray16(path, arr):
    a = np.ascontiguousarray(arr, dtype="<u2")
    h, w = a.shape
    row = w * 2
    tags = [  # (tag, type, count, value-or-offset placeholder)
        (256, 4, 1, w), (257, 4, 1, h), (258, 3, 1, 16), (259, 3, 1, 1), (262, 3, 1, 1),
        (273, 4, h, None), (277, 3, 1, 1), (278, 4, 1, 1), (279, 4, h, None), (284, 3, 1, 1), (339, 3, 1, 1),
    ]
    ifd_off = 8
    ifd_size = 2 + 12 * len(tags) + 4
    offsets_off = ifd_off + ifd_size
    counts_off = offsets_off + 4 * h
    data_off = counts_off + 4 * h
    with open(path, "wb") as f:
        f.write(b"II*\x00" + struct.pack("<I", ifd_off))
        f.write(struct.pack("<H", len(tags)))
        for tag, typ, count, val in tags:
            if tag == 273: val = offsets_off
            if tag == 279: val = counts_off
            if typ == 3 and count == 1:
                f.write(struct.pack("<HHIHH", tag, typ, count, val, 0))
            else:
                f.write(struct.pack("<HHII", tag, typ, count, val))
        f.write(struct.pack("<I", 0))
        f.write(np.arange(h, dtype="<u4").__mul__(row).__add__(data_off).tobytes())
        f.write(np.full(h, row, dtype="<u4").tobytes())
        f.write(a.tobytes())
