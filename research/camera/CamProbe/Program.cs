using System.Text.Json;
using Atlas3K.Core;
using Atlas3K.Core.Campaign;
using Atlas3K.Core.Campaign.Camera;

if (args.Length == 2 && args[0] == "files") { TileFiles.Run(args[1]); return; }
if (args.Contains("meshbounds")) { MeshBounds.Run(); return; }
if (args.Contains("customprobe")) { CustomProbe.Run(); return; }
if (args.Contains("sidefit")) { SideFit.Run(); return; }
if (args.Contains("leafcmp")) { LeafCmp.Run(); return; }
if (args.Contains("quadfit")) { QuadFit.Run(); return; }
if (args.Contains("invfit")) { InvFit.Run(); return; }
if (args.Contains("tilefit")) { TileFit.Run(); return; }
var paths = new ProjectPaths
{
    MapName = "3k_dlc07_main_map",
    AssemblyKitRoot = @"C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\assembly_kit",
    GameDataDir = @"C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\data",
};
var ctx = new CampaignBuildContext(paths, Environment.GetEnvironmentVariable("CAM_ROOT") ?? "Z:/tmp_cam_empty");
var notes = new List<string>();
var field = CameraHeightmapStep.BuildField(ctx, notes, out var tw, out var th);
Console.WriteLine(string.Join("\n", notes));
if (args.Contains("patches")) { PatchCompare.Run(field); return; }
if (args.Length == 3 && args[0] == "cell") { CellProbe.Run(field, tw, th, int.Parse(args[1]), int.Parse(args[2])); return; }
if (args.Contains("diffcells")) { DiffCells.Run(field, tw, th); return; }
if (args.Contains("rivers")) { RiverDump.Run(field); return; }
const string F = "Z:/Claude/TerryClone/research/bob_re/frida_out/";

// probe points
var pts = JsonDocument.Parse(File.ReadAllText(F + "probe_points.json")).RootElement.EnumerateArray().Select(p => (p[0].GetSingle(), p[1].GetSingle())).ToArray();
var bobH = JsonDocument.Parse(File.ReadAllText(F + "cam_s4d_probe.json")).RootElement.GetProperty("heights").EnumerateArray().Select(e => e.GetSingle()).ToArray();
var kinds = new Dictionary<string, int>();
int exact = 0;
var shown = 0;
for (var i = 0; i < pts.Length; i++)
{
    var (x, z) = pts[i];
    var mine = field.Height(x, z);
    if (BitConverter.SingleToInt32Bits(mine) == BitConverter.SingleToInt32Bits(bobH[i])) { exact++; continue; }
    var p = field.PatchHeight(x, z);
    var g = field.GlobalMeshHeight(x, z / CameraHeightField.ZScale);
    string k;
    if (g == float.MinValue && p < bobH[i]) k = "fallback (bob above patch)";
    else if (g == float.MinValue) k = "fallback, patch wins in mine";
    else if (p >= g) k = Math.Abs(p - bobH[i]) < 1e-4 ? "patch, near (<1e-4)" : "patch, far";
    else k = Math.Abs(g - bobH[i]) < 1e-4 ? "gm, near" : "gm, far";
    kinds[k] = kinds.GetValueOrDefault(k) + 1;
    if (k.StartsWith("fallback (") && shown++ < 12) Console.WriteLine($"  FB x {x} z {z} bob {bobH[i]} mine {mine} p {p}");
    if (k.Contains("far") && shown++ < 10) Console.WriteLine($"  {k}: x {x} z {z} bob {bobH[i]} mine {mine} p {p} g {g}");
}
Console.WriteLine($"probe points {pts.Length}: exact {exact}");
foreach (var kv in kinds.OrderByDescending(k => k.Value)) Console.WriteLine($"  {kv.Key}: {kv.Value}");

// full grid
var bob = new float[1784 * 1405];
Buffer.BlockCopy(File.ReadAllBytes(F + "cam_s4d.f32"), 0, bob, 0, bob.Length * 4);
var cells = CameraHeightmapStep.Sample(field, 1784, 1405, CameraHeightmapStep.SceneWidth(tw), CameraHeightmapStep.SceneDepth(th), 4);
int ex = 0, near = 0, mineHigh = 0, bobHigh = 0;
for (var i = 0; i < bob.Length; i++)
{
    if (BitConverter.SingleToInt32Bits(cells[i]) == BitConverter.SingleToInt32Bits(bob[i])) { ex++; continue; }
    var d = cells[i] - bob[i];
    if (Math.Abs(d) < 1e-4) near++; else if (d > 0) mineHigh++; else bobHigh++;
}
Console.WriteLine($"cells: bit-exact {100.0 * ex / bob.Length:F4}%  |d|<1e-4 {100.0 * near / bob.Length:F4}%  mine higher {100.0 * mineHigh / bob.Length:F4}%  bob higher {100.0 * bobHigh / bob.Length:F4}%");
File.WriteAllBytes("Z:/Claude/TerryClone/research/camera/native_cells.f32", cells.SelectMany(BitConverter.GetBytes).ToArray());
Console.WriteLine($"stepX {CameraHeightmapStep.SceneWidth(tw) / 1784:R} stepZ {CameraHeightmapStep.SceneDepth(th) / 1405:R}");
