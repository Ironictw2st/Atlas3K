using System.Buffers.Binary;
using Atlas3K.Core.Campaign.Rivers;
using Atlas3K.Formats.Models;

namespace Atlas3K.Core.Battle.Build.Meshes;

/// <summary>
/// "Process Terry tile (heightmap)" terrain meshes: shadow_mesh, outfield_mesh and mesh.rigid_model_v2 in the tile
/// folder (tooldatabuilder process_tile_internal → FUN_1800edbf0 per mode → FUN_1800d9c60 → MODEL_PROCESSOR
/// open_height_map + write). Order as BOB: shadow, then (requires_infield_lodding) outfield, mesh.
/// </summary>
[BattleStepOrder(200)]
public sealed class BattleTileMeshStep : IBattleBuildStep
{
    public string Name => "tile_meshes";

    /// <summary>conversion_params.triangle_decimation_angle_factors0 of the vanilla battle tile database (_settings.bin).</summary>
    public const float BattleAngleFactor0 = 20f;

    public void Run(BattleBuildContext ctx, Action<string> log)
    {
        var project = TerryTileProject.Load(ctx.TerryFile);
        var field = project.HeightField(out var w, out var h);
        Directory.CreateDirectory(ctx.OutTileDir);
        foreach (var (mode, file) in new[]
                 {
                     (BattleTileMeshBuilder.Mode.Shadow, "shadow_mesh.rigid_model_v2"),
                     (BattleTileMeshBuilder.Mode.Outfield, "outfield_mesh.rigid_model_v2"),
                     (BattleTileMeshBuilder.Mode.Mesh, "mesh.rigid_model_v2"),
                 })
        {
            if (mode == BattleTileMeshBuilder.Mode.Outfield && !project.InfieldTile) continue;
            var result = BattleTileMeshBuilder.Build(field, w, h, project.TriangleDensity, project.TilesWide, project.TilesHigh,
                project.NormalStrength, mode, BattleAngleFactor0);
            var bytes = TileMeshBytes(result, w);
            File.WriteAllBytes(Path.Combine(ctx.OutTileDir, file), bytes);
            log($"{file}: {result.Positions.Count} vertices, {result.Indices.Count / 3} triangles");
        }
    }

    /// <summary>An RMV2 v8 with no LOD (the shadow mesh of a height field): 140 bytes.</summary>
    public static byte[] EmptyModel()
    {
        var b = new byte[140];
        "RMV2"u8.CopyTo(b);
        BinaryPrimitives.WriteUInt32LittleEndian(b.AsSpan(4), 8);
        return b;
    }

    /// <summary>The tile mesh as BOB writes it: material 96 ("TerrainBase0"), 8-byte vertices (x, y, z half floats with
    /// BOB's rounding, 0), indices with each triangle's first two corners swapped. Material block after the name:
    /// tile width and depth in world units, the field width, LOD count 1, 16, and the index count before the fringes.</summary>
    public static byte[] TileMeshBytes(BattleTileMeshBuilder.Result r, int fieldWidth)
    {
        if (r.Positions.Count == 0) return EmptyModel();
        var model = new RigidModelV2
        {
            Material = 96,
            LodQuality = new byte[4],
            Shader = TileShader(),
            MaterialBlock = TerrainBaseMaterial(1024, 1024, (uint)fieldWidth, 1, 16, (uint)r.MainIndexCount),
            VertexStride = 8,
        };
        var verts = new byte[r.Positions.Count * 8];
        float[] bounds = [float.MaxValue, float.MaxValue, float.MaxValue, float.MinValue, float.MinValue, float.MinValue];
        for (var i = 0; i < r.Positions.Count; i++)
        {
            var (x, y, z) = r.Positions[i];
            var s = verts.AsSpan(i * 8);
            BinaryPrimitives.WriteUInt16LittleEndian(s, BobRiver.HalfBits(x));
            BinaryPrimitives.WriteUInt16LittleEndian(s[2..], BobRiver.HalfBits(y));
            BinaryPrimitives.WriteUInt16LittleEndian(s[4..], BobRiver.HalfBits(z));
            bounds[0] = Math.Min(bounds[0], x); bounds[1] = Math.Min(bounds[1], y); bounds[2] = Math.Min(bounds[2], z);
            bounds[3] = Math.Max(bounds[3], x); bounds[4] = Math.Max(bounds[4], y); bounds[5] = Math.Max(bounds[5], z);
        }
        model.Vertices = verts;
        model.Bounds = bounds;
        var idx = new ushort[r.Indices.Count];
        for (var t = 0; t < idx.Length; t += 3)
        {
            idx[t] = checked((ushort)r.Indices[t + 1]);
            idx[t + 1] = checked((ushort)r.Indices[t]);
            idx[t + 2] = checked((ushort)r.Indices[t + 2]);
        }
        model.Indices = idx;
        return model.ToBytes();
    }

    /// <summary>"rigid_default" and the bytes BOB leaves after it (the same in every file).</summary>
    private static byte[] TileShader()
    {
        var s = new byte[32];
        "rigid_default"u8.CopyTo(s);
        s[15] = 0x8D;
        s[24] = 0x9E;
        s[25] = 0xD4;
        return s;
    }

    private static byte[] TerrainBaseMaterial(uint width, uint depth, uint fieldWidth, uint lods, uint sixteen, uint mainIndices)
    {
        var m = new byte[88];
        "TerrainBase0"u8.CopyTo(m);
        var s = m.AsSpan(64);
        BinaryPrimitives.WriteUInt32LittleEndian(s, width);
        BinaryPrimitives.WriteUInt32LittleEndian(s[4..], depth);
        BinaryPrimitives.WriteUInt32LittleEndian(s[8..], fieldWidth);
        BinaryPrimitives.WriteUInt32LittleEndian(s[12..], lods);
        BinaryPrimitives.WriteUInt32LittleEndian(s[16..], sixteen);
        BinaryPrimitives.WriteUInt32LittleEndian(s[20..], mainIndices);
        return m;
    }
}
