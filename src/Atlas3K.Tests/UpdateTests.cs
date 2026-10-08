using System.IO.Compression;
using System.Net;
using System.Security.Cryptography;
using System.Text.Json.Nodes;
using Atlas3K.Core.Updates;

namespace Atlas3K.Tests;

public class UpdateTests
{
    [Theory]
    [InlineData("0.1.0-alpha.2", "0.1.0-alpha.10")]
    [InlineData("0.1.0-alpha.10", "0.1.0-beta.1")]
    [InlineData("0.1.0-beta.1", "0.1.0-rc.1")]
    [InlineData("0.1.0-rc.1", "0.1.0")]
    [InlineData("0.1.0", "0.1.1-alpha.1")]
    [InlineData("v0.1.9", "0.2.0")]
    [InlineData("0.1.0-alpha", "0.1.0-alpha.1")]
    public void Versions_OrderLikeSemVer(string older, string newer)
    {
        Assert.True(SemVersion.Parse(older) < SemVersion.Parse(newer));
        Assert.True(SemVersion.Parse(newer) > SemVersion.Parse(older));
    }

    [Fact]
    public void Versions_IgnoreBuildMetadata() =>
        Assert.Equal(0, SemVersion.Parse("0.1.0-alpha.2+abc123").CompareTo(SemVersion.Parse("v0.1.0-alpha.2")));

    private static JsonObject Release(string tag, bool pre, string? sha = "AB", bool draft = false, bool asset = true) => new()
    {
        ["tag_name"] = tag, ["name"] = "Atlas3K " + tag, ["prerelease"] = pre, ["draft"] = draft,
        ["published_at"] = "2026-10-06T03:46:30Z", ["html_url"] = $"https://github.com/x/releases/{tag}",
        ["body"] = sha is null ? "notes" : $"notes\n\nSHA-256 of the zip: `{sha.PadRight(64, '0')}`",
        ["assets"] = asset
            ? new JsonArray(new JsonObject { ["name"] = $"Atlas3K-{tag[1..]}.zip", ["browser_download_url"] = $"https://dl/{tag}.zip", ["size"] = 10 })
            : new JsonArray(),
    };

    [Fact]
    public void Channels_PickTheNewestEligibleRelease()
    {
        var json = new JsonArray(Release("v0.3.0-beta.1", true), Release("v0.2.0", false), Release("v0.2.1-alpha.1", true),
            Release("v0.4.0", false, draft: true), Release("v0.5.0", false, asset: false), Release("v0.1.0", false)).ToJsonString();
        var releases = UpdateService.ParseReleases(json);
        Assert.Equal(["0.3.0-beta.1", "0.2.1-alpha.1", "0.2.0", "0.1.0"], releases.Select(r => r.Version.ToString()));
        Assert.Equal("AB".PadRight(64, '0'), releases[0].Sha256);

        var current = SemVersion.Parse("0.1.0-alpha.2");
        Assert.Equal("0.2.0", UpdateService.Pick(releases, UpdateChannel.Stable, current)!.Version.ToString());
        Assert.Equal("0.3.0-beta.1", UpdateService.Pick(releases, UpdateChannel.Unstable, current)!.Version.ToString());
        Assert.Null(UpdateService.Pick(releases, UpdateChannel.Stable, SemVersion.Parse("0.2.0")));
    }

    [Fact]
    public void Channel_FollowsSettingsThenInstallThenVersion()
    {
        var pre = SemVersion.Parse("0.1.0-alpha.2");
        Assert.Equal(UpdateChannel.Unstable, UpdateService.ChannelFor(new Core.AppSettings(), pre));
        Assert.Equal(UpdateChannel.Stable, UpdateService.ChannelFor(new Core.AppSettings(), SemVersion.Parse("0.2.0")));
        Assert.Equal(UpdateChannel.Stable, UpdateService.ChannelFor(new Core.AppSettings(), pre, new UpdateService.InstallInfo("", "stable", "")));
        Assert.Equal(UpdateChannel.Unstable, UpdateService.ChannelFor(new Core.AppSettings { UpdateChannel = "unstable" }, pre,
            new UpdateService.InstallInfo("", "stable", "")));
    }

    private sealed class FakeHttp(Dictionary<string, byte[]> files) : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken ct) =>
            Task.FromResult(files.TryGetValue(request.RequestUri!.ToString(), out var body)
                ? new HttpResponseMessage(HttpStatusCode.OK) { Content = new ByteArrayContent(body) }
                : new HttpResponseMessage(HttpStatusCode.NotFound));
    }

    private static byte[] Zip(params (string Name, string Text)[] files)
    {
        using var ms = new MemoryStream();
        using (var zip = new ZipArchive(ms, ZipArchiveMode.Create, leaveOpen: true))
            foreach (var (name, text) in files)
            {
                using var w = new StreamWriter(zip.CreateEntry(name).Open());
                w.Write(text);
            }
        return ms.ToArray();
    }

    [Fact]
    public async Task Download_VerifiesTheChecksum_AndUnpacks()
    {
        var dir = Directory.CreateTempSubdirectory("a3k_upd_");
        Environment.SetEnvironmentVariable("ATLAS3K_UPDATES_DIR", dir.FullName); // only read once; the service's dir may be elsewhere
        try
        {
            var zip = Zip(("Atlas3K.exe", "new exe"), ("lib.dll", "new lib"));
            var sha = Convert.ToHexString(SHA256.HashData(zip));
            var release = new ReleaseInfo(SemVersion.Parse("9.9.9"), "v9.9.9", "t", false, DateTime.Now, "", "", "Atlas3K-9.9.9.zip",
                "https://dl/x.zip", zip.Length, sha);
            var service = new UpdateService(new HttpClient(new FakeHttp(new() { ["https://dl/x.zip"] = zip })));
            var staged = await service.DownloadAsync(release);
            Assert.Equal("new exe", File.ReadAllText(Path.Combine(staged, "Atlas3K.exe")));

            var bad = release with { Sha256 = new string('0', 64) };
            await Assert.ThrowsAsync<InvalidDataException>(() => service.DownloadAsync(bad));
            await Assert.ThrowsAsync<InvalidDataException>(() => service.DownloadAsync(release with { Sha256 = null }));
            Directory.Delete(Path.Combine(UpdateService.UpdatesDir, "9.9.9"), recursive: true);
        }
        finally { dir.Delete(true); }
    }

    [Fact]
    public void ApplyScript_BacksUpInstalls_AndRollsBack()
    {
        if (!OperatingSystem.IsWindows()) return;
        var root = Directory.CreateTempSubdirectory("a3k_apply_");
        try
        {
            string P(params string[] parts) => Path.Combine([root.FullName, .. parts]);
            Directory.CreateDirectory(P("install"));
            Directory.CreateDirectory(P("new", "sub"));
            File.WriteAllText(P("install", "Atlas3K.exe"), "old exe");
            File.WriteAllText(P("install", "old_only.dll"), "old");
            File.WriteAllText(P("new", "Atlas3K.exe"), "new exe");
            File.WriteAllText(P("new", "sub", "x.dll"), "new");
            var script = P("apply.ps1");
            File.WriteAllText(script, UpdateService.ApplyScript);
            void Apply(string source)
            {
                var psi = new System.Diagnostics.ProcessStartInfo(UpdateService.PowerShellExe) { UseShellExecute = false, CreateNoWindow = true };
                foreach (var a in new[] { "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script, "-Source", source, "-Target", P("install"),
                             "-Backup", P("backup"), "-WaitPid", "0", "-Log", P("update.log") })
                    psi.ArgumentList.Add(a);
                using var p = System.Diagnostics.Process.Start(psi)!;
                Assert.True(p.WaitForExit(120_000));
            }
            Apply(P("new"));
            var log = File.ReadAllText(P("update.log"));
            Assert.Contains("installed", log);
            Assert.Equal("new exe", File.ReadAllText(P("install", "Atlas3K.exe")));
            Assert.Equal("new", File.ReadAllText(P("install", "sub", "x.dll")));
            Assert.Equal("old exe", File.ReadAllText(P("backup", "Atlas3K.exe")));

            // rolling back = installing the backup (from a copy, since the helper rewrites the backup)
            Directory.CreateDirectory(P("rollback"));
            foreach (var f in Directory.GetFiles(P("backup"))) File.Copy(f, P("rollback", Path.GetFileName(f)));
            Apply(P("rollback"));
            Assert.Equal("old exe", File.ReadAllText(P("install", "Atlas3K.exe")));
            Assert.Equal("new exe", File.ReadAllText(P("backup", "Atlas3K.exe")));
        }
        finally { root.Delete(true); }
    }
}
