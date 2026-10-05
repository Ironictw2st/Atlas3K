using BitMiracle.LibTiff.Classic;

namespace TerryClone.Formats.Maps;

/// <summary>
/// Reads/writes the assembly-kit terrain TIFs:
///  - 16-bit greyscale, uncompressed (height / sea_height / lf_heights / lf_sea_heights)
///  - 8-bit palettised (blend: LZW; tree: uncompressed)
/// </summary>
public static class TiffMap
{
    /// <summary>TIFF colormap: three arrays of 256 16-bit channel values.</summary>
    public sealed record Palette(ushort[] R, ushort[] G, ushort[] B);

    static TiffMap()
    {
        // Photoshop-authored AK TIFs carry private tags LibTiff warns about; keep the console quiet.
        Tiff.SetErrorHandler(new QuietErrorHandler());
    }

    public static Raster<ushort> ReadGray16(string path)
    {
        using var tif = Tiff.Open(path, "r") ?? throw new IOException($"Cannot open {path}");
        var (w, h) = Size(tif);
        if (tif.GetField(TiffTag.BITSPERSAMPLE)[0].ToInt() != 16)
            throw new InvalidDataException($"{Path.GetFileName(path)} is not 16-bit.");
        var raster = new Raster<ushort>(w, h);
        var row = new byte[tif.ScanlineSize()];
        for (var y = 0; y < h; y++)
        {
            tif.ReadScanline(row, y);
            Buffer.BlockCopy(row, 0, raster.Data, y * w * 2, w * 2);
        }
        return raster;
    }

    public static (Raster<byte> Indices, Palette Palette) ReadPalette8(string path)
    {
        using var tif = Tiff.Open(path, "r") ?? throw new IOException($"Cannot open {path}");
        var (w, h) = Size(tif);
        var map = tif.GetField(TiffTag.COLORMAP) ?? throw new InvalidDataException($"{Path.GetFileName(path)} has no colormap.");
        var palette = new Palette(map[0].ToUShortArray(), map[1].ToUShortArray(), map[2].ToUShortArray());
        var raster = new Raster<byte>(w, h);
        var row = new byte[tif.ScanlineSize()];
        for (var y = 0; y < h; y++)
        {
            tif.ReadScanline(row, y);
            Buffer.BlockCopy(row, 0, raster.Data, y * w, w);
        }
        return (raster, palette);
    }

    public static void WriteGray16(string path, Raster<ushort> raster)
    {
        WriteAtomically(path, temp =>
        {
            using var tif = Tiff.Open(temp, "w") ?? throw new IOException($"Cannot create {temp}");
            SetCommon(tif, raster.Width, raster.Height, 16, Photometric.MINISBLACK, Compression.NONE);
            var row = new byte[raster.Width * 2];
            for (var y = 0; y < raster.Height; y++)
            {
                Buffer.BlockCopy(raster.Data, y * raster.Width * 2, row, 0, row.Length);
                tif.WriteScanline(row, y);
            }
        });
    }

    public static void WritePalette8(string path, Raster<byte> raster, Palette palette, bool lzw)
    {
        WriteAtomically(path, temp =>
        {
            using var tif = Tiff.Open(temp, "w") ?? throw new IOException($"Cannot create {temp}");
            SetCommon(tif, raster.Width, raster.Height, 8, Photometric.PALETTE, lzw ? Compression.LZW : Compression.NONE);
            tif.SetField(TiffTag.COLORMAP, palette.R, palette.G, palette.B);
            var row = new byte[raster.Width];
            for (var y = 0; y < raster.Height; y++)
            {
                Buffer.BlockCopy(raster.Data, y * raster.Width, row, 0, row.Length);
                tif.WriteScanline(row, y);
            }
        });
    }

    private static void SetCommon(Tiff tif, int width, int height, int bits, Photometric photometric, Compression compression)
    {
        tif.SetField(TiffTag.IMAGEWIDTH, width);
        tif.SetField(TiffTag.IMAGELENGTH, height);
        tif.SetField(TiffTag.BITSPERSAMPLE, bits);
        tif.SetField(TiffTag.SAMPLESPERPIXEL, 1);
        tif.SetField(TiffTag.SAMPLEFORMAT, SampleFormat.UINT);
        tif.SetField(TiffTag.PHOTOMETRIC, photometric);
        tif.SetField(TiffTag.PLANARCONFIG, PlanarConfig.CONTIG);
        tif.SetField(TiffTag.COMPRESSION, compression);
        tif.SetField(TiffTag.ROWSPERSTRIP, compression == Compression.NONE ? 1 : 2);
    }

    private static void WriteAtomically(string path, Action<string> write)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(path))!);
        var temp = path + ".tmp";
        write(temp);
        File.Move(temp, path, overwrite: true);
    }

    /// <summary>Width and height of a TIF without reading its pixels.</summary>
    public static (int Width, int Height) ReadSize(string path)
    {
        using var tif = Tiff.Open(path, "r") ?? throw new IOException($"Cannot open {path}");
        return Size(tif);
    }

    private static (int W, int H) Size(Tiff tif) =>
        (tif.GetField(TiffTag.IMAGEWIDTH)[0].ToInt(), tif.GetField(TiffTag.IMAGELENGTH)[0].ToInt());

    private sealed class QuietErrorHandler : TiffErrorHandler
    {
        public override void WarningHandler(Tiff tif, string method, string format, params object[] args) { }
        public override void WarningHandlerExt(Tiff tif, object clientData, string method, string format, params object[] args) { }
    }
}
