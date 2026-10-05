"""Parse the tile sets in campaign _tile_database/_settings.bin (exploratory): u32 count at 0x1f8, then per set
u16 version 2, u16 name length + name, u16 link length + link tile path, then a fixed tail."""
import struct, sys
P = r"C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\assembly_kit_190E\raw_data\terrain\tiles\campaign\_tile_database\_settings.bin"
b = open(P, 'rb').read()
o = b.index(b'\x02\x00\x07\x00generic') - 4
n = struct.unpack_from('<I', b, o)[0]; o += 4
print('sets', n)
for _ in range(n):
    ver, ln = struct.unpack_from('<HH', b, o); name = b[o + 4:o + 4 + ln].decode(); o += 4 + ln
    ll = struct.unpack_from('<H', b, o)[0]; link = b[o + 2:o + 2 + ll].decode(); o += 2 + ll
    # tail until the next entry
    nxt = o
    while nxt < len(b) - 4 and not (b[nxt:nxt + 2] == b'\x02\x00' and 0 < struct.unpack_from('<H', b, nxt + 2)[0] < 40 and b[nxt + 4:nxt + 5].isalpha()):
        nxt += 1
    tail = b[o:nxt]
    print(f'{name:28s} link={link[-20:]:20s} tail({len(tail)}) {tail.hex(" ")}')
    o = nxt
