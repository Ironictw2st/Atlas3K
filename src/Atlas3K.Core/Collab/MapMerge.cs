using System.Text;
using System.Xml.Linq;
using Atlas3K.Formats.Terry;

namespace Atlas3K.Core.Collab;

/// <summary>
/// Three-way merge of one map file, by type: Terry XML (.layer, .terry) per entity (<see cref="TerryXmlMerge"/>),
/// rasters (.tif, .png) per pixel (<see cref="RasterMerge"/>), anything else whole-file. Used by the git merge driver
/// (<c>Atlas3K.Cli merge-driver</c>) and by change-package import.
/// </summary>
public static class MapMerge
{
    public enum FileType { TerryXml, Raster, Other }

    /// <summary>Per-user state that never merges or syncs.</summary>
    public static bool IsPrivate(string path) =>
        path.EndsWith(".terry.user", StringComparison.OrdinalIgnoreCase);

    public static FileType TypeOf(string path)
    {
        var ext = Path.GetExtension(path).ToLowerInvariant();
        if (ext is ".layer" or ".terry") return FileType.TerryXml;
        if (RasterImage.IsRaster(path)) return FileType.Raster;
        return FileType.Other;
    }

    /// <summary>
    /// Merges theirs into ours and writes the result to <paramref name="outPath"/> (usually ours' path).
    /// <paramref name="basePath"/> null or missing = the file is new on both sides. <paramref name="name"/> is the
    /// file's project-relative name for reports.
    /// </summary>
    public static FileMergeResult Merge(string? basePath, string oursPath, string theirsPath, string outPath, string name)
    {
        var hasBase = basePath is not null && File.Exists(basePath);
        switch (TypeOf(name))
        {
            case FileType.TerryXml:
            {
                var oursText = File.ReadAllText(oursPath);
                var r = TerryXmlMerge.Merge(hasBase ? File.ReadAllText(basePath!) : null, oursText, File.ReadAllText(theirsPath), name);
                var changed = r.Text != oursText;
                if (changed || !SamePath(oursPath, outPath)) File.WriteAllText(outPath, r.Text, new UTF8Encoding(false));
                return new FileMergeResult(name, changed, r.Conflicts,
                    $"{r.TakenFromTheirs} entities from theirs ({r.Added} added, {r.Removed} removed), {r.Conflicts.Count} conflict(s)");
            }
            case FileType.Raster:
            {
                RasterImage o, t, b;
                try
                {
                    o = RasterImage.Load(oursPath);
                    t = RasterImage.Load(theirsPath);
                    b = hasBase ? RasterImage.Load(basePath!) : null!;
                }
                catch (Exception e) when (e is InvalidDataException or IOException)
                {
                    return WholeFile(basePath, oursPath, theirsPath, outPath, name);
                }
                var r = RasterMerge.Merge(hasBase ? b : null, o, t, name);
                if (!SamePath(oursPath, outPath)) File.Copy(oursPath, outPath, overwrite: true);
                var changed = r.Merged is not null && !ReferenceEquals(r.Merged, o) && r.FromTheirs > 0;
                if (changed)
                {
                    if (ReferenceEquals(r.Merged, t)) File.Copy(theirsPath, outPath, overwrite: true);
                    else r.Merged!.Save(outPath);
                }
                return new FileMergeResult(name, changed, r.Conflicts, $"{r.FromTheirs} pixel(s) from theirs, {r.Conflicts.Count} conflicting cell(s)");
            }
            default:
                return WholeFile(basePath, oursPath, theirsPath, outPath, name);
        }
    }

    private static FileMergeResult WholeFile(string? basePath, string oursPath, string theirsPath, string outPath, string name)
    {
        var o = File.ReadAllBytes(oursPath);
        var t = File.ReadAllBytes(theirsPath);
        var b = basePath is not null && File.Exists(basePath) ? File.ReadAllBytes(basePath) : null;
        if (!SamePath(oursPath, outPath)) File.WriteAllBytes(outPath, o);
        if (o.AsSpan().SequenceEqual(t) || b is not null && b.AsSpan().SequenceEqual(t))
            return new FileMergeResult(name, false, [], "unchanged");
        if (b is not null && b.AsSpan().SequenceEqual(o))
        {
            File.WriteAllBytes(outPath, t);
            return new FileMergeResult(name, true, [], "taken from theirs");
        }
        return new FileMergeResult(name, false, [new MergeConflict(name, "binary", name, "changed on both sides; kept ours")], "conflict");
    }

    private static bool SamePath(string a, string b) =>
        Path.GetFullPath(a).Equals(Path.GetFullPath(b), StringComparison.OrdinalIgnoreCase);
}

/// <summary>Resolves recorded conflicts in the merged files, to ours (no change) or theirs (from the
/// <see cref="ConflictSet"/>'s copy of theirs).</summary>
public static class ConflictResolver
{
    /// <summary>Resolves the given entries (indices; all open when null) and returns how many were resolved.</summary>
    public static int Resolve(ConflictSet set, string side, IReadOnlyCollection<int>? indices = null)
    {
        if (side is not ("ours" or "theirs")) throw new ArgumentException("side must be \"ours\" or \"theirs\"");
        var entries = set.Entries();
        var picked = entries.Where(e => !e.Resolved && (indices is null || indices.Contains(e.Index))).ToList();
        if (side == "theirs")
            foreach (var group in picked.GroupBy(e => (e.Root, e.Conflict.File)))
                ApplyTheirs(set, group.Key.Root, group.Key.File, group.Select(e => e.Conflict).ToList());
        var done = picked.Select(e => e.Index).ToHashSet();
        set.Save(entries.Select(e => done.Contains(e.Index) ? e with { Resolved = true, Resolution = side } : e).ToList());
        return done.Count;
    }

    private static void ApplyTheirs(ConflictSet set, string root, string file, List<MergeConflict> conflicts)
    {
        var path = Path.Combine(root, file.Replace('/', Path.DirectorySeparatorChar));
        var theirs = set.TheirsCopy(file);
        if (!File.Exists(theirs)) throw new FileNotFoundException($"theirs copy of {file} is missing", theirs);
        if (conflicts.Any(c => c.Kind is "header" or "size" or "binary"))
        {
            File.Copy(theirs, path, overwrite: true);
            return;
        }
        switch (MapMerge.TypeOf(file))
        {
            case MapMerge.FileType.TerryXml:
            {
                var text = File.ReadAllText(path);
                var doc = TerryXml.Parse(text);
                var mine = TerryXmlMerge.Entities(doc);
                var their = TerryXmlMerge.Entities(TerryXml.Load(theirs));
                foreach (var c in conflicts)
                {
                    var id = c.Target.Split('/')[0];
                    var t = their.GetValueOrDefault(id);
                    var o = mine.GetValueOrDefault(id);
                    if (c.Kind == "attribute" && o is not null && t is not null)
                    {
                        var key = c.Target[(id.Length + 1)..];
                        var dot = key.LastIndexOf('.');
                        var (comp, attr) = dot < 0 ? ("", key) : (key[..dot], key[(dot + 1)..]);
                        var target = comp.Length == 0 ? o : o.Element(comp.Split('#')[0]);
                        var source = comp.Length == 0 ? t : t.Element(comp.Split('#')[0]);
                        target?.SetAttributeValue(attr, (string?)source?.Attribute(attr));
                    }
                    else if (t is null) o?.Remove();
                    else if (o is not null) o.ReplaceWith(new XElement(t));
                    else if (doc.Descendants("entity").FirstOrDefault()?.Parent is { } container) container.Add(new XElement(t));
                    mine = TerryXmlMerge.Entities(doc);
                }
                File.WriteAllText(path, TerryXml.ToText(doc.Root!, TerryXml.NewlineOf(text)), new UTF8Encoding(false));
                break;
            }
            case MapMerge.FileType.Raster:
            {
                var mine = RasterImage.Load(path);
                var their = RasterImage.Load(theirs);
                var data = (byte[])mine.Data.Clone();
                foreach (var c in conflicts.Where(c => c.Rect is not null)) RasterMerge.CopyRect(their, data, c.Rect!);
                mine.WithData(data).Save(path);
                break;
            }
            default:
                File.Copy(theirs, path, overwrite: true);
                break;
        }
    }
}
