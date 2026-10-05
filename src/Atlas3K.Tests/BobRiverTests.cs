using Atlas3K.Core;
using Atlas3K.Core.Campaign;
using Atlas3K.Core.Campaign.Rivers;
using Atlas3K.Formats.Maps;
using Atlas3K.Formats.Models;

namespace Atlas3K.Tests;

/// <summary>BOB's own river geometry (BobRiver) against BOB's main190 "Terry file" output. The data tests need the 190E
/// assembly kit and the saved BOB run (output/bob_runs/frida_rivers2_main190_bob_terrain, 2026-10-05) and skip
/// without them.</summary>
public class BobRiverTests
{
    private static readonly ProjectPaths Main190 = new()
    {
        AssemblyKitRoot = new ProjectPaths().AssemblyKitRoot + "_190E",
        MapName = "3k_190e_expanded_map",
    };
    private static string BobRun => Path.Combine(Main190.OutputRoot, "bob_runs", "frida_rivers2_main190_bob_terrain");

    /// <summary>Bytes BOB leaves uninitialised: LOD padding and two material bytes; they differ between BOB runs.</summary>
    private static readonly int[] Uninitialised = [0xA5, 0xA6, 0xA7, 0x31A, 0x31B];

    [Fact]
    public void HalfBits_MatchesIeeeOnRepresentableValues_AndBobsRounding()
    {
        foreach (var v in new[] { 0f, 1f, -2.5f, 463.5f, 1.4150390625f, 0.0001220703125f, 65504f })
            Assert.Equal(BitConverter.HalfToUInt16Bits((Half)v), BobRiver.HalfBits(v));
        Assert.Equal(0x7c00, BobRiver.HalfBits(1e6f));                          // overflow → infinity
        // BOB adds ((v - 1) & v) & 0x1fff (the dropped bits without their lowest set bit) before dropping 13 bits, so
        // an exact tie truncates: 1 + 3·2^-11 gives 0x3c01 where IEEE ties-to-even gives 0x3c02
        var tie = BitConverter.UInt32BitsToSingle(0x3f803000);
        Assert.Equal(0x3c02, BitConverter.HalfToUInt16Bits((Half)tie));
        Assert.Equal(0x3c01, BobRiver.HalfBits(tie));
        Assert.Equal(0x3c02, BobRiver.HalfBits(BitConverter.UInt32BitsToSingle(0x3f803800)));   // above the tie: up
    }

    [Fact]
    public void Spline_DegenerateEndsUseMidpointsAndStraightLength()
    {
        var s = new BobRiver.Spline();
        s.Add([0, 0, 0], [0, 0, 0], [3, 0, 4], [6, 0, 8]);
        Assert.Equal([1.5f, 0f, 2f], s.Segments[0][1]);                          // p1 = (p2 + p0) / 2
        Assert.Equal(10f, s.Lengths[0]);
        var ts = s.Optimise();
        Assert.Equal(0f, ts[0]);
        Assert.Contains(1f, ts);
    }

    [Fact]
    public void Main190_RiverModels_MatchBobApartFromUninitialisedBytes()
    {
        if (!Directory.Exists(Path.Combine(BobRun, "models")) || !Directory.Exists(Main190.AkTerrainDir)) return;
        var outDir = Path.Combine(Path.GetTempPath(), "atlas3k_bobriver_" + Guid.NewGuid().ToString("N"));
        try
        {
            var ctx = new CampaignBuildContext(Main190, outDir);
            var result = new RiversStep().Run(ctx);
            Assert.Contains(result.Notes, n => n.StartsWith("river geometry: BOB's", StringComparison.Ordinal));
            var reference = Directory.GetFiles(Path.Combine(BobRun, "models"));
            Assert.Equal(48, reference.Length);
            foreach (var file in reference)
            {
                var bob = File.ReadAllBytes(file);
                var ours = File.ReadAllBytes(ctx.OutFile("models", Path.GetFileName(file)));
                if (file.EndsWith(".rigid_model_v2", StringComparison.Ordinal))
                    foreach (var i in Uninitialised) bob[i] = ours[i];
                Assert.True(bob.AsSpan().SequenceEqual(ours), Path.GetFileName(file));
            }
        }
        finally { if (Directory.Exists(outDir)) Directory.Delete(outDir, true); }
    }

    /// <summary>BOB rasterises the river models already on disk when its Terry file run starts (here the native models
    /// the kit held, saved in output/backups/main190_working_before_frida_rivers2_*): every patch file and the
    /// collection must come out byte-identical from those models.</summary>
    [Fact]
    public void Main190_HeightPatches_MatchBobByteForByte()
    {
        var backups = Path.Combine(Main190.OutputRoot, "backups");
        var source = Directory.Exists(backups)
            ? Directory.GetDirectories(backups, "main190_working_before_frida_rivers2_*").Select(d => Path.Combine(d, "terrain", "models")).FirstOrDefault(Directory.Exists)
            : null;
        if (source is null || !Directory.Exists(Path.Combine(BobRun, "height_patches"))) return;
        var collection = new HeightPatchCollection();
        var count = 0;
        foreach (var file in Directory.GetFiles(source, "river_*.wsmodel.rigid_model_v2")
                     .OrderBy(f => int.Parse(Path.GetFileName(f).Split('_', '.')[1])))
        {
            var number = int.Parse(Path.GetFileName(file).Split('_', '.')[1]);
            foreach (var (name, raster, header, minX, minZ, maxX, maxZ) in BobRiver.HeightPatches(RigidModelV2.Read(file), number))
            {
                var bob = File.ReadAllBytes(Path.Combine(BobRun, "height_patches", name + ".compressed_map"));
                Assert.True(bob.AsSpan().SequenceEqual(CompressedMap.Encode(raster, header)), name);
                collection.Patches.Add(new HeightPatchCollection.Patch(HeightPatchCollection.PatchPath(Main190.MapName, name), minX, minZ, maxX, maxZ));
                count++;
            }
        }
        Assert.Equal(87, count);
        Assert.Equal(File.ReadAllBytes(Path.Combine(BobRun, "height_patches", "rivers.height_patch_collection")), collection.ToBytes());
    }
}
