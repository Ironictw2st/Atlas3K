using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace Atlas3K.Core.Collab;

/// <summary>
/// "I'm working on this" locks shared through the project repository: locks.json on the atlas3k/locks branch,
/// updated by pushing a new commit on top of the one read (a rejected push means someone else changed the locks
/// meanwhile, so it re-reads and retries). Works with any git remote.
///   file   a map file (layer, raster, tile_map.png): editors refuse to save it for anyone but the owner
///   layer  a Terry file layer by name; stored as its .layer file, enforced like a file lock
///   region a world rect [x0, z0, x1, z1]: advisory, shown on the map and in status
/// A local copy (.git\atlas3k\locks.json) is refreshed by every lock command, pull and status, and is what
/// <see cref="LockGuard"/> checks, so saving never waits on the network.
/// </summary>
public sealed class LockService(CollabRepo repo)
{
    public sealed record Lock(string Id, string Owner, string Kind, string Target, string? Label, string? Reason, DateTime Created,
                              double[]? Rect = null);

    private const string Branch = "atlas3k/locks";
    private const string FileName = "locks.json";

    internal static readonly JsonSerializerOptions Json = new()
    {
        WriteIndented = true,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    };

    private GitService Git => repo.Git;
    public string CachePath => Path.Combine(repo.StateDir, FileName);
    private string Ref => repo.HasRemote ? $"refs/remotes/origin/{Branch}" : $"refs/heads/{Branch}";

    /// <summary>Fetches the shared locks (when there is a remote) and refreshes the local copy.</summary>
    public List<Lock> Refresh()
    {
        if (repo.HasRemote) Git.TryGit("fetch", "-q", "origin", $"+refs/heads/{Branch}:{Ref}");
        var locks = ReadRef().Locks;
        Directory.CreateDirectory(repo.StateDir);
        File.WriteAllText(CachePath, JsonSerializer.Serialize(locks, Json));
        File.WriteAllText(Path.Combine(repo.StateDir, "user"), repo.Identity());
        return locks;
    }

    public List<Lock> Cached() =>
        File.Exists(CachePath) ? JsonSerializer.Deserialize<List<Lock>>(File.ReadAllText(CachePath), Json) ?? [] : [];

    private (List<Lock> Locks, string? Commit) ReadRef()
    {
        var head = Git.TryGit("rev-parse", "--verify", "-q", Ref);
        if (!head.Ok) return ([], null);
        var text = Git.TryGit("show", $"{head.Text}:{FileName}");
        return (text.Ok ? JsonSerializer.Deserialize<List<Lock>>(text.StdOut, Json) ?? [] : [], head.Text);
    }

    /// <summary>Takes a lock. Throws when it overlaps someone else's lock on the same target.</summary>
    public Lock Acquire(string kind, string target, string? label = null, string? reason = null, double[]? rect = null)
    {
        if (kind is not ("file" or "layer" or "region")) throw new ArgumentException("kind must be file, layer or region");
        var me = repo.Identity();
        Lock? made = null;
        Update(locks =>
        {
            var clash = locks.FirstOrDefault(l => l.Owner != me && Overlaps(l, kind, target, rect));
            if (clash is not null)
                throw new InvalidOperationException($"{clash.Label ?? clash.Target} is locked by {clash.Owner} since {clash.Created:g}{(clash.Reason is null ? "" : $" ({clash.Reason})")}");
            made = locks.FirstOrDefault(l => l.Owner == me && l.Kind == kind && l.Target == target)
                   ?? new Lock(Guid.NewGuid().ToString("N")[..8], me, kind, target, label, reason, DateTime.Now, rect);
            if (!locks.Contains(made)) locks.Add(made);
            return $"lock {kind} {label ?? target} ({me})";
        });
        return made!;
    }

    /// <summary>Releases locks by id (all of mine when null). Someone else's lock needs <paramref name="force"/>.</summary>
    public List<Lock> Release(IReadOnlyCollection<string>? ids, bool force = false)
    {
        var me = repo.Identity();
        var released = new List<Lock>();
        Update(locks =>
        {
            released.Clear();
            foreach (var l in locks.ToList())
            {
                if (ids is null ? l.Owner != me : !ids.Contains(l.Id)) continue;
                if (l.Owner != me && !force) throw new InvalidOperationException($"lock {l.Id} belongs to {l.Owner}; pass force to break it");
                locks.Remove(l);
                released.Add(l);
            }
            return $"unlock {string.Join(", ", released.Select(l => l.Label ?? l.Target))} ({me})";
        });
        return released;
    }

    private static bool Overlaps(Lock l, string kind, string target, double[]? rect)
    {
        if (l.Kind == "region" || kind == "region")
            return l.Kind == "region" && kind == "region" && l.Rect is { } a && rect is { } b
                   && a[0] < b[2] && b[0] < a[2] && a[1] < b[3] && b[1] < a[3];
        return l.Target.Equals(target, StringComparison.OrdinalIgnoreCase);
    }

    /// <summary>Read, change and publish locks.json; retries when someone else published in between.</summary>
    private void Update(Func<List<Lock>, string> change)
    {
        for (var attempt = 0; attempt < 5; attempt++)
        {
            if (repo.HasRemote) Git.TryGit("fetch", "-q", "origin", $"+refs/heads/{Branch}:{Ref}");
            var (locks, parent) = ReadRef();
            var message = change(locks);
            var blob = Git.Run("git", ["hash-object", "-w", "--stdin"], true,
                Encoding.UTF8.GetBytes(JsonSerializer.Serialize(locks, Json) + "\n")).Text;
            var tree = Git.Run("git", ["mktree"], true, Encoding.UTF8.GetBytes($"100644 blob {blob}\t{FileName}\n")).Text;
            var args = new List<string> { "commit-tree", tree, "-m", message };
            if (parent is not null) args.AddRange(["-p", parent]);
            var commit = Git.Git([.. args]).Text;
            if (!repo.HasRemote)
            {
                Git.Git("update-ref", Ref, commit);
                Refresh();
                return;
            }
            if (Git.TryGit("push", "-q", "origin", $"{commit}:refs/heads/{Branch}").Ok)
            {
                Git.Git("update-ref", Ref, commit);
                Refresh();
                return;
            }
        }
        throw new InvalidOperationException("could not publish the lock change (the locks branch kept changing); try again");
    }
}

/// <summary>
/// Stops editors from saving files someone else holds a file or layer lock on. Called by <see cref="Editing.FileJournal"/>
/// before every batch; reads only the local lock cache of the repository the files are in.
/// </summary>
public static class LockGuard
{
    public static void Check(IEnumerable<string> files)
    {
        foreach (var group in files.GroupBy(f => Path.GetDirectoryName(Path.GetFullPath(f)) ?? "", StringComparer.OrdinalIgnoreCase))
        {
            var root = RepoOf(group.Key);
            if (root is null) continue;
            var state = Path.Combine(root, ".git", "atlas3k");
            var cache = Path.Combine(state, "locks.json");
            if (!File.Exists(cache)) continue;
            var me = File.Exists(Path.Combine(state, "user")) ? File.ReadAllText(Path.Combine(state, "user")).Trim() : "";
            List<LockService.Lock> locks;
            try { locks = JsonSerializer.Deserialize<List<LockService.Lock>>(File.ReadAllText(cache), LockService.Json) ?? []; }
            catch (JsonException) { continue; }
            foreach (var f in group)
            {
                var rel = Path.GetRelativePath(root, Path.GetFullPath(f)).Replace('\\', '/');
                if (locks.FirstOrDefault(l => l.Kind is "file" or "layer" && l.Owner != me
                                              && l.Target.Equals(rel, StringComparison.OrdinalIgnoreCase)) is { } l)
                    throw new InvalidOperationException(
                        $"{l.Label ?? rel} is locked by {l.Owner}{(l.Reason is null ? "" : $" ({l.Reason})")}; ask them to release it (lock {l.Id})");
            }
        }
    }

    /// <summary>Regions of others' locks a world point falls in (advisory).</summary>
    public static List<LockService.Lock> RegionLocksAt(string mapDir, double x, double z)
    {
        var cache = Path.Combine(mapDir, ".git", "atlas3k", "locks.json");
        if (!File.Exists(cache)) return [];
        var me = File.ReadAllText(Path.Combine(mapDir, ".git", "atlas3k", "user")).Trim();
        return (JsonSerializer.Deserialize<List<LockService.Lock>>(File.ReadAllText(cache), LockService.Json) ?? [])
            .Where(l => l.Kind == "region" && l.Owner != me && l.Rect is { } r && x >= r[0] && x <= r[2] && z >= r[1] && z <= r[3]).ToList();
    }

    private static string? RepoOf(string dir)
    {
        for (var d = dir; d is not null; d = Path.GetDirectoryName(d))
            if (Directory.Exists(Path.Combine(d, ".git"))) return File.Exists(Path.Combine(d, CollabRepo.ProjectFile)) ? d : null;
        return null;
    }
}
