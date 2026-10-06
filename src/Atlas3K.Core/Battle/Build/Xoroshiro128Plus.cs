namespace Atlas3K.Core.Battle.Build;

/// <summary>
/// The xoroshiro128+ generator qttoolutility's procedural code uses (inlined in QTU::generate_grass, FUN_1800788c0):
/// both state words start as the seed (a zero seed takes the constants below), one step is discarded, and each draw
/// returns s0 + s1 before stepping. Shared by the battle vegetation steps.
/// </summary>
public sealed class Xoroshiro128Plus
{
    private ulong _s0, _s1;

    public Xoroshiro128Plus(ulong seed)
    {
        _s0 = _s1 = seed;
        if (seed == 0) { _s0 = 0x33001294d9708f82; _s1 = 0xa524c8b000000004; }
        Step();
    }

    private void Step()
    {
        var s1 = _s1 ^ _s0;
        _s0 = ((_s0 >> 9) | (_s0 << 55)) ^ s1 ^ (s1 << 14);
        _s1 = (s1 >> 28) | (s1 << 36);
    }

    /// <summary>The next 64-bit output.</summary>
    public ulong Next()
    {
        var r = _s0 + _s1;
        Step();
        return r;
    }

    /// <summary>The top 16 bits of the next output (what the grass generator scales to an angle or a radius).</summary>
    public ushort NextHigh16() => (ushort)(Next() >> 48);

    /// <summary>An index in [0, count): the top 32 bits of a draw, redrawn while they are &lt;= 0xffffffff % count
    /// (BOB's rejection test, as written), then taken modulo count.</summary>
    public int NextIndex(uint count)
    {
        var lim = 0xffffffffu % count;
        uint v;
        do v = (uint)(Next() >> 32); while (v <= lim);
        return (int)(v % count);
    }
}
