using System.Diagnostics;
using System.IO.Compression;
using System.Net.Http.Headers;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace Atlas3K.Core.Updates;

/// <summary>Which releases an install follows: Stable = full releases only; Unstable = pre-releases too (alpha, beta,
/// release candidates), whichever is newest.</summary>
public enum UpdateChannel { Stable, Unstable }

/// <summary>A downloadable Atlas3K release.</summary>
public sealed record ReleaseInfo(SemVersion Version, string Tag, string Name, bool Prerelease, DateTime Published, string Notes,
                                 string PageUrl, string AssetName, string AssetUrl, long AssetSize, string? Sha256)
{
    /// <summary>A "&lt;zip&gt;.sha256" asset, preferred over the checksum in the notes.</summary>
    public string? ShaAssetUrl { get; init; }
}

/// <summary>
/// Updates from the GitHub releases of <see cref="DefaultRepository"/>. Release zips (tools/publish.ps1) carry
/// <see cref="InstallMarker"/>; only an install with that marker updates itself (a source build never does). The
/// zip is verified against its SHA-256 (a "&lt;zip&gt;.sha256" asset, or "SHA-256 … `hex`" in the release notes),
/// unpacked to %LocalAppData%\Atlas3K\updates\&lt;version&gt;, and swapped in by a helper script once Atlas3K has
/// closed: it backs the install up first (for rolling back) and restores it if the copy fails.
/// </summary>
public sealed partial class UpdateService(HttpClient? http = null, string repository = UpdateService.DefaultRepository)
{
    public const string DefaultRepository = "Ironictw2st/Atlas3K";
    public const string InstallMarker = "atlas3k-install.json";

    private readonly HttpClient _http = http ?? CreateClient();

    public string Repository { get; } = repository;

    /// <summary>%LocalAppData%\Atlas3K\updates (or ATLAS3K_UPDATES_DIR): downloads, staged versions, the backup and logs.</summary>
    public static string UpdatesDir { get; } = Environment.GetEnvironmentVariable("ATLAS3K_UPDATES_DIR") is { Length: > 0 } d
        ? Path.GetFullPath(d)
        : Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Atlas3K", "updates");

    public static string BackupDir => Path.Combine(UpdatesDir, "previous");
    public static string LogPath => Path.Combine(UpdatesDir, "update.log");

    private static HttpClient CreateClient()
    {
        var c = new HttpClient { Timeout = TimeSpan.FromMinutes(10) };
        c.DefaultRequestHeaders.UserAgent.Add(new ProductInfoHeaderValue("Atlas3K-Updater", "1.0"));
        c.DefaultRequestHeaders.Accept.Add(new MediaTypeWithQualityHeaderValue("application/vnd.github+json"));
        return c;
    }

    // ---------------------------------------------------------------- install & settings

    /// <summary>The release marker of an install folder (null for source builds).</summary>
    public sealed record InstallInfo(string Version, string Channel, string Folder);

    public static InstallInfo? Install(string? folder = null)
    {
        folder ??= AppContext.BaseDirectory;
        var marker = Path.Combine(folder, InstallMarker);
        if (!File.Exists(marker)) return null;
        try
        {
            var n = JsonNode.Parse(File.ReadAllText(marker));
            return new InstallInfo(n?["version"]?.GetValue<string>() ?? "", n?["channel"]?.GetValue<string>() ?? "", Path.GetFullPath(folder));
        }
        catch (JsonException) { return null; }
    }

    /// <summary>The channel the user picked (settings "updateChannel"); otherwise the one the install was published
    /// on; otherwise unstable for a pre-release version.</summary>
    public static UpdateChannel ChannelFor(AppSettings settings, SemVersion current, InstallInfo? install = null)
    {
        var picked = settings.UpdateChannel;
        if (string.IsNullOrEmpty(picked)) picked = install?.Channel ?? "";
        return picked.Equals("stable", StringComparison.OrdinalIgnoreCase) ? UpdateChannel.Stable
            : picked.Equals("unstable", StringComparison.OrdinalIgnoreCase) ? UpdateChannel.Unstable
            : current.IsPrerelease ? UpdateChannel.Unstable : UpdateChannel.Stable;
    }

    // ---------------------------------------------------------------- check

    public async Task<List<ReleaseInfo>> ReleasesAsync(CancellationToken ct = default)
    {
        using var response = await _http.GetAsync($"https://api.github.com/repos/{Repository}/releases?per_page=50", ct);
        if ((int)response.StatusCode == 403 && response.Headers.TryGetValues("X-RateLimit-Remaining", out var left) && left.FirstOrDefault() == "0")
            throw new InvalidOperationException("GitHub's update check limit for this network is used up; try again in an hour.");
        response.EnsureSuccessStatusCode();
        return ParseReleases(await response.Content.ReadAsStringAsync(ct));
    }

    /// <summary>Releases (newest first) from the GitHub API's JSON: drafts and releases without an Atlas3K zip are left out.</summary>
    public static List<ReleaseInfo> ParseReleases(string json)
    {
        var list = new List<ReleaseInfo>();
        foreach (var r in JsonNode.Parse(json)!.AsArray())
        {
            if (r is null || r["draft"]?.GetValue<bool>() == true) continue;
            var tag = r["tag_name"]?.GetValue<string>() ?? "";
            if (SemVersion.TryParse(tag) is not { } version) continue;
            var assets = r["assets"]?.AsArray().OfType<JsonObject>().ToList() ?? [];
            var zip = assets.FirstOrDefault(a => a["name"]?.GetValue<string>() is { } n
                && n.StartsWith("Atlas3K", StringComparison.OrdinalIgnoreCase) && n.EndsWith(".zip", StringComparison.OrdinalIgnoreCase));
            if (zip is null) continue;
            var zipName = zip["name"]!.GetValue<string>();
            var notes = r["body"]?.GetValue<string>() ?? "";
            var shaAsset = assets.FirstOrDefault(a => a["name"]?.GetValue<string>() is { } n && n.Equals(zipName + ".sha256", StringComparison.OrdinalIgnoreCase));
            list.Add(new ReleaseInfo(version, tag, r["name"]?.GetValue<string>() ?? tag, r["prerelease"]?.GetValue<bool>() == true,
                r["published_at"]?.GetValue<DateTime>() ?? DateTime.MinValue, notes, r["html_url"]?.GetValue<string>() ?? "",
                zipName, zip["browser_download_url"]!.GetValue<string>(), zip["size"]?.GetValue<long>() ?? 0,
                ShaInNotes(notes))
            {
                ShaAssetUrl = shaAsset?["browser_download_url"]?.GetValue<string>(),
            });
        }
        return list.OrderByDescending(r => r.Version).ToList();
    }

    [GeneratedRegex(@"SHA-?256[^`\n]*`([0-9A-Fa-f]{64})`", RegexOptions.IgnoreCase)]
    private static partial Regex ShaPattern();

    private static string? ShaInNotes(string notes) => ShaPattern().Match(notes) is { Success: true } m ? m.Groups[1].Value.ToUpperInvariant() : null;

    /// <summary>The newest release on the channel that is newer than <paramref name="current"/>, or null.</summary>
    public static ReleaseInfo? Pick(IEnumerable<ReleaseInfo> releases, UpdateChannel channel, SemVersion current) =>
        releases.Where(r => channel == UpdateChannel.Unstable || !r.Prerelease)
            .Where(r => r.Version > current)
            .OrderByDescending(r => r.Version).FirstOrDefault();

    // ---------------------------------------------------------------- download

    /// <summary>Downloads and verifies the release zip and unpacks it to updates\&lt;version&gt;\files. Returns that folder.</summary>
    public async Task<string> DownloadAsync(ReleaseInfo release, IProgress<double>? progress = null, CancellationToken ct = default)
    {
        var dir = Path.Combine(UpdatesDir, release.Version.ToString());
        Directory.CreateDirectory(dir);
        var zipPath = Path.Combine(dir, release.AssetName);
        var expected = release.Sha256;
        if (release.ShaAssetUrl is { } shaUrl)
        {
            var text = await _http.GetStringAsync(shaUrl, ct);
            expected = text.Trim().Split(' ', '\t', '\n')[0].ToUpperInvariant();
        }
        if (expected is not { Length: 64 })
            throw new InvalidDataException($"release {release.Tag} has no SHA-256 checksum, so it cannot be verified; download it by hand from {release.PageUrl}");

        using (var response = await _http.GetAsync(release.AssetUrl, HttpCompletionOption.ResponseHeadersRead, ct))
        {
            response.EnsureSuccessStatusCode();
            var total = response.Content.Headers.ContentLength ?? release.AssetSize;
            await using var source = await response.Content.ReadAsStreamAsync(ct);
            await using var file = File.Create(zipPath + ".part");
            var buffer = new byte[1 << 16];
            long done = 0;
            int n;
            while ((n = await source.ReadAsync(buffer, ct)) > 0)
            {
                await file.WriteAsync(buffer.AsMemory(0, n), ct);
                done += n;
                if (total > 0) progress?.Report((double)done / total);
            }
        }
        string actual;
        await using (var f = File.OpenRead(zipPath + ".part")) actual = Convert.ToHexString(await SHA256.HashDataAsync(f, ct));
        if (!actual.Equals(expected, StringComparison.OrdinalIgnoreCase))
        {
            File.Delete(zipPath + ".part");
            throw new InvalidDataException($"the download of {release.AssetName} is damaged or was changed (SHA-256 {actual[..12]}…, expected {expected[..12]}…)");
        }
        File.Move(zipPath + ".part", zipPath, overwrite: true);

        var files = Path.Combine(dir, "files");
        if (Directory.Exists(files)) Directory.Delete(files, recursive: true);
        ZipFile.ExtractToDirectory(zipPath, files);
        // a zip may hold the files in one top folder
        var root = File.Exists(Path.Combine(files, "Atlas3K.exe")) ? files
            : Directory.GetDirectories(files).FirstOrDefault(d => File.Exists(Path.Combine(d, "Atlas3K.exe")))
              ?? throw new InvalidDataException($"{release.AssetName} holds no Atlas3K.exe");
        File.Delete(zipPath);
        return root;
    }

    // ---------------------------------------------------------------- apply

    /// <summary>
    /// Starts the helper that installs <paramref name="source"/> over <paramref name="install"/> once process
    /// <paramref name="waitForPid"/> (this Atlas3K) and any other program running from the install folder have exited,
    /// backing the install up to <see cref="BackupDir"/> first, then starts <paramref name="restart"/> (an exe in the
    /// install folder) unless null. The caller should exit right after.
    /// </summary>
    public static Process StartApply(string source, string install, int waitForPid, string? restart, string? restartArgs = null)
    {
        Directory.CreateDirectory(UpdatesDir);
        var script = Path.Combine(UpdatesDir, "apply_update.ps1");
        File.WriteAllText(script, ApplyScript);
        var args = new List<string>
        {
            "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", script,
            "-Source", LongPath(source), "-Target", LongPath(install), "-Backup", BackupDir,
            "-WaitPid", waitForPid.ToString(System.Globalization.CultureInfo.InvariantCulture), "-Log", LogPath,
        };
        if (restart is not null) args.AddRange(["-Restart", restart]);
        if (!string.IsNullOrEmpty(restartArgs)) args.AddRange(["-RestartArgs", restartArgs]);
        var psi = new ProcessStartInfo(PowerShellExe) { UseShellExecute = false, CreateNoWindow = true };
        foreach (var a in args) psi.ArgumentList.Add(a);
        return Process.Start(psi) ?? throw new InvalidOperationException("could not start the update helper (powershell.exe)");
    }

    /// <summary>The full path with 8.3 short names (C:\Users\ABCDEF~1) expanded: the helper compares it with running
    /// programs' paths, which are always long.</summary>
    public static string LongPath(string path)
    {
        var full = Path.GetFullPath(path).TrimEnd('\\', '/');
        if (!OperatingSystem.IsWindows()) return full;
        var buffer = new char[32768];
        var n = GetLongPathName(full, buffer, buffer.Length);
        return n > 0 && n < buffer.Length ? new string(buffer, 0, (int)n) : full;
    }

    [System.Runtime.InteropServices.DllImport("kernel32.dll", CharSet = System.Runtime.InteropServices.CharSet.Unicode, EntryPoint = "GetLongPathNameW")]
    private static extern uint GetLongPathName(string shortPath, char[] longPath, int size);

    /// <summary>Windows PowerShell by full path (it is not always on PATH).</summary>
    public static string PowerShellExe =>
        Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), "WindowsPowerShell", "v1.0", "powershell.exe") is var p && File.Exists(p)
            ? p : "powershell.exe";

    /// <summary>A rollback is possible when a previous install was backed up by an update.</summary>
    public static InstallInfo? Previous() => File.Exists(Path.Combine(BackupDir, "Atlas3K.exe")) ? Install(BackupDir) ?? new InstallInfo("?", "", BackupDir) : null;

    /// <summary>Starts the helper that puts the backed-up previous version back (the current one becomes the backup).</summary>
    public static Process StartRollback(string install, int waitForPid, string? restart)
    {
        if (Previous() is null) throw new InvalidOperationException("no previous version is kept");
        // the helper backs the install up over BackupDir, so roll back from a copy of it
        var source = Path.Combine(UpdatesDir, "rollback");
        if (Directory.Exists(source)) Directory.Delete(source, recursive: true);
        CopyTree(BackupDir, source);
        return StartApply(source, install, waitForPid, restart);
    }

    private static void CopyTree(string from, string to)
    {
        foreach (var dir in Directory.EnumerateDirectories(from, "*", SearchOption.AllDirectories))
            Directory.CreateDirectory(Path.Combine(to, Path.GetRelativePath(from, dir)));
        Directory.CreateDirectory(to);
        foreach (var file in Directory.EnumerateFiles(from, "*", SearchOption.AllDirectories))
            File.Copy(file, Path.Combine(to, Path.GetRelativePath(from, file)), overwrite: true);
    }

    /// <summary>The helper: wait, back up, copy (robocopy, retried), restore on failure, restart. Logs to -Log.</summary>
    public const string ApplyScript = """
        param([string]$Source, [string]$Target, [string]$Backup, [int]$WaitPid = 0, [string]$Log,
              [string]$Restart = "", [string]$RestartArgs = "")
        $ErrorActionPreference = "Stop"
        function Say($m) { Add-Content -Path $Log -Value ("[{0:yyyy-MM-dd HH:mm:ss}] {1}" -f (Get-Date), $m) }
        function Copy-Tree($from, $to) {
            & (Join-Path $env:SystemRoot "System32\robocopy.exe") $from $to /E /R:5 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
            if ($LASTEXITCODE -ge 8) { throw "robocopy $from -> $to failed ($LASTEXITCODE)" }
        }
        try {
            Say "update: $Source -> $Target"
            if ($WaitPid -gt 0) { Wait-Process -Id $WaitPid -Timeout 120 -ErrorAction SilentlyContinue }
            # other Atlas3K programs (CLI, web editor) running from the install folder must close too
            $deadline = (Get-Date).AddMinutes(2)
            while ($true) {
                $busy = @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.Path -and $_.Path.StartsWith($Target, [StringComparison]::OrdinalIgnoreCase) })
                if ($busy.Count -eq 0) { break }
                if ((Get-Date) -gt $deadline) { throw ("still running from the install folder: " + (($busy | ForEach-Object { $_.ProcessName }) -join ", ")) }
                Start-Sleep -Milliseconds 500
            }
            if (Test-Path $Backup) { Remove-Item $Backup -Recurse -Force }
            Copy-Tree $Target $Backup
            Say "backed up to $Backup"
            try {
                Copy-Tree $Source $Target
                Say "installed"
            } catch {
                Say "install failed, restoring: $_"
                Copy-Tree $Backup $Target
                throw
            }
        } catch {
            Say "FAILED: $_"
        } finally {
            if ($Restart) {
                $exe = Join-Path $Target $Restart
                if ($RestartArgs) { Start-Process -FilePath $exe -ArgumentList $RestartArgs } else { Start-Process -FilePath $exe }
            }
        }
        """;
}
