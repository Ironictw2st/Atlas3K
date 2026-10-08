using Atlas3K.Core;
using Atlas3K.Core.Collab;
using Atlas3K.Core.Editing;
using Atlas3K.Formats.Maps;

namespace Atlas3K.Tests;

/// <summary>
/// Two people sharing a map through git: a bare remote, two kits, edits to one layer and one heightmap on both sides,
/// pulled through Atlas3K's merge driver (with LFS). Needs git, git-lfs and a built Atlas3K.Cli; skipped otherwise.
/// </summary>
public class CollabRepoTests
{
    private static string? CliExe()
    {
        var dir = AppContext.BaseDirectory;
        foreach (var config in new[] { "Debug", "Release" })
        {
            var exe = Path.GetFullPath(Path.Combine(dir, "..", "..", "..", "..", "Atlas3K.Cli", "bin", config, "net9.0", "Atlas3K.Cli.exe"));
            if (File.Exists(exe)) return exe;
        }
        return null;
    }

    private static string Entity(string id, string pos) =>
        $"    <entity id=\"{id}\">\n      <ECTransform position=\"{pos}\" rotation=\"0 0 0\" scale=\"1 1 1\" pivot=\"0 0 0\"/>\n    </entity>\n";

    private static string Layer(params string[] entities) =>
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<layer version=\"35\">\n  <entities>\n" + string.Concat(entities)
        + "  </entities>\n  <associations>\n    <Logical/>\n    <Transform/>\n  </associations>\n</layer>\n";

    private const string A = "1000000000000aa", B = "1000000000000bb";

    [Fact]
    public void TwoClones_EditTheSameFiles_PullMergesThem()
    {
        var cli = CliExe();
        if (cli is null || !GitService.Available("git") || !GitService.Available("git", "lfs", "version")) return;
        var root = Directory.CreateTempSubdirectory("a3k_repo_");
        try
        {
            ProjectPaths Kit(string name) => new()
            {
                AssemblyKitRoot = Path.Combine(root.FullName, name),
                OutputRoot = Path.Combine(root.FullName, name + "_out"),
                MapName = "m",
            };
            var bare = Path.Combine(root.FullName, "remote.git");
            new GitService(root.FullName).Git("init", "-q", "--bare", "-b", "main", bare);
            var remote = new Uri(bare).AbsoluteUri;

            var alicePaths = Kit("alice");
            Directory.CreateDirectory(alicePaths.AkTerrainDir);
            var layerFile = Path.Combine(alicePaths.AkTerrainDir, "m.l1.layer");
            var heightFile = Path.Combine(alicePaths.AkTerrainDir, "m.height.1.tif");
            File.WriteAllText(layerFile, Layer(Entity(A, "1 0 1"), Entity(B, "5 0 5")));
            TiffMap.WriteGray16(heightFile, new Raster<ushort>(256, 256));
            var alice = CollabRepo.Init(alicePaths, cli);
            Identity(alice, "alice");
            alice.Git.Git("remote", "add", "origin", remote);
            alice.Push();

            var bobPaths = Kit("bob");
            var bob = CollabRepo.Clone(bobPaths, remote, cli);
            Identity(bob, "bob");
            Assert.Equal(File.ReadAllBytes(heightFile), File.ReadAllBytes(Path.Combine(bob.Root, "m.height.1.tif")));

            // Alice moves A and raises one corner; Bob moves B and raises another.
            File.WriteAllText(layerFile, Layer(Entity(A, "2 0 1"), Entity(B, "5 0 5")));
            var h = TiffMap.ReadGray16(heightFile);
            h[10, 10] = 1000;
            TiffMap.SaveGray16Like(heightFile, h);
            Assert.Equal(1, alice.Diff().Count(d => d.Kind == "terry"));
            alice.Commit("alice: move A, hill");
            alice.Push();

            File.WriteAllText(Path.Combine(bob.Root, "m.l1.layer"), Layer(Entity(A, "1 0 1"), Entity(B, "5 0 9")));
            var hb = TiffMap.ReadGray16(Path.Combine(bob.Root, "m.height.1.tif"));
            hb[200, 200] = 2000;
            TiffMap.SaveGray16Like(Path.Combine(bob.Root, "m.height.1.tif"), hb);
            bob.Commit("bob: move B, hill");
            var pull = bob.Pull();
            Assert.True(pull.Ok, pull.Output);
            Assert.Equal(0, pull.Conflicts);
            Assert.Equal(Layer(Entity(A, "2 0 1"), Entity(B, "5 0 9")), File.ReadAllText(Path.Combine(bob.Root, "m.l1.layer")));
            var merged = TiffMap.ReadGray16(Path.Combine(bob.Root, "m.height.1.tif"));
            Assert.Equal(1000, merged[10, 10]);
            Assert.Equal(2000, merged[200, 200]);
            Assert.Empty(bob.GetStatus().Changes);
            Assert.True(GitService.IsLfsPointer(bob.Git.RunBytes("git", ["show", "HEAD:m.height.1.tif"]).StdOut)); // stored in LFS
            bob.Push();

            // Both now move A: a conflict, kept ours until resolved to theirs.
            alice.Pull();
            File.WriteAllText(layerFile, Layer(Entity(A, "3 0 3"), Entity(B, "5 0 9")));
            alice.Commit("alice: A again");
            alice.Push();
            File.WriteAllText(Path.Combine(bob.Root, "m.l1.layer"), Layer(Entity(A, "4 0 4"), Entity(B, "5 0 9")));
            bob.Commit("bob: A too");
            var clash = bob.Pull();
            Assert.False(clash.Ok);
            Assert.Equal(1, clash.Conflicts);
            Assert.Throws<InvalidOperationException>(() => bob.Commit(null));
            ConflictResolver.Resolve(bob.Conflicts, "theirs");
            bob.Commit(null);
            Assert.Equal(Layer(Entity(A, "3 0 3"), Entity(B, "5 0 9")), File.ReadAllText(Path.Combine(bob.Root, "m.l1.layer")));

            // Locks: Bob locks the layer; Alice's editors refuse to save it.
            bob.Push();
            var bobLocks = new LockService(bob);
            var held = bobLocks.Acquire("file", "m.l1.layer", "l1", "rework");
            alice.Pull();
            new LockService(alice).Refresh();
            var journal = new FileJournal(Path.Combine(root.FullName, "alice_out", "j"));
            var ex = Assert.Throws<InvalidOperationException>(() => journal.Commit([(layerFile, p => File.WriteAllText(p, "x"))], "edit"));
            Assert.Contains("bob", ex.Message);
            bobLocks.Release([held.Id]);
            new LockService(alice).Refresh();
            journal.Commit([(layerFile, p => File.WriteAllText(p, Layer(Entity(A, "3 0 3"))))], "edit");
        }
        finally
        {
            foreach (var f in Directory.EnumerateFiles(root.FullName, "*", SearchOption.AllDirectories)) File.SetAttributes(f, FileAttributes.Normal);
            root.Delete(true);
        }
    }

    private static void Identity(CollabRepo repo, string who)
    {
        repo.Git.Git("config", "user.name", who);
        repo.Git.Git("config", "user.email", $"{who}@example.com");
        File.WriteAllText(Path.Combine(repo.StateDir, "user"), who);
    }
}
