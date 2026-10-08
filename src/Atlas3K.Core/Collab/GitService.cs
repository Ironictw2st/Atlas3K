using System.Diagnostics;
using System.Text;

namespace Atlas3K.Core.Collab;

/// <summary>
/// Runs git (and git-lfs, gh) in a repository. The CLIs are used rather than a library because LFS (needed for the
/// map's rasters) is only implemented by git-lfs itself.
/// </summary>
public sealed class GitService(string root)
{
    public sealed record Output(int ExitCode, string StdOut, string StdErr)
    {
        public bool Ok => ExitCode == 0;
        public string Text => StdOut.TrimEnd();
    }

    public string Root { get; } = Path.GetFullPath(root);

    /// <summary>git with the given arguments; throws with git's message unless <paramref name="check"/> is false.</summary>
    public Output Git(params string[] args) => Run("git", args, check: true);
    public Output TryGit(params string[] args) => Run("git", args, check: false);
    public Output Gh(params string[] args) => Run("gh", args, check: true);
    public Output TryGh(params string[] args) => Run("gh", args, check: false);

    public Output Run(string exe, IEnumerable<string> args, bool check, byte[]? stdin = null, string? cwd = null)
    {
        var bytes = RunBytes(exe, args, stdin, cwd);
        var result = new Output(bytes.ExitCode, Encoding.UTF8.GetString(bytes.StdOut), bytes.StdErr);
        if (check && !result.Ok)
            throw new InvalidOperationException($"{exe} {string.Join(' ', args)} failed: {(result.StdErr.Trim().Length > 0 ? result.StdErr.Trim() : result.Text)}");
        return result;
    }

    public (int ExitCode, byte[] StdOut, string StdErr) RunBytes(string exe, IEnumerable<string> args, byte[]? stdin = null, string? cwd = null)
    {
        var psi = new ProcessStartInfo(exe)
        {
            WorkingDirectory = cwd ?? Root,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            RedirectStandardInput = stdin is not null,
            UseShellExecute = false,
            CreateNoWindow = true,
            StandardErrorEncoding = Encoding.UTF8,
        };
        foreach (var a in args) psi.ArgumentList.Add(a);
        psi.Environment["GIT_TERMINAL_PROMPT"] = "0";
        psi.Environment["GH_PROMPT_DISABLED"] = "1";
        using var p = Process.Start(psi) ?? throw new InvalidOperationException($"cannot start {exe}");
        var err = p.StandardError.ReadToEndAsync();
        if (stdin is not null)
        {
            var write = Task.Run(() =>
            {
                p.StandardInput.BaseStream.Write(stdin);
                p.StandardInput.Close();
            });
            using var ms = new MemoryStream();
            p.StandardOutput.BaseStream.CopyTo(ms);
            write.Wait();
            p.WaitForExit();
            return (p.ExitCode, ms.ToArray(), err.Result);
        }
        using var output = new MemoryStream();
        p.StandardOutput.BaseStream.CopyTo(output);
        p.WaitForExit();
        return (p.ExitCode, output.ToArray(), err.Result);
    }

    /// <summary>Whether a tool is on PATH (git, git-lfs via "git lfs", gh).</summary>
    public static bool Available(string exe, params string[] versionArgs)
    {
        try { return new GitService(Environment.CurrentDirectory).Run(exe, versionArgs.Length > 0 ? versionArgs : ["--version"], false).Ok; }
        catch (System.ComponentModel.Win32Exception) { return false; }
    }

    /// <summary>The top of the work tree containing <paramref name="path"/>, or null.</summary>
    public static string? FindRoot(string path)
    {
        var dir = Directory.Exists(path) ? path : Path.GetDirectoryName(Path.GetFullPath(path));
        for (; dir is not null; dir = Path.GetDirectoryName(dir))
            if (Directory.Exists(Path.Combine(dir, ".git")) || File.Exists(Path.Combine(dir, ".git"))) return dir;
        return null;
    }

    public string GitDir => Path.GetFullPath(Path.Combine(Root, Git("rev-parse", "--git-dir").Text));

    // ---------------------------------------------------------------- LFS

    private static readonly byte[] LfsHeader = "version https://git-lfs.github.com/spec/v1"u8.ToArray();

    public static bool IsLfsPointer(byte[] bytes) => bytes.Length < 1024 && bytes.AsSpan().StartsWith(LfsHeader);

    /// <summary>The real content of an LFS pointer (fetched if needed); other bytes are returned as they are.</summary>
    public byte[] Smudge(byte[] bytes, string pathForFilter)
    {
        if (!IsLfsPointer(bytes)) return bytes;
        var r = RunBytes("git", ["lfs", "smudge", "--", pathForFilter], bytes);
        if (r.ExitCode != 0) throw new InvalidOperationException($"git lfs smudge failed: {r.StdErr.Trim()}");
        return r.StdOut;
    }

    /// <summary>Stores content in LFS and returns its pointer (what the repository records).</summary>
    public byte[] Clean(byte[] content, string pathForFilter)
    {
        var r = RunBytes("git", ["lfs", "clean", "--", pathForFilter], content);
        if (r.ExitCode != 0) throw new InvalidOperationException($"git lfs clean failed: {r.StdErr.Trim()}");
        return r.StdOut;
    }

    /// <summary>A file's content at a revision (LFS resolved), or null when it does not exist there.</summary>
    public byte[]? Show(string rev, string relPath)
    {
        var r = RunBytes("git", ["show", $"{rev}:{relPath.Replace('\\', '/')}"]);
        return r.ExitCode == 0 ? Smudge(r.StdOut, relPath) : null;
    }
}
