using Atlas3K.Core.Battle.Build;
using Atlas3K.Core.Battle.Build.Meshes;
using Xunit;

namespace Atlas3K.Tests;

/// <summary>The native battle tile meshes (shadow / outfield / mesh, river and outfield river) against BOB's own files in
/// the battle-parity corpus. Masked: the LOD header's quality u32 (0xA4..0xA7) of every RMV2 and the river material's
/// uninitialised u32 (0x318..0x31B), as in the corpus's masks.json.</summary>
public class BattleTileMeshTests
{
    private static readonly string[] Files =
    [
        "shadow_mesh.rigid_model_v2", "outfield_mesh.rigid_model_v2", "mesh.rigid_model_v2",
        "river_mesh.wsmodel", "river_mesh.wsmodel.rigid_model_v2",
        "outfield_river_mesh.wsmodel", "outfield_river_mesh.wsmodel.rigid_model_v2",
    ];

    public static IEnumerable<object[]> Projects() =>
        Directory.Exists(BattleBmdTests.Corpus)
            ? Directory.EnumerateDirectories(BattleBmdTests.Corpus)
                .Where(d => Directory.Exists(Path.Combine(d, "src", "tile")) && Directory.Exists(Path.Combine(d, "bob_run1", "tile")))
                .Select(d => new object[] { Path.GetFileName(d) })
            : [new object[] { "" }];

    [Theory]
    [MemberData(nameof(Projects))]
    public void MatchesBob(string id)
    {
        if (id.Length == 0) return;   // corpus not available
        var project = Path.Combine(BattleBmdTests.Corpus, id);
        var outRoot = Path.Combine(Path.GetTempPath(), "atlas3k_tile_mesh_" + id);
        try
        {
            var ctx = new BattleBuildContext(TestKits.Vanilla, id, outRoot)
            {
                SourceTileDir = Path.Combine(project, "src", "tile"), SourceMapDir = Path.Combine(project, "src", "map"),
            };
            new BattleTileMeshStep().Run(ctx, _ => { });
            new BattleRiverMeshStep().Run(ctx, _ => { });
            foreach (var f in Files)
            {
                var bob = File.ReadAllBytes(Path.Combine(project, "bob_run1", "tile", f));
                var native = File.ReadAllBytes(Path.Combine(ctx.OutTileDir, f));
                Assert.Equal(bob.Length, native.Length);
                var masked = f.EndsWith(".rigid_model_v2") ? UninitialisedBytes(bob, f.Contains("river")) : [];
                for (var i = 0; i < bob.Length; i++)
                    if (!masked.Contains(i) && bob[i] != native[i]) Assert.Fail($"{id} {f}: first difference at 0x{i:X}");
            }
        }
        finally
        {
            if (Directory.Exists(outRoot)) Directory.Delete(outRoot, true);
        }
    }

    /// <summary>Bytes BOB fills from stale memory (as research/battle_build/make_masks.py): the LOD header u32 at 0xA4 and,
    /// in river models, the u32 at +624 of every mesh part (one per river).</summary>
    private static HashSet<int> UninitialisedBytes(byte[] rmv2, bool river)
    {
        var words = new HashSet<int> { 0xA4, 0xA5, 0xA6, 0xA7 };
        if (!river) return words;
        var lods = BitConverter.ToInt32(rmv2, 8);
        for (var l = 0; l < lods; l++)
        {
            var meshes = BitConverter.ToInt32(rmv2, 140 + l * 28);
            var off = BitConverter.ToInt32(rmv2, 140 + l * 28 + 12);
            for (var m = 0; m < meshes; m++)
            {
                for (var k = 0; k < 4; k++) words.Add(off + 624 + k);
                off += BitConverter.ToInt32(rmv2, off + 4);
            }
        }
        return words;
    }

    [Fact]
    public void ShadowMeshOfAHeightFieldIsEmpty()
    {
        var field = new float[17 * 17];
        var r = BattleTileMeshBuilder.Build(field, 17, 17, 2, 8, 8, 2f, BattleTileMeshBuilder.Mode.Shadow, 20f);
        Assert.Empty(r.Indices);
        Assert.Equal(140, BattleTileMeshStep.TileMeshBytes(r, 17).Length);
    }
}
