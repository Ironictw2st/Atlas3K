using Atlas3K.Core.Campaign.Camera;
using Atlas3K.Formats.Maps;
using Atlas3K.Formats.Packs;
static class MeshBounds
{
    public static void Run()
    {
        var packs = PackSet.OpenVanilla(@"C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\data");
        var prefix = PackFile.Normalize(TileDatabase.Folder);
        var db = TileDatabase.Load(packs.Packs.SelectMany(p => p.Entries.Keys).Where(k => k.StartsWith(prefix, StringComparison.Ordinal)).Distinct().Select(k => packs.TryRead(k)).OfType<byte[]>());
        foreach (var name in new[] { @"terrain\tiles\campaign\roads_tracks\turn4_a\", @"terrain\tiles\campaign\blockout_cliff\turn2\", @"terrain\tiles\campaign\river\turn4_a\", @"terrain\tiles\campaign\generic\generic_1x1\" })
        {
            var t = db.GetValueOrDefault(TileDatabase.NormalisePath(name));
            var m = packs.TryRead(name + "mesh.rigid_model_v2");
            Console.WriteLine($"{name} size {t?.Width}x{t?.Height} mesh {(m is null ? "none" : string.Join(",", CameraHeightField.ModelBounds(m).Select(v => v.ToString("G6"))))}");
        }
    }
}
