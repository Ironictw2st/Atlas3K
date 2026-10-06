using System.Runtime.InteropServices;

namespace Atlas3K.Core.Battle.Build;

/// <summary>
/// BOB's DDS writer, TOOLDATABUILDER::write_dds_AMD_compressor, on top of the kit's own AMDCompress_MT_DLL.dll (AMD's
/// legacy Compressonator API, AMD_TC_ConvertTexture). Calling the same library is what makes the block compression
/// byte-identical. BOB's mip chain: each level a 2×2 box average of the previous one with rounding ((a+b+c+d+2) >> 2,
/// per byte), down to a smallest size of 1 &lt;&lt; minMipShift (1 for battle maps, 3 for campaign); every level is
/// compressed with default options (all zero but dwSize = 2000) and the DDS is a standard header + the levels
/// (Frida dump of a BOB run, research/bob_re/frida_amd_compress.js).
/// </summary>
public static class AmdCompress
{
    public const int FormatArgb8888 = 1;
    public const int FormatDxt1 = 12, FormatDxt3 = 31, FormatDxt5 = 32;

    [StructLayout(LayoutKind.Sequential)]
    private struct Texture
    {
        public uint Size, Width, Height, Pitch;
        public int Format;
        public uint DataSize;
        public IntPtr Data;
    }

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate int ConvertTexture(ref Texture src, ref Texture dst, IntPtr options, IntPtr feedback, IntPtr user1, IntPtr user2);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate uint CalculateBufferSize(ref Texture tex);

    private static ConvertTexture? _convert;
    private static CalculateBufferSize? _size;
    private static readonly object Gate = new();

    /// <summary>Loads AMDCompress_MT_DLL.dll from the kit's binaries folder.</summary>
    public static void Load(string kitRoot)
    {
        lock (Gate)
        {
            if (_convert is not null) return;
            var dll = Path.Combine(kitRoot, "binaries", "AMDCompress_MT_DLL.dll");
            if (!File.Exists(dll)) throw new FileNotFoundException($"{dll} not found (the kit's AMD texture compressor)");
            var h = NativeLibrary.Load(dll);
            _convert = Marshal.GetDelegateForFunctionPointer<ConvertTexture>(NativeLibrary.GetExport(h, "AMD_TC_ConvertTexture"));
            _size = Marshal.GetDelegateForFunctionPointer<CalculateBufferSize>(NativeLibrary.GetExport(h, "AMD_TC_CalculateBufferSize"));
        }
    }

    /// <summary>One level: ARGB8888 pixels (B, G, R, A bytes, row-major) → compressed blocks.</summary>
    public static byte[] Compress(byte[] bgra, int width, int height, int format)
    {
        if (_convert is null || _size is null) throw new InvalidOperationException("AmdCompress.Load first");
        var src = new Texture { Size = 32, Width = (uint)width, Height = (uint)height, Pitch = (uint)width * 4, Format = FormatArgb8888, DataSize = (uint)bgra.Length };
        var dst = new Texture { Size = 32, Width = (uint)width, Height = (uint)height, Pitch = 0, Format = format };
        dst.DataSize = _size(ref dst);
        var outBytes = new byte[dst.DataSize];
        var options = Marshal.AllocHGlobal(2000);
        var srcPin = GCHandle.Alloc(bgra, GCHandleType.Pinned);
        var dstPin = GCHandle.Alloc(outBytes, GCHandleType.Pinned);
        try
        {
            Marshal.Copy(new byte[2000], 0, options, 2000);
            Marshal.WriteInt32(options, 2000);
            src.Data = srcPin.AddrOfPinnedObject();
            dst.Data = dstPin.AddrOfPinnedObject();
            var err = _convert(ref src, ref dst, options, IntPtr.Zero, IntPtr.Zero, IntPtr.Zero);
            if (err != 0) throw new InvalidOperationException($"AMD_TC_ConvertTexture failed ({err})");
        }
        finally
        {
            srcPin.Free(); dstPin.Free(); Marshal.FreeHGlobal(options);
        }
        return outBytes;
    }

    /// <summary>The next mip: 2×2 box average per byte with rounding.</summary>
    public static byte[] Downsample(byte[] bgra, int width, int height, out int w2, out int h2)
    {
        w2 = Math.Max(1, width / 2); h2 = Math.Max(1, height / 2);
        var r = new byte[w2 * h2 * 4];
        for (var y = 0; y < h2; y++)
            for (var x = 0; x < w2; x++)
                for (var c = 0; c < 4; c++)
                {
                    int x0 = Math.Min(2 * x, width - 1), x1 = Math.Min(2 * x + 1, width - 1), y0 = Math.Min(2 * y, height - 1), y1 = Math.Min(2 * y + 1, height - 1);
                    var s = bgra[(y0 * width + x0) * 4 + c] + bgra[(y0 * width + x1) * 4 + c] + bgra[(y1 * width + x0) * 4 + c] + bgra[(y1 * width + x1) * 4 + c];
                    r[(y * w2 + x) * 4 + c] = (byte)((s + 2) >> 2);
                }
        return r;
    }

    /// <summary>write_dds_AMD_compressor: the mip chain compressed level by level into a DDS (FOURCC).</summary>
    public static byte[] WriteDds(byte[] bgra, int width, int height, int format, int minMipShift)
    {
        var minSize = 1 << minMipShift;
        var levels = new List<byte[]>();
        int w = width, h = height;
        var level = bgra;
        while (true)
        {
            levels.Add(Compress(level, w, h, format));
            if (w / 2 < minSize || h / 2 < minSize) break;
            level = Downsample(level, w, h, out var w2, out var h2);
            w = w2; h = h2;
        }
        var fourcc = format switch { FormatDxt1 => "DXT1", FormatDxt3 => "DXT3", _ => "DXT5" };
        using var ms = new MemoryStream();
        using var bw = new BinaryWriter(ms);
        bw.Write("DDS "u8); bw.Write(124); bw.Write(0xA1007); bw.Write(height); bw.Write(width); bw.Write(levels[0].Length); bw.Write(0); bw.Write(levels.Count);
        for (var i = 0; i < 11; i++) bw.Write(0);
        bw.Write(32); bw.Write(4); bw.Write(System.Text.Encoding.ASCII.GetBytes(fourcc)); for (var i = 0; i < 5; i++) bw.Write(0);
        bw.Write(0x401008); for (var i = 0; i < 4; i++) bw.Write(0);
        foreach (var l in levels) bw.Write(l);
        return ms.ToArray();
    }
}
