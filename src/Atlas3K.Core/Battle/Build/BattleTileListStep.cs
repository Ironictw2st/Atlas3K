using Atlas3K.Core.Campaign;
using Atlas3K.Core.Campaign.TileMapCheck;
using Atlas3K.Formats.Maps;
using Atlas3K.Formats.Terry;

namespace Atlas3K.Core.Battle.Build;

/// <summary>
/// tile_list.bin of a battle map (BOB "Tilemap" with save_final_tile_map): the campaign tile matching
/// (<see cref="TileMatchSimulator"/>, WARSCAPE::EDITOR_TILE_MAP) on the battle tile database, with the battle-only
/// inputs: placement groups from raw_data/terrain/battles/tile_placement_groups.xml merged after the database's own
/// (TILE_PLACEMENT_GROUPS::load_and_merge) and explicit_tiles.txt placed first. Records and heights as the campaign
/// writer (<see cref="TileListWriter"/>); the header differs (floats 0.5, 0.5, ..., marker 0).
/// </summary>
[BattleStepOrder(150)]
public sealed class BattleTileListStep : IBattleBuildStep
{
    public string Name => "tile_list";

    public void Run(BattleBuildContext ctx, Action<string> log)
    {
        var db = BattleTileData.LoadDatabase(ctx, out var loose);
        var groupsPath = Path.Combine(Path.GetDirectoryName(ctx.SourceMapDir)!, "tile_placement_groups.xml");
        if (!File.Exists(groupsPath)) groupsPath = Path.Combine(ctx.RawData, "terrain", "battles", "tile_placement_groups.xml");
        var groups = BattleTileData.LoadPlacementGroups(groupsPath)
            .Select(g => new TileMatchSimulator.ExtraGroup(g.Rgb, g.LinkAsSet, g.TileSets, g.Variations)).ToList();
        var explicitTiles = BattleTileData.LoadExplicitTiles(Path.Combine(ctx.SourceMapDir, "explicit_tiles.txt"))
            .Select(e => new TileMatchSimulator.ExplicitTile(e.Location, e.X, e.Y, e.Rotation)).ToList();

        var map = HexTileMap.Read(Path.Combine(ctx.SourceMapDir, "tile_map.png"));
        var climate = ClimateIndices(Path.Combine(ctx.SourceMapDir, "climate_map.png"), map, db);
        var sim = new TileMatchSimulator(db, groups, f => loose.Contains(f) ? 1 : 0) {
            ExplicitTiles = explicitTiles, IsCampaign = false, Log = log,
            StopAfterPlacements = int.TryParse(Environment.GetEnvironmentVariable("ATLAS3K_BATTLE_TILE_STOP"), out var stop) ? stop : -1,
        };
        var result = sim.Run(map, climate);
        if (sim.StopAfterPlacements >= 0)
        {
            // diagnostics: ATLAS3K_BATTLE_TILE_EXPLAIN="location;x;y" explains that test in the stopped state
            if (Environment.GetEnvironmentVariable("ATLAS3K_BATTLE_TILE_EXPLAIN") is { } ex && ex.Split(';') is [var l, var ex1, var ey])
                log(sim.Explain(l, int.Parse(ex1), int.Parse(ey)));
            return;
        }
        foreach (var m in sim.Messages.Take(20)) log("tile_list: " + m);
        if (Environment.GetEnvironmentVariable("ATLAS3K_BATTLE_TILE_TRACE") is { Length: > 0 } trace)
        {
            File.WriteAllLines(trace, result.Tiles.Select(t => $"{t.Location}\t{t.X}\t{t.Y}\t{t.Rotation}\t{t.Layer}"));
            File.WriteAllLines(trace + ".db", sim.DatabaseOrder);
            for (var pass = 0; pass <= 5; pass++) File.WriteAllLines(trace + $".pass{pass}", sim.PassOrder(pass));
        }

        var byLocation = db.Tiles.GroupBy(t => t.Variations[0].Location, StringComparer.OrdinalIgnoreCase)
            .ToDictionary(g => g.Key, g => g.First(), StringComparer.OrdinalIgnoreCase);
        var placed = result.Tiles.Select(t => new PlacedTile(byLocation[t.Location], t.X, t.Y, t.Rotation, t.Climate, t.Layer));
        var lf = HeightField.FromRaster(TiffMap.ReadGray16(Path.Combine(ctx.SourceMapDir, "lf_heights.tif")));
        var sea = HeightField.FromRaster(TiffMap.ReadGray16(Path.Combine(ctx.SourceMapDir, "lf_sea_heights.tif")));
        var list = TileListWriter.Build(db, map.PixelWidth, map.PixelHeight, placed, lf, sea, t => t.UseAltLf);
        list.Floats = [0.5f, 0.5f, 1, 1, 500, 1.333f];
        list.Marker = 0;
        list.Write(Path.Combine(ctx.OutMapDir, "tile_list.bin"));
        log($"tile_list: {list.Records.Count} records, {list.Paths.Count} tiles, {result.NoTile.Count} uncovered points");
    }

    /// <summary>climate_map.png → per image pixel the database climate whose colour matches exactly, else 0
    /// (load_map_from_memory).</summary>
    private static byte[] ClimateIndices(string path, HexTileMap map, CampaignTileDatabase db)
    {
        var result = new byte[map.Pixels.Length];
        if (!File.Exists(path)) return result;
        var c = HexTileMap.Read(path);
        if (c.PixelWidth != map.PixelWidth || c.PixelHeight != map.PixelHeight) return result;
        var index = db.Climates.GroupBy(x => x.Rgb).ToDictionary(g => g.Key, g => (byte)g.First().Index);
        for (var i = 0; i < result.Length; i++) result[i] = index.GetValueOrDefault(c.Pixels[i]);
        return result;
    }
}
