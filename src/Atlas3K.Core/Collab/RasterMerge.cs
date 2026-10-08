using System.Runtime.InteropServices;
using Atlas3K.Formats.Maps;

namespace Atlas3K.Core.Collab;

/// <summary>
/// A map raster as raw pixels, whatever its file format: 16-bit greyscale TIF (height, sea_height), 8-bit palette TIF
/// (blend, tree) or PNG (tile_map, climate maps). Saved back in the file's own format (TIFs patched in place when
/// uncompressed), so merges don't churn headers.
/// </summary>
public sealed class RasterImage
{
    public enum Format { Gray16Tif, Palette8Tif, Png }

    public Format Kind { get; }
    public int Width { get; }
    public int Height { get; }
    public int BytesPerPixel { get; }
    public byte[] Data { get; }
    public TiffMap.Palette? Palette { get; }

    private RasterImage(Format kind, int width, int height, int bpp, byte[] data, TiffMap.Palette? palette = null)
    {
        Kind = kind;
        Width = width;
        Height = height;
        BytesPerPixel = bpp;
        Data = data;
        Palette = palette;
    }

    public static bool IsRaster(string path) =>
        Path.GetExtension(path).ToLowerInvariant() is ".tif" or ".tiff" or ".png";

    public static RasterImage Load(string path)
    {
        if (Path.GetExtension(path).Equals(".png", StringComparison.OrdinalIgnoreCase))
        {
            var png = PngMap.Read(path);
            return new RasterImage(Format.Png, png.Width, png.Height, 4, MemoryMarshal.AsBytes(png.Data.AsSpan()).ToArray());
        }
        var layout = TiffMap.ReadLayout(path);
        if (layout.Bits == 16)
        {
            var r = TiffMap.ReadGray16(path);
            return new RasterImage(Format.Gray16Tif, r.Width, r.Height, 2, MemoryMarshal.AsBytes(r.Data.AsSpan()).ToArray());
        }
        if (layout.Bits == 8)
        {
            var (indices, palette) = TiffMap.ReadPalette8(path);
            return new RasterImage(Format.Palette8Tif, indices.Width, indices.Height, 1, indices.Data, palette);
        }
        throw new InvalidDataException($"{Path.GetFileName(path)}: {layout.Bits}-bit TIF is not a map raster Atlas3K merges");
    }

    public RasterImage WithData(byte[] data) => new(Kind, Width, Height, BytesPerPixel, data, Palette);

    /// <summary>Writes the pixels to <paramref name="path"/>; for TIFs the file there is the format template (it must
    /// exist: TIFs are saved "like" it).</summary>
    public void Save(string path)
    {
        switch (Kind)
        {
            case Format.Png:
                PngMap.Write(path, new Raster<uint>(Width, Height, MemoryMarshal.Cast<byte, uint>(Data).ToArray()));
                break;
            case Format.Gray16Tif:
                var r16 = new Raster<ushort>(Width, Height, MemoryMarshal.Cast<byte, ushort>(Data).ToArray());
                if (File.Exists(path)) TiffMap.SaveGray16Like(path, r16);
                else TiffMap.WriteGray16(path, r16);
                break;
            case Format.Palette8Tif:
                var r8 = new Raster<byte>(Width, Height, Data);
                if (File.Exists(path)) TiffMap.SavePalette8Like(path, r8, Palette!);
                else TiffMap.WritePalette8(path, r8, Palette!, lzw: true);
                break;
        }
    }

    public bool PixelEquals(RasterImage other, int i) =>
        Data.AsSpan(i * BytesPerPixel, BytesPerPixel).SequenceEqual(other.Data.AsSpan(i * BytesPerPixel, BytesPerPixel));
}

/// <summary>
/// Per-pixel three-way merge of map rasters: a pixel changed on one side takes that side; a pixel both sides changed
/// to different values is a conflict (kept ours). Conflicts are reported per <see cref="Cell"/>-pixel cell.
/// </summary>
public static class RasterMerge
{
    public const int Cell = 64;

    public sealed record Result(RasterImage? Merged, List<MergeConflict> Conflicts, long FromTheirs);

    public static Result Merge(RasterImage? b, RasterImage o, RasterImage t, string file)
    {
        if (o.Width != t.Width || o.Height != t.Height || b is not null && (b.Width != o.Width || b.Height != o.Height))
        {
            // A resize on one side only takes that side whole.
            if (b is not null && Same(b, o)) return new Result(t, [], (long)t.Width * t.Height);
            if (b is not null && Same(b, t)) return new Result(o, [], 0);
            return new Result(o, [new MergeConflict(file, "size", "size",
                $"sizes differ (ours {o.Width}x{o.Height}, theirs {t.Width}x{t.Height}); kept ours")], 0);
        }
        var bpp = o.BytesPerPixel;
        var data = (byte[])o.Data.Clone();
        var cells = new Dictionary<(int, int), int>();
        long fromTheirs = 0;
        var n = o.Width * o.Height;
        for (var i = 0; i < n; i++)
        {
            if (o.PixelEquals(t, i)) continue;
            if (b is not null && b.PixelEquals(t, i)) continue;
            if (b is not null && b.PixelEquals(o, i))
            {
                Buffer.BlockCopy(t.Data, i * bpp, data, i * bpp, bpp);
                fromTheirs++;
                continue;
            }
            var key = (i % o.Width / Cell, i / o.Width / Cell);
            cells[key] = cells.GetValueOrDefault(key) + 1;
        }
        var conflicts = cells.OrderBy(c => c.Key.Item2).ThenBy(c => c.Key.Item1).Select(c =>
        {
            int x = c.Key.Item1 * Cell, y = c.Key.Item2 * Cell;
            return new MergeConflict(file, "pixels", $"{x},{y}",
                $"{c.Value} pixel(s) changed differently on both sides in [{x},{y}] (+{Cell}); kept ours",
                Rect: [x, y, Math.Min(Cell, o.Width - x), Math.Min(Cell, o.Height - y)]);
        }).ToList();
        return new Result(o.WithData(data), conflicts, fromTheirs);
    }

    private static bool Same(RasterImage a, RasterImage b) =>
        a.Width == b.Width && a.Height == b.Height && a.Data.AsSpan().SequenceEqual(b.Data);

    public sealed record Change(long Pixels, int[]? Bounds, List<int[]> Cells);

    /// <summary>The pixels that differ between two same-sized rasters: count, bounding rect [x, y, w, h] and the
    /// changed <see cref="Cell"/> cells ([cx, cy]).</summary>
    public static Change Diff(RasterImage before, RasterImage after)
    {
        if (before.Width != after.Width || before.Height != after.Height)
            return new Change((long)after.Width * after.Height, [0, 0, after.Width, after.Height], []);
        long count = 0;
        int x0 = int.MaxValue, y0 = int.MaxValue, x1 = -1, y1 = -1;
        var cells = new HashSet<(int, int)>();
        var w = after.Width;
        for (var i = 0; i < w * after.Height; i++)
        {
            if (before.PixelEquals(after, i)) continue;
            count++;
            int x = i % w, y = i / w;
            x0 = Math.Min(x0, x); y0 = Math.Min(y0, y); x1 = Math.Max(x1, x); y1 = Math.Max(y1, y);
            cells.Add((x / Cell, y / Cell));
        }
        return new Change(count, count == 0 ? null : [x0, y0, x1 - x0 + 1, y1 - y0 + 1],
            cells.OrderBy(c => c.Item2).ThenBy(c => c.Item1).Select(c => new[] { c.Item1, c.Item2 }).ToList());
    }

    /// <summary>Copies a rect of pixels from <paramref name="source"/> into <paramref name="target"/>'s data.</summary>
    public static void CopyRect(RasterImage source, byte[] target, int[] rect)
    {
        var bpp = source.BytesPerPixel;
        for (var y = rect[1]; y < rect[1] + rect[3]; y++)
        {
            var at = (y * source.Width + rect[0]) * bpp;
            Buffer.BlockCopy(source.Data, at, target, at, rect[2] * bpp);
        }
    }
}
