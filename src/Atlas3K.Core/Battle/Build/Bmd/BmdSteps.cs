using System.Xml.Linq;
using Atlas3K.Formats.Battle;

namespace Atlas3K.Core.Battle.Build.Bmd;

/// <summary>Tile project facts the bmd and vegetation steps share: climates (.terry climate_mask) and the tile's pack
/// path prefix.</summary>
public static class TileProject
{
    public static IReadOnlyList<string> Climates(BattleBuildContext ctx)
    {
        var data = XDocument.Load(ctx.TerryFile).Descendants("data").FirstOrDefault(d => d.Attribute("climate_mask") is not null);
        return ((string?)data?.Attribute("climate_mask") ?? "").Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
    }

    /// <summary>terrain/tiles/battle/_assembly_kit/&lt;tile&gt;/ (forward slashes, as BOB writes references).</summary>
    public static string PackFolder(BattleBuildContext ctx) =>
        $"terrain/tiles/battle/_assembly_kit/{Path.GetFileName(ctx.OutTileDir)}/";

    public static void WriteBmd(string path, BmdNode root)
    {
        File.WriteAllBytes(path, BattleBmd.Write(root));
        File.WriteAllText(Path.ChangeExtension(path, ".xml"), BattleBmd.ToXml(root));
    }
}

/// <summary>bmd_data.bin/.xml (BOB TerryTile "Process Terry tile (excluding heightmap)"): the layers' exported
/// entities, the forest ambush hints (<see cref="ForestHints"/>), plus references to the grass and tree lists the
/// vegetation steps wrote.</summary>
[BattleStepOrder(340)]
public sealed class BattleBmdDataStep : IBattleBuildStep
{
    public string Name => "bmd_data";

    public void Run(BattleBuildContext ctx, Action<string> log)
    {
        var catalog = BmdMetaCatalog.FromKit(ctx.RawData);
        var scene = TileScene.Load(ctx.TerryFile);
        var folder = TileProject.PackFolder(ctx);
        var climates = TileProject.Climates(ctx);
        List<(string, string)> Lists(string ext) => climates.Where(c => File.Exists(Path.Combine(ctx.OutTileDir, $"{c}.{ext}")))
            .Select(c => (c, $"{folder}{c}.{ext}")).ToList();
        var builder = new BattleBmdBuilder(catalog);
        var forest = ForestHints.Compute(ctx);
        var root = builder.BuildData(scene, Lists("grass_list.bin"), Lists("tree_list.bin"), forest);
        TileProject.WriteBmd(Path.Combine(ctx.OutTileDir, "bmd_data.bin"), root);
        foreach (var n in builder.Notes) log($"bmd_data: {n}");
    }
}

/// <summary>&lt;climate&gt;_procedural_bmd_data.bin/.xml (BOB Vegetation "Procedural Generation"): the procedural
/// vegetation's scene objects. The procedural ground-type layer is not saved with the project (serializable="0"), so
/// BOB's headless run places 0 positions and writes the empty bmd for every climate of the mask; that is all the
/// corpus has. Placed procedural objects (VFX and trees from Terry's live session) are not reproduced.</summary>
[BattleStepOrder(320)]
public sealed class BattleProceduralBmdStep : IBattleBuildStep
{
    public string Name => "procedural_bmd";

    public void Run(BattleBuildContext ctx, Action<string> log)
    {
        foreach (var climate in TileProject.Climates(ctx))
            TileProject.WriteBmd(Path.Combine(ctx.OutTileDir, $"{climate}_procedural_bmd_data.bin"), BattleBmdBuilder.Empty(null));
    }
}

/// <summary>bmd_nogo_data.bin/.xml (BOB TerryTile "Process Terry tile (heightmap)"): an empty bmd whose
/// TERRAIN_OUTLINES are the no-go outlines of the tile's height field (<see cref="NogoOutlines"/>): the Height TIF
/// cropped to the vertex grid (<see cref="Meshes.TerryTileProject.HeightField"/>), one cell = tile size / (width − 1)
/// (2 world units for an 8x8 tile).</summary>
[BattleStepOrder(330)]
public sealed class BattleNogoStep : IBattleBuildStep
{
    public string Name => "bmd_nogo";

    public void Run(BattleBuildContext ctx, Action<string> log)
    {
        var project = Meshes.TerryTileProject.Load(ctx.TerryFile);
        var field = project.HeightField(out var w, out var h);
        var cell = project.TilesWide * 256f / (w - 1);
        var root = BattleBmdBuilder.Empty(null);
        var outlines = root.Child("TERRAIN_OUTLINES");
        foreach (var o in NogoOutlines.Compute(field, w, h, cell))
            outlines.Children.Add(BmdMake.Node("EMPIRE_OUTLINE", "", o.Select(p => BmdMake.Node("position", "OUTLINE", p.X, p.Y)).ToList()));
        TileProject.WriteBmd(Path.Combine(ctx.OutTileDir, "bmd_nogo_data.bin"), root);
        log($"bmd_nogo: {outlines.Children.Count} terrain outlines");
    }
}
