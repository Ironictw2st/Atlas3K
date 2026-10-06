namespace Atlas3K.Core.Battle.Build;

/// <summary>
/// Paths of one battle map's native build. Sources are the kit's raw_data (the battle map folder and its
/// <c>_assembly_kit</c> tile project, which share the map id); outputs go under <see cref="OutRoot"/> in BOB's
/// working_data layout, so a native folder can be compared file by file with BOB's (<see cref="BobMapDir"/> etc.).
/// Steps only read the kit; nothing is written into raw_data or working_data.
/// </summary>
public sealed class BattleBuildContext
{
    public BattleBuildContext(string kitRoot, string mapId, string outRoot)
    {
        KitRoot = Path.GetFullPath(kitRoot);
        MapId = mapId;
        OutRoot = Path.GetFullPath(outRoot);
    }

    /// <summary>The assembly kit folder (the one holding raw_data and working_data).</summary>
    public string KitRoot { get; }

    /// <summary>The map folder name under terrain/battles (for kit-made maps the tile project's guid).</summary>
    public string MapId { get; }

    /// <summary>Output root; mirrors working_data (terrain/battles/..., terrain/tiles/battle/...).</summary>
    public string OutRoot { get; }

    /// <summary>The tile project folder name under terrain/tiles/battle/_assembly_kit (the map id for kit-made maps).</summary>
    public string TileId { get; init; } = "";

    string Tile => TileId.Length > 0 ? TileId : MapId;

    public string RawData => Path.Combine(KitRoot, "raw_data");
    public string WorkingData => Path.Combine(KitRoot, "working_data");

    /// <summary>raw_data/terrain/battles/&lt;id&gt;: tile_map.png, climate_map.png, explicit_tiles.txt, lf_heights.tif, lf_sea_heights.tif.</summary>
    public string SourceMapDir => Path.Combine(RawData, "terrain", "battles", MapId);

    /// <summary>raw_data/terrain/tiles/battle/_assembly_kit/&lt;tile&gt;: the Terry tile project (.terry, .layer, TIFs).</summary>
    public string SourceTileDir => Path.Combine(RawData, "terrain", "tiles", "battle", "_assembly_kit", Tile);

    /// <summary>BOB's output map folder (reference for parity; may be stale).</summary>
    public string BobMapDir => Path.Combine(WorkingData, "terrain", "battles", MapId);

    /// <summary>BOB's output tile folder (reference for parity; may be stale).</summary>
    public string BobTileDir => Path.Combine(WorkingData, "terrain", "tiles", "battle", "_assembly_kit", Tile);

    /// <summary>BOB's tile database folder (TILES/_assembly_kit_&lt;tile&gt;.bin/.xml).</summary>
    public string BobTileDbDir => Path.Combine(WorkingData, "terrain", "tiles", "battle", "_tile_database", "TILES");

    public string OutMapDir => Path.Combine(OutRoot, "terrain", "battles", MapId);
    public string OutTileDir => Path.Combine(OutRoot, "terrain", "tiles", "battle", "_assembly_kit", Tile);
    public string OutTileDbDir => Path.Combine(OutRoot, "terrain", "tiles", "battle", "_tile_database", "TILES");

    /// <summary>The tile database entry's file name stem: _assembly_kit_&lt;tile&gt;.</summary>
    public string TileDbStem => "_assembly_kit_" + Tile;

    /// <summary>The tile project's .terry file (the one Terry saves; there is exactly one per tile folder).</summary>
    public string TerryFile =>
        Directory.EnumerateFiles(SourceTileDir, "*.terry").SingleOrDefault()
        ?? throw new FileNotFoundException($"no .terry in {SourceTileDir}");

    /// <summary>Shared values steps hand to later steps (e.g. decoded heights), keyed by name.</summary>
    public Dictionary<string, object> Shared { get; } = [];

    public void EnsureOutDirs()
    {
        Directory.CreateDirectory(OutMapDir);
        Directory.CreateDirectory(OutTileDir);
        Directory.CreateDirectory(OutTileDbDir);
    }
}
