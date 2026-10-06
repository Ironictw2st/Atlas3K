using System.Xml.Linq;
using Atlas3K.Formats.Maps;
using Atlas3K.Formats.Packs;

namespace Atlas3K.Core.Battle.Build;

/// <summary>A placement group from raw_data/terrain/battles/tile_placement_groups.xml (PLACEMENT_GROUP v2): colour,
/// link_as_set, tile-set names and variation locations ("tiles").</summary>
public sealed record BattlePlacementGroup(string Name, byte R, byte G, byte B, string LinkAsSet, IReadOnlyList<string> TileSets,
                                          IReadOnlyList<string> Variations)
{
    public uint Rgb => (uint)(R << 16 | G << 8 | B);
}

/// <summary>
/// The battle tile database as BOB sees it through its VFS: _settings.bin and tiles\*.bin from the vanilla packs
/// (terrain/tiles/battle/_tile_database/), overlaid with the kit's working_data copies, where BOB's tile export writes
/// the _assembly_kit_&lt;id&gt; entry (TILES\ there; the VFS is case-insensitive). A native build's own entry
/// (<see cref="BattleBuildContext.OutTileDbDir"/>) replaces the kit's when present.
/// </summary>
public static class BattleTileData
{
    public const string DatabaseFolder = "terrain/tiles/battle/_tile_database/";

    public static CampaignTileDatabase LoadDatabase(BattleBuildContext ctx) => LoadDatabase(ctx, out _);

    /// <param name="looseFiles">Tile files that came from loose folders (the kit's working_data, the native output):
    /// BOB's VFS lists them after the packs' (<see cref="Campaign.TileMapCheck.TileMatchSimulator"/> listingRank).</param>
    public static CampaignTileDatabase LoadDatabase(BattleBuildContext ctx, out HashSet<string> looseFiles)
    {
        looseFiles = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var settings = ctx.ReadVfs(DatabaseFolder + "_settings.bin") ?? throw new FileNotFoundException("battle _settings.bin not found");
        var files = new Dictionary<string, byte[]>(StringComparer.OrdinalIgnoreCase);
        var prefix = PackFile.Normalize(DatabaseFolder + "tiles/");
        foreach (var key in ctx.Packs.Packs.SelectMany(p => p.Entries.Keys).Where(k => k.StartsWith(prefix, StringComparison.Ordinal) && k.EndsWith(".bin", StringComparison.Ordinal)).Distinct())
        {
            var name = key[(key.LastIndexOf('\\') + 1)..];
            if (!files.ContainsKey(name) && ctx.Packs.TryRead(key) is { } bytes) files[name] = bytes;
        }
        // the loose entries as one TILES folder lists them (lower-case ordinal); a later folder's copy of an entry wins
        var loose = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (var dir in new[] { Path.Combine(ctx.WorkingData, "terrain", "tiles", "battle", "_tile_database", "TILES") }
                     .Concat(ctx.ExtraTileDbDirs).Append(ctx.OutTileDbDir))
            if (Directory.Exists(dir))
                foreach (var f in Directory.EnumerateFiles(dir, "*.bin"))
                    loose[Path.GetFileName(f)] = f;
        foreach (var (name, f) in loose.OrderBy(kv => kv.Key.ToLowerInvariant(), StringComparer.Ordinal))
        {
            files[name] = File.ReadAllBytes(f);
            looseFiles.Add(name);
        }
        return CampaignTileDatabase.Load(settings, files.Select(kv => (kv.Key, kv.Value)));
    }

    /// <summary>tile_placement_groups.xml next to the battle map folders (raw_data/terrain/battles/), as
    /// TILE_PLACEMENT_GROUPS::load_and_merge reads it ("&lt;map folder&gt;/../tile_placement_groups.xml"); empty if
    /// there is none.</summary>
    public static List<BattlePlacementGroup> LoadPlacementGroups(string path)
    {
        if (!File.Exists(path)) return [];
        var doc = XDocument.Load(path);
        var result = new List<BattlePlacementGroup>();
        foreach (var g in doc.Root!.Element("groups")?.Elements("group") ?? [])
        {
            var c = g.Element("colour");
            byte Byte(string n) => (byte)int.Parse(c?.Element(n)?.Value.Trim() ?? "0");
            result.Add(new BattlePlacementGroup(
                g.Element("name")?.Value.Trim() ?? "", Byte("r"), Byte("g"), Byte("b"), g.Element("link_as_set")?.Value.Trim() ?? "",
                g.Element("tile_sets")?.Elements("tile_set").Select(e => e.Element("name")?.Value.Trim() ?? "").ToList() ?? [],
                g.Element("tiles")?.Elements("tile").Select(e => e.Element("name")?.Value.Trim() ?? "").ToList() ?? []));
        }
        return result;
    }

    /// <summary>explicit_tiles.txt (EDITOR_TILE_MAP::load_explicit_tiles): "x,y,location,rot" per line, y in image space
    /// (top-left of the footprint); rot 0/90/180/270 → 0x10/0x20/0x40/0x80.</summary>
    public static List<(string Location, int X, int Y, int Rotation)> LoadExplicitTiles(string path)
    {
        var result = new List<(string, int, int, int)>();
        if (!File.Exists(path)) return result;
        foreach (var raw in File.ReadAllLines(path))
        {
            var parts = raw.Split(',');
            if (parts.Length < 4) continue;
            var rot = int.Parse(parts[3].Trim()) switch { 90 => 0x20, 180 => 0x40, 270 => 0x80, _ => 0x10 };
            result.Add((parts[2].Trim(), int.Parse(parts[0].Trim()), int.Parse(parts[1].Trim()), rot));
        }
        return result;
    }
}
