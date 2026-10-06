using Atlas3K.Core.Battle.Build.Meshes;
using Atlas3K.Formats.Maps;

namespace Atlas3K.Core.Battle.Build;

/// <summary>
/// hf_height_map.compressed_map of the battle tile (tooldatabuilder FUN_1800edbf0, mode 0): the decimated terrain mesh
/// (<see cref="BattleTileMeshBuilder"/>, the one mesh.rigid_model_v2 is written from, in float before half
/// quantisation) rasterised back onto the 1025 × 1025 vertex grid with BOB's rasteriser (<see cref="MeshRaster"/>), the
/// field initialised to 1.0, then normalised to its min..max: v = trunc((h − lo) · (1/(hi − lo)) · 65535) in
/// float32, header f[1] = lo, f[4] = hi (all 0 for a flat tile). Steep areas differ from the raw TIF where the
/// triangle merger dropped vertices.
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
        var source = project.HeightField(out var fw, out var fh);
        // FUN_1800edbf0 (mode 0): the decimated terrain mesh rasterised back into a field initialised to 1.0
        var mesh = BattleTileMeshBuilder.Build(source, fw, fh, project.TriangleDensity, project.TilesWide, project.TilesHigh,
            project.NormalStrength, BattleTileMeshBuilder.Mode.Mesh, BattleTileMeshStep.BattleAngleFactor0);
        var field = new float[fw * fh];
        Array.Fill(field, 1f);
        MeshRaster.Rasterise(field, fw, fh, mesh.Positions, mesh.Indices, 1f / (128f / project.TriangleDensity));
        float lo = float.MaxValue, hi = float.MinValue;
        foreach (var x in field) { if (x < lo) lo = x; if (x > hi) hi = x; }
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
/// hf_water_map.compressed_map (FUN_1800edbf0): a field of −1000 with the tile's river model (river_mesh.wsmodel
/// .rigid_model_v2 + pivot, model units = pixels) rasterised in by <see cref="MeshRaster"/>. Written only when the
/// tile has a river. Not covered by the corpus: water planes (FUN_1800ed480, WATER_PLANE_MESH entities).
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
        var v = new List<(float X, float Y, float Z)>(n);
        for (var i = 0; i < n; i++)
            v.Add((BitConverter.ToSingle(model.Vertices, i * stride) + pivot.X, BitConverter.ToSingle(model.Vertices, i * stride + 4) + pivot.Y,
                   BitConverter.ToSingle(model.Vertices, i * stride + 8) + pivot.Z));
        MeshRaster.Rasterise(field, width, height, v, model.Indices.Select(i => (int)i).ToList(), Scale);
    }
}
