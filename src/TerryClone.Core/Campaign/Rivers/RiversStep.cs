using System.Diagnostics;
using TerryClone.Core.Campaign.GlobalMesh;
using TerryClone.Formats.Maps;
using TerryClone.Formats.Models;

namespace TerryClone.Core.Campaign.Rivers;

/// <summary>models\river_N.* and height_patches\* from the ECRiverSpline entities of the AK layers.</summary>
public sealed class RiversStep : ICampaignBuildStep
{
    /// <summary>World units per lf pixel along x and z in the props/hex world (vanilla 595.1 / 7136, 541.786 / 5620).</summary>
    public const double WorldPerPixelX = 595.1 / 7136, WorldPerPixelZ = 541.78619 / 5620;

    public string Name => "rivers";
    public string ReplacesBobAction => "Terrain / Terry file (models\\river_N, height_patches)";
    public IReadOnlyList<string> DependsOn => ["rasters"];

    public IReadOnlyList<string> CheckInputs(CampaignBuildContext ctx)
    {
        var missing = new List<string>();
        if (!File.Exists(ctx.OutFile("lf_height_map.compressed_map"))) missing.Add("missing lf_height_map.compressed_map (run step 'rasters')");
        if (!Directory.Exists(ctx.Paths.AkTerrainDir)) missing.Add($"missing {ctx.Paths.AkTerrainDir}");
        else if (RiverLayers(ctx).Count == 0) missing.Add("no layer with ECRiverSpline entities in the AK map folder");
        return missing;
    }

    public StepResult Run(CampaignBuildContext ctx)
    {
        var sw = Stopwatch.StartNew();
        var notes = new List<string>();
        var lf = CompressedMap.Read(ctx.OutFile("lf_height_map.compressed_map"));
        var worldW = (float)(lf.Raster.Width * WorldPerPixelX);
        var worldH = (float)(lf.Raster.Height * WorldPerPixelZ);
        // terrain height for terrain_relative splines: props-world z maps onto the square-pixel terrain grid
        var terrainH = lf.Raster.Height / 4 * GlobalMeshStep.TileSize;
        var sampler = new LfSampler(lf, lf.Raster.Width / 4 * GlobalMeshStep.TileSize, terrainH, GlobalMeshStep.TileSize);
        double Terrain(double x, double z) => sampler.Height((float)x, (float)(z * terrainH / worldH));

        var rivers = RiverLayers(ctx).SelectMany(RiverBuilder.ReadLayer).OrderBy(r => r.Number).ToList();
        var duplicates = rivers.GroupBy(r => r.Number).Where(g => g.Count() > 1).Select(g => g.Key).ToList();
        if (duplicates.Count > 0) throw new InvalidDataException($"river numbers used twice (entity names river_N): {string.Join(", ", duplicates)}");

        var models = ctx.OutFile("models");
        var patchesDir = ctx.OutFile("height_patches");
        Directory.CreateDirectory(models);
        Directory.CreateDirectory(patchesDir);
        foreach (var old in Directory.EnumerateFiles(models, "river_*").Concat(Directory.EnumerateFiles(patchesDir, "river_*")))
            File.Delete(old);

        var written = new List<string>();
        var collection = new HeightPatchCollection();
        foreach (var river in rivers)
        {
            var sections = RiverBuilder.Sample(river, Terrain);
            if (sections.Count < 2) { notes.Add($"{river.Name}: fewer than 2 cross-sections, skipped"); continue; }
            var model = RiverBuilder.BuildModel(sections, worldW, worldH);
            var mesh = Path.Combine(models, $"river_{river.Number}.wsmodel.rigid_model_v2");
            model.Write(mesh);
            var wsmodel = Path.Combine(models, $"river_{river.Number}.wsmodel");
            File.WriteAllText(wsmodel, WsModel.River(ctx.MapName, river.Number, river.Material));
            written.AddRange([mesh, wsmodel]);

            foreach (var (name, raster, header, minX, minZ, maxX, maxZ) in RiverBuilder.HeightPatches(model, river.Number))
            {
                var file = Path.Combine(patchesDir, name + ".compressed_map");
                CompressedMap.Write(file, raster, header);
                written.Add(file);
                collection.Patches.Add(new HeightPatchCollection.Patch(HeightPatchCollection.PatchPath(ctx.MapName, name), minX, minZ, maxX, maxZ));
            }
        }
        var collectionPath = Path.Combine(patchesDir, "rivers.height_patch_collection");
        collection.Write(collectionPath);
        written.Add(collectionPath);
        notes.Add($"{rivers.Count} rivers, {collection.Patches.Count} height patches");
        return new StepResult(Name, written, notes, sw.Elapsed);
    }

    private static List<string> RiverLayers(CampaignBuildContext ctx) =>
        Directory.EnumerateFiles(ctx.Paths.AkTerrainDir, "*.layer")
            .Where(f => File.ReadLines(f).Take(4000).Any(l => l.Contains("<ECRiverSpline", StringComparison.Ordinal)))
            .ToList();
}
