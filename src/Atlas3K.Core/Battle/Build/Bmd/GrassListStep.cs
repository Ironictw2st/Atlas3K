using System.Globalization;
using System.Xml.Linq;
using Atlas3K.Core.Battle.Build.Meshes;

namespace Atlas3K.Core.Battle.Build.Bmd;

/// <summary>
/// &lt;climate&gt;.grass_list.bin (BOB Vegetation "Generate Grass", bob_vegetation FUN_180003690): for every climate of
/// the tile's climate_mask, <see cref="GrassGenerator"/> over the Blend8 map with the project's grass_seed and the game's
/// grass_generation_spec.xml, heights from the Height map. A climate whose grass is empty gets no file, and outfield
/// tiles (tile_database infield_tile="false") get none (BOB skips them). Runs before bmd_data, which references the lists.
/// </summary>
[BattleStepOrder(310)]
public sealed class GrassListStep : IBattleBuildStep
{
    public string Name => "grass_list";

    public void Run(BattleBuildContext ctx, Action<string> log)
    {
        var climates = TileProject.Climates(ctx);
        foreach (var c in climates)
        {
            var stale = Path.Combine(ctx.OutTileDir, $"{c}.grass_list.bin");
            if (File.Exists(stale)) File.Delete(stale);
        }
        var project = TerryTileProject.Load(ctx.TerryFile);
        if (!project.InfieldTile) { log("grass_list: outfield tile, no grass (as BOB)"); return; }
        if (project.HeightTif is null) { log("grass_list: no Height map TIF, no grass"); return; }
        if (TileBlend.Read(ctx.SourceTileDir) is not { } blend) { log("grass_list: no blend map TIF, no grass"); return; }
        if (project.Masked) log("grass_list: the tile has a cell mask; masked cells are not excluded yet (unverified against BOB)");

        var inner = XDocument.Load(ctx.TerryFile).Descendants("data").First(d => d.Attribute("climate_mask") is not null);
        var textures = Enumerable.Range(0, 8).Select(i => (string?)inner.Attribute($"texture_channel_{i}") ?? "").ToList();
        var seed = uint.Parse((string?)inner.Element("procedural")?.Attribute("grass_seed") ?? "0", CultureInfo.InvariantCulture);
        var specXml = ctx.ReadVfs(GrassSpec.PackPath) ?? throw new FileNotFoundException(GrassSpec.PackPath);
        var spec = GrassSpec.Parse(System.Text.Encoding.UTF8.GetString(specXml));
        var weights = GrassGenerator.BlendWeights(blend.Data, 8);
        var (hw, _, heights) = TerryTileProject.ReadFloatTif(project.HeightTif);

        foreach (var climate in climates)
        {
            var items = GrassGenerator.Generate(weights, blend.W, blend.H, 8, textures, spec, climate, seed,
                project.TilesWide, project.TilesHigh, project.TriangleDensity);
            var bytes = GrassGenerator.WriteList(items, spec, heights, hw, project.TilesWide, project.TilesHigh, project.TriangleDensity);
            if (bytes is null) { log($"grass_list: {climate}: no grass"); continue; }
            File.WriteAllBytes(Path.Combine(ctx.OutTileDir, $"{climate}.grass_list.bin"), bytes);
            log($"grass_list: {climate}: {items.Count} positions generated");
        }
    }
}
