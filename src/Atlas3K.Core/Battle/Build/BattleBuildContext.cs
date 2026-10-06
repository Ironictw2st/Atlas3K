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

    /// <summary>The tile project's folder name / database name: <see cref="TileId"/>, else the map id.</summary>
    public string TileFolder => Tile;

    public string RawData => Path.Combine(KitRoot, "raw_data");
    public string WorkingData => Path.Combine(KitRoot, "working_data");

    /// <summary>raw_data/terrain/battles/&lt;id&gt;: tile_map.png, climate_map.png, explicit_tiles.txt, lf_heights.tif, lf_sea_heights.tif.</summary>
    public string SourceMapDir { get => _SourceMapDir ?? Path.Combine(RawData, "terrain", "battles", MapId); init => _SourceMapDir = value; }
    private readonly string? _SourceMapDir;

    /// <summary>raw_data/terrain/tiles/battle/_assembly_kit/&lt;tile&gt;: the Terry tile project (.terry, .layer, TIFs).</summary>
    public string SourceTileDir { get => _SourceTileDir ?? Path.Combine(RawData, "terrain", "tiles", "battle", "_assembly_kit", Tile); init => _SourceTileDir = value; }
    private readonly string? _SourceTileDir;

    /// <summary>BOB's output map folder (reference for parity; may be stale).</summary>
    public string BobMapDir { get => _BobMapDir ?? Path.Combine(WorkingData, "terrain", "battles", MapId); init => _BobMapDir = value; }
    private readonly string? _BobMapDir;

    /// <summary>BOB's output tile folder (reference for parity; may be stale).</summary>
    public string BobTileDir { get => _BobTileDir ?? Path.Combine(WorkingData, "terrain", "tiles", "battle", "_assembly_kit", Tile); init => _BobTileDir = value; }
    private readonly string? _BobTileDir;

    /// <summary>BOB's tile database folder (TILES/_assembly_kit_&lt;tile&gt;.bin/.xml).</summary>
    public string BobTileDbDir { get => _BobTileDbDir ?? Path.Combine(WorkingData, "terrain", "tiles", "battle", "_tile_database", "TILES"); init => _BobTileDbDir = value; }
    private readonly string? _BobTileDbDir;

    public string OutMapDir => Path.Combine(OutRoot, "terrain", "battles", MapId);
    public string OutTileDir => Path.Combine(OutRoot, "terrain", "tiles", "battle", "_assembly_kit", Tile);
    public string OutTileDbDir => Path.Combine(OutRoot, "terrain", "tiles", "battle", "_tile_database", "TILES");

    /// <summary>The tile database entry's file name stem: _assembly_kit_&lt;tile&gt;.</summary>
    public string TileDbStem => "_assembly_kit_" + Tile;

    /// <summary>The tile project's .terry file (the one Terry saves; there is exactly one per tile folder).</summary>
    public string TerryFile =>
        Directory.EnumerateFiles(SourceTileDir, "*.terry").SingleOrDefault()
        ?? throw new FileNotFoundException($"no .terry in {SourceTileDir}");

    /// <summary>Where Terry saved the tile's database entry (an input BOB reads and rewrites): the kit's
    /// working_data/terrain/tiles/battle/_tile_database/TILES by default.</summary>
    public string TerryTileDbDir { get => _TerryTileDbDir ?? Path.Combine(WorkingData, "terrain", "tiles", "battle", "_tile_database", "TILES"); init => _TerryTileDbDir = value; }
    private readonly string? _TerryTileDbDir;

    /// <summary>The game's data folder (vanilla packs), for the files BOB reads from its VFS (tile database settings,
    /// tiles listed in explicit_tiles.txt, ...).</summary>
    public string GameDataDir { get; init; } = Defaults.GameData;

    private Atlas3K.Formats.Packs.PackSet? _packs;

    /// <summary>The vanilla packs (opened on first use).</summary>
    public Atlas3K.Formats.Packs.PackSet Packs => _packs ??= Atlas3K.Formats.Packs.PackSet.OpenVanilla(GameDataDir);

    /// <summary>A game file as BOB sees it: the kit's working_data copy if there is one, else the vanilla packs; null when
    /// neither has it. <paramref name="path"/> is a pack path (forward or back slashes).</summary>
    public byte[]? ReadVfs(string path)
    {
        var loose = Path.Combine(WorkingData, path.Replace('\\', '/'));
        return File.Exists(loose) ? File.ReadAllBytes(loose) : Packs.TryRead(path.Replace('\\', '/'));
    }

    /// <summary>Shared values steps hand to later steps (e.g. decoded heights), keyed by name.</summary>
    public Dictionary<string, object> Shared { get; } = [];

    public void EnsureOutDirs()
    {
        Directory.CreateDirectory(OutMapDir);
        Directory.CreateDirectory(OutTileDir);
        Directory.CreateDirectory(OutTileDbDir);
    }
}
