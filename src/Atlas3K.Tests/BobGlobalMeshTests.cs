using Atlas3K.Core;
using Atlas3K.Core.Campaign;
using Atlas3K.Core.Campaign.GlobalMesh;

namespace Atlas3K.Tests;

/// <summary>The global_mesh step's BOB path against BOB's main190 "Global Mesh" output. Needs the 190E assembly kit and
/// the saved BOB run (output/bob_runs/frida_gmesh2_main190_bob, 2026-10-05: global_meshes + the lf maps and tile list BOB
/// read from the main190 pack) and skips without them.</summary>
public class BobGlobalMeshTests
{
    private static readonly ProjectPaths Main190 = new()
    {
        AssemblyKitRoot = new ProjectPaths().AssemblyKitRoot + "_190E",
        MapName = "3k_190e_expanded_map",
    };
    private static string BobRun => Path.Combine(Main190.OutputRoot, "bob_runs", "frida_gmesh2_main190_bob");

    /// <summary>Bytes BOB leaves uninitialised: 0x148..0x14B on every mesh (material block), 0xA5..0xA7 on sea meshes
    /// (LOD padding); they differ between BOB runs.</summary>
    private static bool Uninitialised(string file, int i) =>
        i is >= 0x148 and <= 0x14B || (Path.GetFileName(file).StartsWith("sea_", StringComparison.Ordinal) && i is >= 0xA5 and <= 0xA7);

    [Fact]
    public void Main190_GlobalMeshes_MatchBobApartFromUninitialisedBytes()
    {
        var inputs = Path.Combine(BobRun, "inputs");
        if (!Directory.Exists(inputs) || !Directory.Exists(Path.Combine(BobRun, "global_meshes")) || !Directory.Exists(Main190.AkWorkingDir)) return;
        if (Environment.GetEnvironmentVariable("ATLAS3K_GMESH_BOB_HEIGHT") is not null) return;   // research override set
        var outDir = Path.Combine(Path.GetTempPath(), "atlas3k_bobgmesh_" + Guid.NewGuid().ToString("N"));
        try
        {
            var ctx = new CampaignBuildContext(Main190, outDir);
            Directory.CreateDirectory(ctx.TerrainOutDir);
            foreach (var f in Directory.GetFiles(inputs)) File.Copy(f, ctx.OutFile(Path.GetFileName(f)));
            var result = new GlobalMeshStep().Run(ctx);
            Assert.Contains(result.Notes, n => n.StartsWith("BOB height query", StringComparison.Ordinal));
            var reference = Directory.GetFiles(Path.Combine(BobRun, "global_meshes"));
            Assert.Equal(494, reference.Length);
            Assert.Equal(494, Directory.GetFiles(ctx.OutFile("global_meshes")).Length);
            foreach (var file in reference)
            {
                var bob = File.ReadAllBytes(file);
                var ours = File.ReadAllBytes(ctx.OutFile("global_meshes", Path.GetFileName(file)));
                Assert.True(bob.Length == ours.Length, Path.GetFileName(file));
                for (var i = 0; i < bob.Length; i++)
                    if (bob[i] != ours[i] && !Uninitialised(file, i))
                        Assert.Fail($"{Path.GetFileName(file)} differs at 0x{i:X}");
            }
        }
        finally { if (Directory.Exists(outDir)) Directory.Delete(outDir, true); }
    }
}
