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
/// entities, plus references to the grass and tree lists the vegetation steps wrote.</summary>
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
        var root = builder.BuildData(scene, Lists("grass_list.bin"), Lists("tree_list.bin"));
        TileProject.WriteBmd(Path.Combine(ctx.OutTileDir, "bmd_data.bin"), root);
        foreach (var n in builder.Notes) log($"bmd_data: {n}");
    }
}
