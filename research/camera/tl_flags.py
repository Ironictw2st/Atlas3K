import struct, sys, collections
def read(p):
    b = open(p, 'rb').read(); o = 12
    for _ in range(2):
        n = struct.unpack_from('<I', b, o)[0]; o += 4
        for _ in range(n): l = struct.unpack_from('<H', b, o)[0]; o += 2 + l
    o += 24 + 44 + 1; n = struct.unpack_from('<I', b, o)[0]; o += 4
    return [struct.unpack_from('<HIBHHBBff', b, o + 21 * i) for i in range(n)]
for p in sys.argv[1:]:
    r = read(p); print(p, len(r), collections.Counter(x[6] for x in r), collections.Counter(x[5] for x in r))
