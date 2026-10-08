using Atlas3K.Core.Editing;

namespace Atlas3K.Core.Collab;

/// <summary>Where a change package's base comes from.</summary>
public static class PatchSources
{
    /// <summary>The map folder against a copy of it (e.g. the folder as it was handed out, or the vanilla map).</summary>
    public static List<PatchPackage.Source> FromFolder(ProjectPaths paths, string baseDir)
    {
        var mapDir = paths.AkTerrainDir;
        var names = Files(mapDir).Union(Files(baseDir), StringComparer.OrdinalIgnoreCase);
        return names.Select(n =>
        {
            var b = Path.Combine(baseDir, n);
            var a = Path.Combine(mapDir, n);
            return new PatchPackage.Source(Rel(paths, a), File.Exists(b) ? b : null, File.Exists(a) ? a : null);
        }).ToList();
    }

    private static IEnumerable<string> Files(string dir) =>
        Directory.Exists(dir)
            ? Directory.EnumerateFiles(dir, "*", SearchOption.AllDirectories).Select(f => Path.GetRelativePath(dir, f))
                .Where(f => !MapMerge.IsPrivate(f) && !f.EndsWith(".tmp", StringComparison.OrdinalIgnoreCase))
            : [];

    /// <summary>The map's edit journals (props/entities, tile map, terrain, blend, ...) that hold batches.</summary>
    public static List<FileJournal> Journals(ProjectPaths paths)
    {
        var leaf = Path.GetFileName(FileJournal.EditDir(paths, "x"));
        if (!Directory.Exists(paths.OutputRoot)) return [];
        return Directory.EnumerateDirectories(paths.OutputRoot)
            .Select(kind => Path.Combine(kind, leaf))
            .Where(d => File.Exists(Path.Combine(d, "journal.jsonl")))
            .Select(d => new FileJournal(d)).ToList();
    }

    /// <summary>
    /// Every kit file the map's journals changed after <paramref name="since"/>: the base is the snapshot taken before
    /// the first such batch touched it, the result the file as it is now. Files outside the kit are skipped.
    /// </summary>
    public static List<PatchPackage.Source> FromJournals(ProjectPaths paths, DateTime since)
    {
        var kit = Path.GetFullPath(paths.AssemblyKitRoot).TrimEnd('\\', '/') + Path.DirectorySeparatorChar;
        var first = new Dictionary<string, (DateTime Time, string? Snapshot)>(StringComparer.OrdinalIgnoreCase);
        foreach (var journal in Journals(paths))
            foreach (var entry in journal.History().Where(e => e.Time > since))
                foreach (var f in entry.Files)
                {
                    var full = Path.GetFullPath(f.Path);
                    if (!full.StartsWith(kit, StringComparison.OrdinalIgnoreCase) || MapMerge.IsPrivate(full)) continue;
                    if (first.TryGetValue(full, out var known) && known.Time <= entry.Time) continue;
                    var snap = f.Before is null ? null : Path.Combine(journal.Dir, entry.Seq.ToString("D5"), Path.GetFileName(full));
                    first[full] = (entry.Time, snap);
                }
        return first.Select(kv => new PatchPackage.Source(Rel(paths, kv.Key), kv.Value.Snapshot,
            File.Exists(kv.Key) ? kv.Key : null)).ToList();
    }

    public static string Rel(ProjectPaths paths, string full) =>
        Path.GetRelativePath(paths.AssemblyKitRoot, full).Replace('\\', '/');

    /// <summary>output\patch_imports\&lt;map&gt;: the undo journal of package imports and their open conflicts.</summary>
    public static string ImportDir(ProjectPaths paths) => FileJournal.EditDir(paths, "patch_imports");
}
