using System.IO.Compression;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using Atlas3K.Core.Editing;

namespace Atlas3K.Core.Collab;

/// <summary>
/// A change package (.a3kpatch): one person's map edits as a zip someone else can import. It holds, per changed file
/// (paths relative to the assembly kit root, e.g. raw_data/terrain/campaigns/&lt;map&gt;/x.layer), the base the edits
/// started from and the result: whole files for Terry XML and small or new rasters, and only the changed 64-pixel
/// cells for large rasters (an 80 MB heightmap edit ships as a few KB).
///
/// Import applies a file directly when it is still at the package's base, and otherwise three-way merges it
/// (<see cref="MapMerge"/>) with the package's base, so edits made meanwhile are kept; conflicts keep the local side
/// and are recorded for resolving. Everything the import writes is one batch of a <see cref="FileJournal"/>, so it can
/// be undone.
/// </summary>
public static class PatchPackage
{
    public const string Extension = ".a3kpatch";
    private const int Format = 1;

    public sealed record PatchFile(string Path, string Change, string? BaseHash, string? AfterHash, string Storage, string Summary);

    public sealed record Manifest(int Format, string Map, string Label, string? Description, string Author, DateTime Created,
                                  List<PatchFile> Files);

    private static readonly JsonSerializerOptions Json = new()
    {
        WriteIndented = true,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    };

    /// <summary>One file of a package source: where its base and result are now (null = absent).</summary>
    public sealed record Source(string RelPath, string? BasePath, string? AfterPath);

    // ---------------------------------------------------------------- export

    public static Manifest Export(IEnumerable<Source> files, string outPath, string map, string label, string? description = null,
                                  string? author = null)
    {
        var list = new List<PatchFile>();
        var temp = outPath + ".tmp";
        using (var zip = ZipFile.Open(temp, ZipArchiveMode.Create))
        {
            foreach (var f in files.OrderBy(f => f.RelPath, StringComparer.OrdinalIgnoreCase))
            {
                if (MapMerge.IsPrivate(f.RelPath)) continue;
                var rel = f.RelPath.Replace('\\', '/');
                var baseHash = Hash(f.BasePath);
                var afterHash = Hash(f.AfterPath);
                if (baseHash == afterHash) continue;
                var change = baseHash is null ? "added" : afterHash is null ? "deleted" : "modified";
                var storage = "full";
                var summary = change;
                if (change == "modified" && MapMerge.TypeOf(rel) == MapMerge.FileType.Raster && TryCells(f, out var cells, out var rsum))
                {
                    storage = "cells";
                    summary = rsum;
                    Write(zip, $"files/{rel}.cells", cells);
                }
                else
                {
                    // A deletion only needs the base hash (import deletes when the file still matches it).
                    if (change == "modified" && File.Exists(f.BasePath)) Write(zip, $"files/{rel}.base", File.ReadAllBytes(f.BasePath!));
                    if (f.AfterPath is not null && File.Exists(f.AfterPath)) Write(zip, $"files/{rel}.after", File.ReadAllBytes(f.AfterPath));
                    if (change == "modified" && MapMerge.TypeOf(rel) == MapMerge.FileType.TerryXml)
                        summary = Summarise(TerryXmlMerge.Diff(File.ReadAllText(f.BasePath!), File.ReadAllText(f.AfterPath!)));
                }
                list.Add(new PatchFile(rel, change, baseHash, afterHash, storage, summary));
            }
            var manifest = new Manifest(Format, map, label, description, author ?? Environment.UserName, DateTime.Now, list);
            Write(zip, "manifest.json", JsonSerializer.SerializeToUtf8Bytes(manifest, Json));
        }
        File.Move(temp, outPath, overwrite: true);
        return ReadManifest(outPath);
    }

    public static string Summarise(List<TerryXmlMerge.EntityChange> changes) =>
        changes.Count == 0 ? "no entity changes"
            : string.Join(", ", changes.GroupBy(c => c.Change).Select(g => $"{g.Count()} {g.Key}"));

    private static void Write(ZipArchive zip, string name, byte[] bytes)
    {
        using var s = zip.CreateEntry(name, CompressionLevel.SmallestSize).Open();
        s.Write(bytes);
    }

    private static string? Hash(string? path) => path is not null && File.Exists(path) ? FileJournal.Hash(File.ReadAllBytes(path)) : null;

    /// <summary>Changed cells of a same-sized raster, when they are under half of it: header (magic, w, h, bpp, count),
    /// then per cell x, y, w, h, base pixels, result pixels.</summary>
    private static bool TryCells(Source f, out byte[] bytes, out string summary)
    {
        bytes = [];
        summary = "";
        RasterImage b, a;
        try
        {
            b = RasterImage.Load(f.BasePath!);
            a = RasterImage.Load(f.AfterPath!);
        }
        catch (Exception e) when (e is InvalidDataException or IOException) { return false; }
        if (b.Width != a.Width || b.Height != a.Height || b.BytesPerPixel != a.BytesPerPixel) return false;
        var diff = RasterMerge.Diff(b, a);
        var total = (b.Width + RasterMerge.Cell - 1) / RasterMerge.Cell * ((b.Height + RasterMerge.Cell - 1) / RasterMerge.Cell);
        if (diff.Cells.Count * 2 > total) return false;
        using var ms = new MemoryStream();
        using (var w = new BinaryWriter(ms))
        {
            w.Write("A3KC"u8);
            w.Write(b.Width);
            w.Write(b.Height);
            w.Write(b.BytesPerPixel);
            w.Write(diff.Cells.Count);
            foreach (var c in diff.Cells)
            {
                int[] rect = [c[0] * RasterMerge.Cell, c[1] * RasterMerge.Cell, 0, 0];
                rect[2] = Math.Min(RasterMerge.Cell, b.Width - rect[0]);
                rect[3] = Math.Min(RasterMerge.Cell, b.Height - rect[1]);
                foreach (var v in rect) w.Write(v);
                w.Write(Block(b, rect));
                w.Write(Block(a, rect));
            }
        }
        bytes = ms.ToArray();
        summary = $"{diff.Pixels} pixel(s) in {diff.Cells.Count} cell(s), bounds [{string.Join(", ", diff.Bounds!)}]";
        return true;
    }

    private static byte[] Block(RasterImage r, int[] rect)
    {
        var bpp = r.BytesPerPixel;
        var block = new byte[rect[2] * rect[3] * bpp];
        for (var y = 0; y < rect[3]; y++)
            Buffer.BlockCopy(r.Data, ((rect[1] + y) * r.Width + rect[0]) * bpp, block, y * rect[2] * bpp, rect[2] * bpp);
        return block;
    }

    private static void Unblock(byte[] data, int width, int bpp, int[] rect, byte[] block)
    {
        for (var y = 0; y < rect[3]; y++)
            Buffer.BlockCopy(block, y * rect[2] * bpp, data, ((rect[1] + y) * width + rect[0]) * bpp, rect[2] * bpp);
    }

    // ---------------------------------------------------------------- read

    public static Manifest ReadManifest(string path)
    {
        using var zip = ZipFile.OpenRead(path);
        return ReadManifest(zip);
    }

    private static Manifest ReadManifest(ZipArchive zip)
    {
        var entry = zip.GetEntry("manifest.json") ?? throw new InvalidDataException("not an Atlas3K change package (no manifest.json)");
        using var s = entry.Open();
        var m = JsonSerializer.Deserialize<Manifest>(s, Json) ?? throw new InvalidDataException("empty manifest");
        if (m.Format > Format) throw new InvalidDataException($"package format {m.Format} is newer than this Atlas3K ({Format}); update Atlas3K");
        return m;
    }

    private static byte[]? Read(ZipArchive zip, string name)
    {
        if (zip.GetEntry(name) is not { } e) return null;
        using var s = e.Open();
        using var ms = new MemoryStream();
        s.CopyTo(ms);
        return ms.ToArray();
    }

    // ---------------------------------------------------------------- import

    public sealed record FileOutcome(string Path, string Action, FileMergeResult? Merge = null);

    public sealed record ImportResult(Manifest Manifest, List<FileOutcome> Files, int Seq, bool DryRun)
    {
        public int Conflicts => Files.Sum(f => f.Merge?.Conflicts.Count ?? 0) + Files.Count(f => f.Action == "conflict");
    }

    /// <summary>
    /// Applies a package under <paramref name="root"/> (the assembly kit root). Files are staged first; nothing is
    /// written on a dry run. Conflicts are recorded in <paramref name="conflicts"/> (cleared first).
    /// </summary>
    public static ImportResult Import(string patchPath, string root, FileJournal journal, ConflictSet conflicts, bool dryRun = false)
    {
        using var zip = ZipFile.OpenRead(patchPath);
        var manifest = ReadManifest(zip);
        var stage = Directory.CreateTempSubdirectory("a3k_import_").FullName;
        var outcomes = new List<FileOutcome>();
        var writes = new List<(string Path, string? Staged)>();
        var theirsCopies = new Dictionary<string, string>();
        try
        {
            var n = 0;
            foreach (var f in manifest.Files)
            {
                n++;
                var target = Path.Combine(root, f.Path.Replace('/', Path.DirectorySeparatorChar));
                var current = Hash(target);
                if (current == f.AfterHash) { outcomes.Add(new FileOutcome(f.Path, "already applied")); continue; }

                string Stage(string suffix, byte[]? bytes)
                {
                    var p = Path.Combine(stage, $"{n}{suffix}{Path.GetExtension(f.Path)}");
                    if (bytes is not null) File.WriteAllBytes(p, bytes);
                    return p;
                }

                if (f.Change == "deleted")
                {
                    if (current is null) outcomes.Add(new FileOutcome(f.Path, "already applied"));
                    else if (current == f.BaseHash) { writes.Add((target, null)); outcomes.Add(new FileOutcome(f.Path, "deleted")); }
                    else outcomes.Add(new FileOutcome(f.Path, "conflict", new FileMergeResult(f.Path, false,
                        [new MergeConflict(f.Path, "entity", f.Path, "the package deletes this file but it was changed here; kept it")], "conflict")));
                    continue;
                }

                // Base and result of the package, as files.
                string? basePath, afterPath;
                if (f.Storage == "cells")
                {
                    if (current is null)
                    {
                        outcomes.Add(new FileOutcome(f.Path, "conflict", new FileMergeResult(f.Path, false,
                            [new MergeConflict(f.Path, "binary", f.Path, "the package edits this raster but it does not exist here")], "conflict")));
                        continue;
                    }
                    (basePath, afterPath) = StageCells(Read(zip, $"files/{f.Path}.cells")!, target, Stage);
                    if (basePath is null)
                    {
                        outcomes.Add(new FileOutcome(f.Path, "conflict", new FileMergeResult(f.Path, false,
                            [new MergeConflict(f.Path, "size", f.Path, "the package was made on a raster of another size")], "conflict")));
                        continue;
                    }
                }
                else
                {
                    var bb = Read(zip, $"files/{f.Path}.base");
                    basePath = bb is null ? null : Stage(".base", bb);
                    afterPath = Stage(".after", Read(zip, $"files/{f.Path}.after") ?? throw new InvalidDataException($"package lacks {f.Path}"));
                }

                if (current is null || current == f.BaseHash)
                {
                    writes.Add((target, afterPath));
                    outcomes.Add(new FileOutcome(f.Path, current is null ? "added" : "applied"));
                    continue;
                }
                var merged = Stage(".merged", File.ReadAllBytes(target));
                var r = MapMerge.Merge(basePath, merged, afterPath!, merged, f.Path);
                if (r.Changed) writes.Add((target, merged));
                if (!r.Clean) theirsCopies[f.Path] = afterPath!;
                outcomes.Add(new FileOutcome(f.Path, !r.Clean ? "merged with conflicts" : r.Changed ? "merged" : "already applied", r));
            }

            var seq = 0;
            if (!dryRun)
            {
                conflicts.Clear();
                foreach (var o in outcomes.Where(o => o.Merge is { Clean: false }))
                    conflicts.Add(root, o.Path, o.Merge!.Conflicts, theirsCopies.GetValueOrDefault(o.Path));
                if (writes.Count > 0)
                    seq = journal.Commit(writes.Select(w => (w.Path, (Action<string>)(p =>
                    {
                        if (w.Staged is null) File.Delete(p);
                        else
                        {
                            Directory.CreateDirectory(Path.GetDirectoryName(p)!);
                            File.Copy(w.Staged, p, overwrite: true);
                        }
                    }))), $"import {Path.GetFileName(patchPath)}: {manifest.Label}");
            }
            return new ImportResult(manifest, outcomes, seq, dryRun);
        }
        finally
        {
            try { Directory.Delete(stage, recursive: true); } catch (IOException) { }
        }
    }

    /// <summary>Rebuilds the package's base and result of a cell-stored raster on top of the local file (outside the
    /// cells both equal the local file). Null when the sizes differ.</summary>
    private static (string?, string?) StageCells(byte[] cells, string target, Func<string, byte[]?, string> stage)
    {
        var local = RasterImage.Load(target);
        using var r = new BinaryReader(new MemoryStream(cells));
        if (Encoding.ASCII.GetString(r.ReadBytes(4)) != "A3KC") throw new InvalidDataException("bad cells block");
        int w = r.ReadInt32(), h = r.ReadInt32(), bpp = r.ReadInt32(), count = r.ReadInt32();
        if (w != local.Width || h != local.Height || bpp != local.BytesPerPixel) return (null, null);
        var b = (byte[])local.Data.Clone();
        var a = (byte[])local.Data.Clone();
        for (var i = 0; i < count; i++)
        {
            int[] rect = [r.ReadInt32(), r.ReadInt32(), r.ReadInt32(), r.ReadInt32()];
            var size = rect[2] * rect[3] * bpp;
            Unblock(b, w, bpp, rect, r.ReadBytes(size));
            Unblock(a, w, bpp, rect, r.ReadBytes(size));
        }
        var basePath = stage(".base", File.ReadAllBytes(target));
        var afterPath = stage(".after", File.ReadAllBytes(target));
        local.WithData(b).Save(basePath);
        local.WithData(a).Save(afterPath);
        return (basePath, afterPath);
    }
}
