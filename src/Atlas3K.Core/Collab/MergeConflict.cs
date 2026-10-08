using System.Text.Json;
using System.Text.Json.Serialization;

namespace Atlas3K.Core.Collab;

/// <summary>
/// One thing a three-way map merge could not decide. <see cref="Kind"/>:
///   entity    both sides changed (or one deleted) the same entity in incompatible ways; Target = entity id
///   attribute both sides set one attribute to different values; Target = "id/Component.attribute"
///   header    the file's non-entity part (layer version, project settings) changed on both sides
///   pixels    both sides changed the same pixels of a raster differently; Rect = [x, y, w, h] in pixels
///   size      raster dimensions differ between the sides
///   binary    a file Atlas3K cannot merge changed on both sides
/// The merged file holds "ours" for every conflict until it is resolved (<see cref="ConflictResolver"/>).
/// Location is the world [x, z] when known, for jumping to it on the map.
/// </summary>
public sealed record MergeConflict(string File, string Kind, string Target, string Detail,
                                   string? Base = null, string? Ours = null, string? Theirs = null,
                                   double[]? Location = null, int[]? Rect = null);

/// <summary>Result of merging one file.</summary>
public sealed record FileMergeResult(string File, bool Changed, List<MergeConflict> Conflicts, string Summary)
{
    public bool Clean => Conflicts.Count == 0;
}

/// <summary>
/// Unresolved conflicts of a merge, kept in a folder: conflicts.json plus a copy of each conflicted file's "theirs"
/// side (theirs\&lt;file&gt;), which resolving to theirs reads from. In a project repo the folder is
/// .git\atlas3k\conflicts, so nothing of it is committed.
/// </summary>
public sealed class ConflictSet(string dir)
{
    public sealed record Entry(int Index, string Root, MergeConflict Conflict, bool Resolved = false, string? Resolution = null);

    private static readonly JsonSerializerOptions Json = new()
    {
        WriteIndented = true,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    };

    public string Dir { get; } = dir;
    private string ListPath => Path.Combine(Dir, "conflicts.json");

    public List<Entry> Entries() =>
        File.Exists(ListPath) ? JsonSerializer.Deserialize<List<Entry>>(File.ReadAllText(ListPath), Json)! : [];

    public List<Entry> Open() => Entries().Where(e => !e.Resolved).ToList();

    public string TheirsCopy(string file) => Path.Combine(Dir, "theirs", file.Replace('/', Path.DirectorySeparatorChar));

    /// <summary>Records a file's conflicts (replacing earlier ones for that file) and keeps its theirs side.</summary>
    public void Add(string root, string file, IEnumerable<MergeConflict> conflicts, string? theirsPath)
    {
        var all = Entries().Where(e => !e.Conflict.File.Equals(file, StringComparison.OrdinalIgnoreCase)).ToList();
        var next = all.Count == 0 ? 1 : all.Max(e => e.Index) + 1;
        foreach (var c in conflicts) all.Add(new Entry(next++, root, c));
        if (theirsPath is not null && File.Exists(theirsPath))
        {
            var copy = TheirsCopy(file);
            Directory.CreateDirectory(Path.GetDirectoryName(copy)!);
            File.Copy(theirsPath, copy, overwrite: true);
        }
        Save(all);
    }

    public void Save(List<Entry> entries)
    {
        Directory.CreateDirectory(Dir);
        File.WriteAllText(ListPath, JsonSerializer.Serialize(entries, Json));
    }

    public void Clear()
    {
        if (Directory.Exists(Dir)) Directory.Delete(Dir, recursive: true);
    }
}
