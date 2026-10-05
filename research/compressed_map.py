"""Decoder for CA's FASTBIN0 *.compressed_map (TABLE_INDEXED) 16-bit rasters.

Worked out against CampaignMaps/Example/.../lf_height_map.compressed_map, which decodes bit-exact to the
lf_height_map.dds that ships next to it.

Layout (little endian):
  "FASTBIN0", u16 version (3), u32 width, u32 height, u32 tile_w, u32 tile_h, 6 x f32 header values,
  u16 len + "TABLE_INDEXED",
  u32 tile_count, u32 offsets[tile_count]          (into the tile data)
  u32 tile_count, u16 sizes[tile_count]
  u32 data_length, tile data
Tiles are row-major, row 0 first. Each tile is one of:
  - raw: size 1 + 2*tw*th, mode byte then u16 samples
  - palette (mode m < 128): (m+1) u16 palette values, then tw*th indices of ceil(log2(m+1)) bits, packed
    LSB first. A one-entry palette (m=0) is a constant tile of 3 bytes.
  - base + delta (mode m >= 128): u16 base, then tw*th unsigned deltas of (m-127) bits, packed LSB first.
    Seen in the river height patches, not in the example map, so it is checked only for continuity.

Header floats [1] and [4] are the value range: height = f[1] + v / 65535 * (f[4] - f[1]) (both 0 on the example
lf map, which is stored normalised).

How BOB writes lf_*_height_map.compressed_map from the u16 source TIFF (measured, 0 mismatches):
  lo, hi = source.min(), source.max()           header f[1] = lo/65535, f[4] = hi/65535 (float32)
  v = trunc(float32(source - lo) / float32(hi - lo) * 65535)   (checked with lo = 0)
A constant source gives lo == hi and all zeros. The land source spans 0..65535, so it is stored as is. The
3k_dlc07 sea source spans 0..44217, so vanilla's lf_sea_height_map values are source * 65535/44217. BOB's
lf_*_height_map.dds step decodes the compressed map it finds in the packs, so import the new one before
generating the .dds.

Height patches (terrain/campaigns/<map>/height_patches/*.compressed_map) use the same container; their world
rectangle is listed in rivers.height_patch_collection as four f32 (x0, z0, x1, z1) after each path. They are
512x512 over 32x32 world units, row 0 at z0, value 0 = no patch. They hold the river WATER SURFACE height
(matching the river spline y to ~0.01 over a footprint of the spline width), not a carved riverbed.
"""
import math
import struct
import numpy as np


def read_header(b):
    assert b[:8] == b"FASTBIN0", "not a FASTBIN0 file"
    version, w, h, tw, th = struct.unpack_from("<H4I", b, 8)
    floats = struct.unpack_from("<6f", b, 0x1A)
    return version, w, h, tw, th, floats


def decode(path_or_bytes):
    b = open(path_or_bytes, "rb").read() if isinstance(path_or_bytes, str) else path_or_bytes
    _, w, h, tw, th, floats = read_header(b)
    i = b.index(b"TABLE_INDEXED") + len("TABLE_INDEXED")
    n = struct.unpack_from("<I", b, i)[0]
    offs = struct.unpack_from(f"<{n}I", b, i + 4)
    j = i + 4 + 4 * n
    n2 = struct.unpack_from("<I", b, j)[0]
    sizes = struct.unpack_from(f"<{n2}H", b, j + 4)
    k = j + 4 + 2 * n2
    data_len = struct.unpack_from("<I", b, k)[0]
    base = k + 4
    assert base + data_len <= len(b)

    cols = -(-w // tw)
    rows = -(-h // th)
    out = np.zeros((rows * th, cols * tw), np.uint16)  # edge tiles are full size; cropped below
    samples = tw * th
    for t in range(n):
        d = b[base + offs[t]:base + offs[t] + sizes[t]]
        if len(d) == 1 + 2 * samples:
            tile = np.frombuffer(d[1:], "<u2")
        elif d[0] >= 128:
            # base + delta: u16 base, then (mode - 127)-bit unsigned deltas
            bits = d[0] - 127
            base_value = struct.unpack_from("<H", d, 1)[0]
            packed = np.frombuffer(d[3:], np.uint8)
            stream = np.unpackbits(packed, bitorder="little")[:samples * bits].reshape(samples, bits)
            tile = (base_value + (stream.astype(np.uint32) << np.arange(bits, dtype=np.uint32)).sum(1)).astype(np.uint16)
        else:
            count = d[0] + 1
            palette = np.frombuffer(d[1:1 + 2 * count], "<u2")
            bits = math.ceil(math.log2(count)) if count > 1 else 0
            if bits == 0:
                tile = np.full(samples, palette[0], np.uint16)
            else:
                packed = np.frombuffer(d[1 + 2 * count:], np.uint8)
                stream = np.unpackbits(packed, bitorder="little")[:samples * bits].reshape(samples, bits)
                idx = (stream.astype(np.uint32) << np.arange(bits, dtype=np.uint32)).sum(1)
                tile = palette[idx]
        r, c = divmod(t, cols)
        out[r * th:(r + 1) * th, c * tw:(c + 1) * tw] = tile.reshape(th, tw)
    return out[:h, :w], floats


def read_patch_collection(path):
    """{patch file name: (x0, z0, x1, z1)} from a *.height_patch_collection."""
    b = open(path, "rb").read()
    assert b[:8] == b"FASTBIN0"
    # u16 version, u32 count, then per patch: u16 (1), u16 length, path, 4 x f32
    count = struct.unpack_from("<I", b, 10)[0]
    pos = 14
    out = {}
    for _ in range(count):
        n = struct.unpack_from("<H", b, pos + 2)[0]
        name = b[pos + 4:pos + 4 + n].decode()
        rect = struct.unpack_from("<4f", b, pos + 4 + n)
        out[name.split("//")[-1]] = rect
        pos += 4 + n + 16
    return out
