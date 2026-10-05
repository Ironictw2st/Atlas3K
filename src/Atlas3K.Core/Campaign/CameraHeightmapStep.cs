using System.Collections.Concurrent;
using System.Diagnostics;
using System.Globalization;
using Atlas3K.Formats.Maps;
using Atlas3K.Formats.Models;
using Atlas3K.Formats.Packs;
using Atlas3K.Formats.Props;

namespace Atlas3K.Core.Campaign;

/// <summary>
/// campaign_maps\&lt;map&gt;\camera_heightmap.png (BOB "Generate Camera Height Map", TOOLDATABUILDER::generate_camera_height_map):
/// the highest point of the scene — terrain clamped at sea level plus every prop model — sampled at lf resolution and
/// reduced by a 4x4 maximum to the tile-map grid. Written as 16-bit greyscale normalised to the highest sample, with
/// tEXt height_scale = highest / 65535 (the game refuses the file without it).
/// BOB (decompiled): per cell, the max of scene height queries over a one-cell rectangle, floored at -1 then 0, pixel =
/// ceil(h / highest * 65535), height_scale = highest / 65535. Terrain height there is lf plus the tile's hf map (zero
/// for all but road/river tiles); campaign relief like mountains comes from props, so props are rasterised here.
/// On prop-free vanilla 3k_dlc07 terrain this matches BOB within 0.05 units on 80% of cells. Over mountains the shipped
/// vanilla file follows an older prop layout (it omits current mountain props and has ones that no longer exist), so
/// it cannot be matched exactly; the output here follows the current props.
/// </summary>
public sealed class CameraHeightmapStep : ICampaignBuildStep
{
    /// <summary>World units per lf pixel (x, z); the same on every 3K map (vanilla 595.1 / 7136, 541.786 / 5620).</summary>
    public const double PixelSizeX = 595.1 / 7136, PixelSizeZ = 541.78619 / 5620;
    /// <summary>Source u16 → world y (fitted exactly on the vanilla land meshes).</summary>
    public const double HeightStep = 0.000218712, HeightOffset = -3.12725;

    public string Name => "camera_heightmap";
    public string ReplacesBobAction => "Terrain / Generate Camera Height Map";
    public IReadOnlyList<string> DependsOn => ["rasters", "global_props"];

    /// <summary>Gaussian blur sigma in tile-map pixels (0 = off, as vanilla appears to be).</summary>
    public double BlurSigma { get; init; }

    public IReadOnlyList<string> CheckInputs(CampaignBuildContext ctx)
    {
        var missing = new List<string>();
        if (!File.Exists(ctx.OutFile("lf_height_map.compressed_map"))) missing.Add("missing lf_height_map.compressed_map (run step 'rasters')");
        if (GlobalPropsSource(ctx) is null) missing.Add("no global_props.bin (output, working_data or vanilla root)");
        if (!Directory.Exists(ctx.Paths.GameDataDir)) missing.Add($"missing game data folder {ctx.Paths.GameDataDir}");
        return missing;
    }

    public StepResult Run(CampaignBuildContext ctx)
    {
        var sw = Stopwatch.StartNew();
        var notes = new List<string>();

        ctx.Log("terrain...");
        var lf = CompressedMap.Read(ctx.OutFile("lf_height_map.compressed_map"));
        var (w, h) = (lf.Raster.Width, lf.Raster.Height);
        var lo = lf.Header[1] * 65535.0;
        var range = (lf.Header[4] - lf.Header[1]) * 65535.0;
        var top = new float[w * h];
        for (var i = 0; i < top.Length; i++)
            top[i] = (float)Math.Max(0, (lo + lf.Raster.Data[i] / 65535.0 * range) * HeightStep + HeightOffset);

        var propsPath = GlobalPropsSource(ctx)!;
        ctx.Log($"props from {propsPath}...");
        var props = GlobalProps.Load(propsPath).ReadRegions(ctx.MapName).SelectMany(r => r.Props).Where(p => !p.IsDecal).ToList();
        var packs = PackSet.OpenVanilla(ctx.Paths.GameDataDir);
        var models = new ConcurrentDictionary<string, RigidModelGeometry?>(StringComparer.OrdinalIgnoreCase);
        var missing = new ConcurrentDictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        long triangles = 0;
        var worldH = h * PixelSizeZ;

        Parallel.ForEach(props, prop =>
        {
            var geometry = models.GetOrAdd(prop.Path, p => LoadModel(packs, p, ctx.TargetRoot));
            if (geometry is null) { missing.AddOrUpdate(prop.Path, 1, (_, n) => n + 1); return; }
            var m = Matrix(prop.Transform);
            var pos = geometry.Positions;
            var world = new float[pos.Length];
            for (var v = 0; v < pos.Length; v += 3)
            {
                double x = pos[v], y = pos[v + 1], z = pos[v + 2];
                world[v] = (float)((m[0] * x + m[1] * y + m[2] * z + prop.Transform.X) / PixelSizeX);                 // column
                world[v + 1] = (float)(m[3] * x + m[4] * y + m[5] * z + prop.Transform.Y);                           // height
                world[v + 2] = (float)((worldH - (m[6] * x + m[7] * y + m[8] * z + prop.Transform.Z)) / PixelSizeZ); // row
                Splat(top, w, h, world[v], world[v + 2], world[v + 1]);
            }
            var idx = geometry.Indices;
            for (var t = 0; t < idx.Length; t += 3)
                RasteriseTriangle(top, w, h, world, idx[t] * 3, idx[t + 1] * 3, idx[t + 2] * 3);
            Interlocked.Add(ref triangles, idx.Length / 3);
        });
        notes.Add($"{props.Count:N0} props, {models.Count(kv => kv.Value != null):N0} models, {triangles:N0} triangles rasterised");
        if (!missing.IsEmpty)
            notes.Add($"{missing.Values.Sum():N0} props skipped, model not readable: " +
                      string.Join(", ", missing.OrderByDescending(kv => kv.Value).Take(8).Select(kv => $"{kv.Key} ({kv.Value})")));

        ctx.Log("tile-map grid...");
        var (cw, ch) = (w / 4, h / 4);
        var cells = new float[cw * ch];
        Parallel.For(0, ch, cy =>
        {
            for (var cx = 0; cx < cw; cx++)
            {
                var max = 0f;
                for (var dy = 0; dy < 4; dy++)
                for (var dx = 0; dx < 4; dx++)
                    max = Math.Max(max, top[(cy * 4 + dy) * w + cx * 4 + dx]);
                cells[cy * cw + cx] = max;
            }
        });
        if (BlurSigma > 0) cells = Blur(cells, cw, ch, BlurSigma);

        var highest = cells.Max();
        var raster = new Raster<ushort>(cw, ch);
        for (var i = 0; i < cells.Length; i++)
            raster.Data[i] = highest > 0 ? (ushort)Math.Ceiling(Math.Max(0f, cells[i] / highest) * 65535f) : (ushort)0; // BOB: ceil
        var scale = (highest / 65535.0).ToString("F6", CultureInfo.InvariantCulture);
        Directory.CreateDirectory(ctx.CampaignMapOutDir);
        var outPath = Path.Combine(ctx.CampaignMapOutDir, "camera_heightmap.png");
        Png16.Write(outPath, raster, new Dictionary<string, string> { ["height_scale"] = scale });
        notes.Add($"{cw}x{ch}, highest sampled height {highest:F3} (height_scale {scale})");
        return new StepResult(Name, [outPath], notes, sw.Elapsed);
    }

    private static string? GlobalPropsSource(CampaignBuildContext ctx) =>
        new[] { ctx.OutFile("global_props.bin"),
                Path.Combine(ctx.Paths.AkWorkingDir, "terrain", "campaigns", ctx.MapName, "global_props.bin"),
                ctx.Paths.GlobalPropsBin }
            .FirstOrDefault(File.Exists);

    /// <summary>A model from the build output (e.g. the native river models) or the game packs.</summary>
    private static RigidModelGeometry? LoadModel(PackSet packs, string path, string targetRoot)
    {
        byte[]? Read(string p)
        {
            var loose = Path.Combine(targetRoot, p.Replace('/', Path.DirectorySeparatorChar));
            return File.Exists(loose) ? File.ReadAllBytes(loose) : packs.TryRead(p);
        }
        try
        {
            var bytes = Read(path);
            if (bytes is null) return null;
            if (path.EndsWith(".wsmodel", StringComparison.OrdinalIgnoreCase))
            {
                var geometry = RigidModelGeometry.WsModelGeometryPath(bytes);
                bytes = geometry is null ? null : Read(geometry);
                if (bytes is null) return null;
            }
            return RigidModelGeometry.Read(bytes);
        }
        catch (Exception e) when (e is InvalidDataException or NotSupportedException or ArgumentOutOfRangeException or IndexOutOfRangeException)
        {
            return null;
        }
    }

    /// <summary>Row-major 3x3 rotation * scale from the stored Blender-style XYZ Euler angles (degrees) and scale:
    /// R = Rz * Ry * Rx, column i scaled by scale i (inverse of <see cref="PropTransform.FromColumns"/>).</summary>
    public static double[] Matrix(PropTransform t)
    {
        const double rad = Math.PI / 180;
        double ci = Math.Cos(t.RotX * rad), si = Math.Sin(t.RotX * rad);
        double cj = Math.Cos(t.RotY * rad), sj = Math.Sin(t.RotY * rad);
        double ch = Math.Cos(t.RotZ * rad), sh = Math.Sin(t.RotZ * rad);
        double cc = ci * ch, cs = ci * sh, sc = si * ch, ss = si * sh;
        // Blender eul_to_mat3: mat[col][row]
        double[,] col =
        {
            { cj * ch, cj * sh, -sj },
            { sj * sc - cs, sj * ss + cc, cj * si },
            { sj * cc + ss, sj * cs - sc, cj * ci },
        };
        double[] s = [t.ScaleX, t.ScaleY, t.ScaleZ];
        var m = new double[9];
        for (var row = 0; row < 3; row++)
            for (var c = 0; c < 3; c++)
                m[row * 3 + c] = col[c, row] * s[c];
        return m;
    }

    private static void Splat(float[] top, int w, int h, float col, float row, float y)
    {
        int x = (int)Math.Floor(col), r = (int)Math.Floor(row);
        if ((uint)x < (uint)w && (uint)r < (uint)h) AtomicMax(ref top[r * w + x], y);
    }

    /// <summary>Samples the triangle's height at every lf pixel centre it covers (xz projection).</summary>
    private static void RasteriseTriangle(float[] top, int w, int h, float[] p, int a, int b, int c)
    {
        double ax = p[a], ay = p[a + 1], az = p[a + 2];
        double bx = p[b], by = p[b + 1], bz = p[b + 2];
        double cx = p[c], cy = p[c + 1], cz = p[c + 2];
        var area = (bx - ax) * (cz - az) - (cx - ax) * (bz - az);
        if (Math.Abs(area) < 1e-12) return;
        var x0 = Math.Max(0, (int)Math.Floor(Math.Min(ax, Math.Min(bx, cx)) - 0.5));
        var x1 = Math.Min(w - 1, (int)Math.Ceiling(Math.Max(ax, Math.Max(bx, cx)) - 0.5));
        var z0 = Math.Max(0, (int)Math.Floor(Math.Min(az, Math.Min(bz, cz)) - 0.5));
        var z1 = Math.Min(h - 1, (int)Math.Ceiling(Math.Max(az, Math.Max(bz, cz)) - 0.5));
        for (var r = z0; r <= z1; r++)
        {
            var pz = r + 0.5;
            for (var x = x0; x <= x1; x++)
            {
                var px = x + 0.5;
                var u = ((bx - px) * (cz - pz) - (cx - px) * (bz - pz)) / area;
                var v = ((cx - px) * (az - pz) - (ax - px) * (cz - pz)) / area;
                var t = 1 - u - v;
                if (u < 0 || v < 0 || t < 0) continue;
                AtomicMax(ref top[r * w + x], (float)(u * ay + v * by + t * cy));
            }
        }
    }

    private static void AtomicMax(ref float target, float value)
    {
        var current = Volatile.Read(ref target);
        while (value > current)
        {
            var seen = Interlocked.CompareExchange(ref target, value, current);
            if (seen == current) return;
            current = seen;
        }
    }

    private static float[] Blur(float[] src, int w, int h, double sigma)
    {
        var r = Math.Max(1, (int)Math.Ceiling(3 * sigma));
        var k = Enumerable.Range(-r, 2 * r + 1).Select(i => Math.Exp(-0.5 * i * i / (sigma * sigma))).ToArray();
        var sum = k.Sum();
        var tmp = new float[src.Length];
        var dst = new float[src.Length];
        Parallel.For(0, h, y =>
        {
            for (var x = 0; x < w; x++)
            {
                double acc = 0;
                for (var i = -r; i <= r; i++) acc += k[i + r] * src[y * w + Math.Clamp(x + i, 0, w - 1)];
                tmp[y * w + x] = (float)(acc / sum);
            }
        });
        Parallel.For(0, h, y =>
        {
            for (var x = 0; x < w; x++)
            {
                double acc = 0;
                for (var i = -r; i <= r; i++) acc += k[i + r] * tmp[Math.Clamp(y + i, 0, h - 1) * w + x];
                dst[y * w + x] = (float)(acc / sum);
            }
        });
        return dst;
    }
}
