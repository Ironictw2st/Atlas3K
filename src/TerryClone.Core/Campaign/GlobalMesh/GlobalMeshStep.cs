using System.Collections.Concurrent;
using System.Diagnostics;
using TerryClone.Formats.Maps;
using TerryClone.Formats.Packs;

namespace TerryClone.Core.Campaign.GlobalMesh;

/// <summary>global_meshes\land_mesh_N (.rigid_model_v2 + .compressed_map) and sea_mesh_N (BOB "Global Mesh").</summary>
public sealed class GlobalMeshStep : ICampaignBuildStep
{
    /// <summary>World units per tile-map pixel on every 3K campaign map (vanilla 595.1 / 1784).</summary>
    public const float TileSize = 595.1f / 1784f;

    public string Name => "global_mesh";
    public string ReplacesBobAction => "Terrain / Global Mesh (land_mesh_N, sea_mesh_N)";
    public IReadOnlyList<string> DependsOn => ["rasters", "tile_list"];

    public IReadOnlyList<string> CheckInputs(CampaignBuildContext ctx)
    {
        var missing = new List<string>();
        foreach (var f in new[] { "lf_height_map.compressed_map", "lf_sea_height_map.compressed_map" })
            if (!File.Exists(ctx.OutFile(f))) missing.Add($"missing {f} (run step 'rasters')");
        if (TileListSource(ctx) is null) missing.Add("no tile_list.bin (output, working_data or vanilla root)");
        if (!Directory.Exists(ctx.Paths.GameDataDir)) missing.Add($"missing game data folder {ctx.Paths.GameDataDir} (tile database)");
        return missing;
    }

    public StepResult Run(CampaignBuildContext ctx)
    {
        var sw = Stopwatch.StartNew();
        var notes = new List<string>();
        var tileListPath = TileListSource(ctx)!;
        ctx.Log($"tile list {tileListPath}");
        var tiles = TileList.Read(tileListPath);

        ctx.Log("tile database...");
        var packs = PackSet.OpenVanilla(ctx.Paths.GameDataDir);
        var prefix = PackFile.Normalize(TileDatabase.Folder);
        var entries = packs.Packs.SelectMany(p => p.Entries.Keys).Where(k => k.StartsWith(prefix, StringComparison.Ordinal)).Distinct()
            .Select(k => packs.TryRead(k)).OfType<byte[]>();
        var db = TileDatabase.Load(entries);
        var coverage = new TileCoverage(tiles, db, TileSize, out var unknown);
        if (unknown.Count > 0) notes.Add($"{unknown.Count} tile paths not in the tile database (ignored): {string.Join(", ", unknown.Take(5))}");

        var land = CompressedMap.Read(ctx.OutFile("lf_height_map.compressed_map"));
        var sea = CompressedMap.Read(ctx.OutFile("lf_sea_height_map.compressed_map"));
        int tilesW = tiles.Ints[1], tilesH = tiles.Ints[2];
        if (land.Raster.Width != tilesW * 4 || land.Raster.Height != tilesH * 4)
            notes.Add($"lf {land.Raster.Width}x{land.Raster.Height} is not 4x the tile list's {tilesW}x{tilesH}");
        float worldW = tilesW * TileSize, worldH = tilesH * TileSize;
        var builder = new GlobalMeshBuilder(coverage, new LfSampler(land, worldW, worldH, TileSize),
            new LfSampler(sea, worldW, worldH, TileSize), tilesW, tilesH, TileSize);

        var per = builder.MeshesPerAxis;
        ctx.Log($"building {per}x{per} land and sea meshes...");
        var results = new ConcurrentDictionary<(MeshKind, int), GlobalMeshBuilder.MeshResult?>();
        Parallel.For(0, per * per * 2, k =>
        {
            var kind = k < per * per ? MeshKind.Land : MeshKind.Sea;
            var index = k % (per * per);
            results[(kind, index)] = builder.Build(index / per, index % per, kind);
        });

        var outDir = ctx.OutFile("global_meshes");
        Directory.CreateDirectory(outDir);
        foreach (var old in Directory.EnumerateFiles(outDir).Where(f => Path.GetFileName(f).StartsWith("land_mesh_", StringComparison.OrdinalIgnoreCase)
                                                                     || Path.GetFileName(f).StartsWith("sea_mesh_", StringComparison.OrdinalIgnoreCase)))
            File.Delete(old);
        var written = new List<string>();
        foreach (var kind in new[] { MeshKind.Land, MeshKind.Sea })
        {
            var number = 0;
            var stem = kind == MeshKind.Land ? "land_mesh_" : "sea_mesh_";
            for (var index = 0; index < per * per; index++)
            {
                if (results[(kind, index)] is not { } mesh) continue;
                var model = Path.Combine(outDir, $"{stem}{number}.rigid_model_v2");
                mesh.Model.Write(model);
                written.Add(model);
                if (mesh.HeightMap is not null)
                {
                    var cm = Path.Combine(outDir, $"{stem}{number}.compressed_map");
                    CompressedMap.Write(cm, mesh.HeightMap, mesh.HeightHeader!);
                    written.Add(cm);
                }
                number++;
            }
            notes.Add($"{number} {kind.ToString().ToLowerInvariant()} meshes");
        }
        return new StepResult(Name, written, notes, sw.Elapsed);
    }

    private static string? TileListSource(CampaignBuildContext ctx) =>
        new[] { ctx.OutFile("tile_list.bin"),
                Path.Combine(ctx.Paths.AkWorkingDir, "terrain", "campaigns", ctx.MapName, "tile_list.bin"),
                Path.Combine(ctx.Paths.TerrainDir, "tile_list.bin") }
            .FirstOrDefault(File.Exists);
}
