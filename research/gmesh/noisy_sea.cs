#:project ../../src/Atlas3K.Formats/Atlas3K.Formats.csproj
// MESH_SPLITTER trigger: copy a lf_sea_height_map.compressed_map with deterministic noise added, so the merger keeps
// most sea grid vertices and big sea meshes go over 65,000 vertices (main190 sea_mesh_54 is at 62,561 unperturbed).
// (the repo global.json pins SDK 9: copy this file out of the repo, with an absolute #:project path, for SDK 10)
// usage: dotnet run noisy_sea.cs <in.compressed_map> <out.compressed_map> [amplitude in u16 steps, default 4000]
using Atlas3K.Formats.Maps;

var map = CompressedMap.Read(args[0]);
var amp = args.Length > 2 ? int.Parse(args[2]) : 4000;
var rng = new Random(12345);
var d = map.Raster.Data;
for (var i = 0; i < d.Length; i++)
    d[i] = (ushort)Math.Clamp(d[i] + rng.Next(-amp, amp + 1), 0, 65535);
CompressedMap.Write(args[1], map.Raster, map.Header, map.Version, map.TileWidth);
Console.WriteLine($"{map.Raster.Width}x{map.Raster.Height} +/-{amp} -> {args[1]}");
