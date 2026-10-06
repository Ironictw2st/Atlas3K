using Atlas3K.Core.Battle.Build.Meshes;
using Atlas3K.Formats.Maps;

namespace Atlas3K.Core.Battle.Build;

/// <summary>
/// hf_height_map.compressed_map of the battle tile ("Process Terry tile (heightmap)"): the project's float Height
/// map cropped to the tile's vertex grid (triangle_density + 1 pixels in from each side: 1280 → 1025 for an 8×8 tile
/// at density 128, the same window the meshes use) and normalised to the full TIF's min..max:
/// v = trunc((h − lo) · (1/(hi − lo)) · 65535) in float32, header f[1] = lo, f[4] = hi (all 0 for a flat tile).
/// Not reproduced yet: BOB's local edits under buildings (dfe064a6: 260 of 1,050,625 pixels near a palace
/// foundation prefab differ).
/// </summary>
[BattleStepOrder(160)]
public sealed class BattleHfHeightStep : IBattleBuildStep
{
    public string Name => "hf_height";

    public void Run(BattleBuildContext ctx, Action<string> log)
    {
        var project = TerryTileProject.Load(ctx.TerryFile);
        if (project.HeightTif is null) throw new FileNotFoundException($"no Height map TIF next to {ctx.TerryFile}");
        var (w, h, v) = TerryTileProject.ReadFloatTif(project.HeightTif);
        var field = project.HeightField(out var fw, out var fh);
        float lo = float.MaxValue, hi = float.MinValue;
        foreach (var x in v) { if (x < lo) lo = x; if (x > hi) hi = x; }
        var raster = new Raster<ushort>(fw, fh);
        if (hi > lo)
        {
            var inv = 1f / (hi - lo);
            for (var i = 0; i < field.Length; i++)
            {
                var t = (field[i] - lo) * inv;
                raster.Data[i] = (ushort)(t * 65535f);
            }
        }
        else lo = hi = 0;
        CompressedMap.Write(Path.Combine(ctx.OutTileDir, "hf_height_map.compressed_map"), raster, [0, lo, 0, 0, hi, 0]);
    }
}

/// <summary>
/// hf_water_map.compressed_map: the tile's river model (river_mesh.wsmodel.rigid_model_v2, written by the river step)
/// rasterised onto the hf grid (the same 1025 × 1025 window, <see cref="Scale"/> world units per pixel, row 0 = z 0)
/// with the height-patch crossing test (<see cref="Campaign.Rivers.BobRiver"/>), keeping the highest surface per pixel;
/// pixels without water are −1000. Written only when the tile has a river. 418 of BOB's 422 water pixels on
/// dfe064a6/df46bdbc (the rule for triangle-edge pixels is not settled yet).
/// </summary>
[BattleStepOrder(290)]
public sealed class BattleHfWaterStep : IBattleBuildStep
{
    public string Name => "hf_water";
    public const float NoWater = -1000f;
    public static float Scale = 1f;
    public static float Offset = 0f;

    public void Run(BattleBuildContext ctx, Action<string> log)
    {
        var path = Path.Combine(ctx.OutTileDir, "hf_water_map.compressed_map");
        var modelPath = Path.Combine(ctx.OutTileDir, "river_mesh.wsmodel.rigid_model_v2");
        if (!File.Exists(modelPath)) { log("hf_water: no river model (run river_meshes first)"); return; }
        var models = new List<Atlas3K.Formats.Models.RigidModelV2>();
        var ws = Path.Combine(ctx.OutTileDir, "river_mesh.wsmodel");
        if (File.Exists(ws) && File.ReadAllText(ws).Contains("<materials/>"))
        {
            // no river: BOB writes no water map
            if (File.Exists(path)) File.Delete(path);
            return;
        }
        var first = Atlas3K.Formats.Models.RigidModelV2.Read(modelPath);
        models.Add(first);
        models.AddRange(first.MoreMeshes);
        var project = TerryTileProject.Load(ctx.TerryFile);
        project.HeightField(out var w, out var h);
        var field = new float[w * h];
        Array.Fill(field, NoWater);
        foreach (var m in models) Rasterise(m, field, w, h);
        float lo = float.MaxValue, hi = float.MinValue;
        foreach (var v in field) { if (v < lo) lo = v; if (v > hi) hi = v; }
        var raster = new Raster<ushort>(w, h);
        if (hi > lo)
        {
            var inv = 1f / (hi - lo);
            for (var i = 0; i < field.Length; i++) raster.Data[i] = (ushort)((field[i] - lo) * inv * 65535f);
        }
        CompressedMap.Write(path, raster, [0, lo, 0, 0, hi, 0]);
        log($"hf_water: {field.Count(v => v != NoWater)} water pixels");
    }

    private static void Rasterise(Atlas3K.Formats.Models.RigidModelV2 model, float[] field, int width, int height)
    {
        var pivot = (X: BitConverter.ToSingle(model.MaterialBlock, 0x224), Y: BitConverter.ToSingle(model.MaterialBlock, 0x228),
                     Z: BitConverter.ToSingle(model.MaterialBlock, 0x22C));
        var n = model.VertexCount;
        var stride = model.Vertices.Length / Math.Max(1, n);
        var vy = new float[n]; var px = new float[n]; var py = new float[n];
        for (var i = 0; i < n; i++)
        {
            var x = BitConverter.ToSingle(model.Vertices, i * stride) + pivot.X;
            vy[i] = BitConverter.ToSingle(model.Vertices, i * stride + 4) + pivot.Y;
            var z = BitConverter.ToSingle(model.Vertices, i * stride + 8) + pivot.Z;
            px[i] = x / Scale + Offset;
            py[i] = z / Scale + Offset;
        }
        var idx = model.Indices;
        for (var q = 0; q + 2 < idx.Length; q += 3)
        {
            int ia = idx[q], ib = idx[q + 1], ic = idx[q + 2];
            float axp = px[ia], ayp = py[ia], bxp = px[ib], byp = py[ib], cxp = px[ic], cyp = py[ic];
            var x0 = Math.Min((int)axp, Math.Min((int)bxp, (int)cxp)) - 1;
            var x1 = Math.Max((int)axp, Math.Max((int)bxp, (int)cxp)) + 1;
            var y0 = Math.Min((int)ayp, Math.Min((int)byp, (int)cyp)) - 1;
            var y1 = Math.Max((int)ayp, Math.Max((int)byp, (int)cyp)) + 1;
            if (x1 < 0 || width < x0 || y1 < 0 || height < y0) continue;
            x0 = Math.Max(x0, 0); y0 = Math.Max(y0, 0); x1 = Math.Min(x1, width); y1 = Math.Min(y1, height);
            var area = MathF.Abs((cxp - axp) * (byp - ayp) - (cyp - ayp) * (bxp - axp));
            for (var y = y0; y < y1; y++)
                for (var x = x0; x < x1; x++)
                {
                    float fx = x, fy = y;
                    if (!Campaign.Rivers.BobRiver.InsideTriangle(fx, fy, axp, ayp, bxp, byp, cxp, cyp)) continue;
                    var inv = 2f / area;
                    var wc = MathF.Abs((fy - ayp) * (bxp - axp) - (fx - axp) * (byp - ayp)) * 0.5f * inv;
                    var wb = MathF.Abs((fy - ayp) * (cxp - axp) - (fx - axp) * (cyp - ayp)) * 0.5f * inv;
                    var wa = 1f - wb - wc;
                    var hgt = vy[ib] * wb + vy[ia] * wa + vy[ic] * wc;
                    ref var cell = ref field[y * width + x];
                    if (!(hgt <= cell)) cell = hgt;
                }
        }
    }
}
