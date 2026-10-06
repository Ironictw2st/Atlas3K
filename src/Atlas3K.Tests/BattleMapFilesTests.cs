using Atlas3K.Core.Battle.Build;
using Xunit;

namespace Atlas3K.Tests;

/// <summary>The native battle map-family files (tile database entry, lf / sea maps, lf_normal, climate, map_info, icon,
/// tile_list, hf_height, hf_water, blend0/1, normal, ground_types) against BOB's own files in the battle-parity corpus
/// (bob_run1), byte for byte.</summary>
public class BattleMapFilesTests
{
    public static IEnumerable<object[]> Projects() =>
        Directory.Exists(BattleBmdTests.Corpus)
            ? Directory.EnumerateDirectories(BattleBmdTests.Corpus)
                .Where(d => Directory.Exists(Path.Combine(d, "src", "tile")) && Directory.Exists(Path.Combine(d, "bob_run1")))
                .Select(d => new object[] { Path.GetFileName(d) })
            : [new object[] { "" }];

    [Theory]
    [MemberData(nameof(Projects))]
    public void MatchesBob(string id)
    {
        if (id.Length == 0 || !Directory.Exists(TestKits.Vanilla)) return;   // corpus or kit not available
        var project = Path.Combine(BattleBmdTests.Corpus, id);
        var outRoot = Path.Combine(Path.GetTempPath(), "atlas3k_battle_map_" + id);
        try
        {
            var hasMap = Directory.Exists(Path.Combine(project, "src", "map"));
            var ctx = new BattleBuildContext(TestKits.Vanilla, id, outRoot)
            {
                SourceTileDir = Path.Combine(project, "src", "tile"), SourceMapDir = Path.Combine(project, "src", "map"),
                TerryTileDbDir = Path.Combine(project, "existing", "tile_db"),
            };
            var steps = new List<string> { "tile_db", "map_info", "icon", "blend", "tile_normal", "ground_types" };
            if (hasMap) steps.AddRange(["lf", "lf_normal", "climate", "tile_list"]);
            steps.AddRange(["hf_height", "tile_meshes", "river_meshes", "hf_water"]);
            var failed = BattleMapBuild.Run(ctx, _ => { }, steps);
            Assert.Empty(failed);
            var bob = Path.Combine(project, "bob_run1");
            var pairs = new List<(string Mine, string Bob)>
            {
                (Path.Combine(ctx.OutTileDbDir, ctx.TileDbStem + ".bin"), Path.Combine(bob, "tile_db", ctx.TileDbStem + ".bin")),
                (Path.Combine(ctx.OutTileDbDir, ctx.TileDbStem + ".xml"), Path.Combine(bob, "tile_db", ctx.TileDbStem + ".xml")),
                (Path.Combine(ctx.OutMapDir, "map_info.xml"), Path.Combine(bob, "map", "map_info.xml")),
                (Path.Combine(ctx.OutMapDir, "icon.tga"), Path.Combine(bob, "map", "icon.tga")),
            };
            if (hasMap)
                foreach (var f in new[] { "lf_height_map.compressed_map", "lf_height_map.dds", "lf_sea_height_map.compressed_map",
                                          "lf_sea_height_map.dds", "lf_normal.dds", "climate_map.cm", "tile_list.bin" })
                    pairs.Add((Path.Combine(ctx.OutMapDir, f), Path.Combine(bob, "map", f)));
            pairs.Add((Path.Combine(ctx.OutTileDir, "ground_types.dds"), Path.Combine(bob, "tile", "ground_types.dds")));
            foreach (var f in new[] { "blend0.dds", "blend1.dds", "normal.dds" })
                Assert.Equal(File.Exists(Path.Combine(bob, "tile", f)), File.Exists(Path.Combine(ctx.OutTileDir, f)));
            foreach (var f in new[] { "blend0.dds", "blend1.dds", "normal.dds" })
                if (File.Exists(Path.Combine(bob, "tile", f))) pairs.Add((Path.Combine(ctx.OutTileDir, f), Path.Combine(bob, "tile", f)));
            pairs.Add((Path.Combine(ctx.OutTileDir, "hf_height_map.compressed_map"), Path.Combine(bob, "tile", "hf_height_map.compressed_map")));
            Assert.Equal(File.Exists(Path.Combine(bob, "tile", "hf_water_map.compressed_map")), File.Exists(Path.Combine(ctx.OutTileDir, "hf_water_map.compressed_map")));
            if (File.Exists(Path.Combine(bob, "tile", "hf_water_map.compressed_map")))
                pairs.Add((Path.Combine(ctx.OutTileDir, "hf_water_map.compressed_map"), Path.Combine(bob, "tile", "hf_water_map.compressed_map")));
            foreach (var (mine, theirs) in pairs)
                Assert.True(File.ReadAllBytes(mine).AsSpan().SequenceEqual(File.ReadAllBytes(theirs)), $"{id}: {Path.GetFileName(mine)} differs");
        }
        finally
        {
            if (Directory.Exists(outRoot)) Directory.Delete(outRoot, true);
        }
    }
}
