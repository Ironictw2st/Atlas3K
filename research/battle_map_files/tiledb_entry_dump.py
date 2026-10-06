"""Decode a battle tile-database entry (_assembly_kit_<id>.bin, TILE v7 / VARIATION v10 / texture_set v2).
usage: tiledb_entry_dump.py <file.bin> [...]"""
import struct, sys


def dump(p):
    d = open(p, 'rb').read(); o = 8
    out = []

    def u16():
        nonlocal o; v, = struct.unpack_from('<H', d, o); o += 2; return v
    def i32():
        nonlocal o; v, = struct.unpack_from('<i', d, o); o += 4; return v
    def f32():
        nonlocal o; v, = struct.unpack_from('<f', d, o); o += 4; return v
    def u8():
        nonlocal o; v = d[o]; o += 1; return v
    def s():
        nonlocal o; n = u16(); v = d[o:o + n].decode('latin1'); o += n; return v
    out.append(('ver', u16())); out.append(('name', s())); out.append(('set', s())); out.append(('mask', s())); out.append(('nogo', s()))
    out.append(('w', i32())); out.append(('h', i32())); out.append(('rgb', (u8(), u8(), u8())))
    for k in ('lodding', 'rotatable'): out.append((k, u8()))
    out.append(('custom_alpha', s())); out.append(('scalable', u8())); out.append(('encampable', u8())); out.append(('custom_blend_tile', s()))
    nv = i32(); out.append(('variations', nv))
    for _ in range(nv):
        out.append(('var_ver', u16()))
        out.append(('ts_ver', u16()))
        out.append(('faction', s()))
        out.append(('channels', [s() for _ in range(8)]))
        out.append(('location', s())); out.append(('vname', s()))
        out.append(('min_h,scale,normal,overlap', (f32(), f32(), f32(), f32())))
        out.append(('tri_density', i32())); out.append(('blend/index/normal_common', (s(), s(), s())))
        out.append(('rgb', (u8(), u8(), u8()))); out.append(('sea_in_infield', u8())); out.append(('shadow_depth', f32()))
        out.append(('sea_plane', u8())); out.append(('subterranean', u8())); out.append(('fog_mask', s()))
    out.append(('targets', i32())); out.append(('links', i32())); out.append(('barbarian', u8())); out.append(('use_alt_lf', u8()))
    out.append(('left', len(d) - o))
    return out


for p in sys.argv[1:]:
    print('==', p, len(open(p, 'rb').read()))
    for k, v in dump(p): print('  ', k, v)
