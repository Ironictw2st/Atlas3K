using Atlas3K.Formats.Packs;
static class TileFiles
{
    public static void Run(string folder)
    {
        var packs = PackSet.OpenVanilla(@"C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\data");
        var p = PackFile.Normalize(folder);
        foreach (var k in packs.Packs.SelectMany(x => x.Entries.Keys).Where(k => k.StartsWith(p, StringComparison.Ordinal)).Distinct())
            Console.WriteLine($"{k} {packs.TryRead(k)?.Length}");
    }
}
