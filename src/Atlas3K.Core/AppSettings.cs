using System.Text.Json;
using System.Text.Json.Serialization;

namespace Atlas3K.Core;

/// <summary>Per-user settings, <c>%AppData%\Atlas3K\settings.json</c>: tool paths, recent projects, window placement.</summary>
public sealed class AppSettings
{
    public static string Folder { get; } = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "Atlas3K");
    public static string FilePath => Path.Combine(Folder, "settings.json");

    /// <summary>Game install (the folder holding data\ and assembly_kit\); empty = auto-detect.</summary>
    public string GameFolder { get; set; } = "";
    /// <summary>Default assembly kit; empty = &lt;game&gt;\assembly_kit.</summary>
    public string AssemblyKit { get; set; } = "";
    public string DbTsvFolder { get; set; } = "";
    public string CompiledRoot { get; set; } = "";
    public string OutputFolder { get; set; } = "";
    public string CacheFolder { get; set; } = "";
    /// <summary>Default tile map source (kit, file or pack) when no project sets one; null = the kit.</summary>
    public Campaign.TileMapCheck.TileMapSource? TileMap { get; set; }
    /// <summary>The map the Start screen opens editors on; empty = 3k_dlc07_main_map.</summary>
    public string MapName { get; set; } = "";
    /// <summary>Mod packs linked as read-only sources (compiled map files, DB tables, assets), highest priority first.
    /// Never written: edits go to the assembly kit or the output folder.</summary>
    public List<string> LinkedPacks { get; set; } = [];
    public List<string> RecentProjects { get; set; } = [];
    public bool DeveloperMode { get; set; }
    public Dictionary<string, WindowPlacement> Windows { get; set; } = [];
    /// <summary>Free-form remembered UI values (last tool, last texture, ...).</summary>
    public Dictionary<string, string> Values { get; set; } = [];

    public sealed record WindowPlacement(double Left, double Top, double Width, double Height, bool Maximized);

    private static readonly JsonSerializerOptions Json = new()
    {
        WriteIndented = true,
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    };

    private static AppSettings? _current;
    /// <summary>Loaded once per process; a missing or unreadable file gives defaults.</summary>
    public static AppSettings Current => _current ??= Load();

    private static AppSettings Load()
    {
        try
        {
            if (File.Exists(FilePath)) return JsonSerializer.Deserialize<AppSettings>(File.ReadAllText(FilePath), Json) ?? new();
        }
        catch (JsonException)
        {
            // keep the broken file for the user instead of overwriting it with defaults on the next save
            try { File.Copy(FilePath, FilePath + ".bad", overwrite: true); } catch (IOException) { }
        }
        catch (Exception e) when (e is IOException or UnauthorizedAccessException) { }
        return new AppSettings();
    }

    public void Save()
    {
        Directory.CreateDirectory(Folder);
        var temp = FilePath + ".tmp";
        File.WriteAllText(temp, JsonSerializer.Serialize(this, Json));
        File.Move(temp, FilePath, overwrite: true);
    }

    /// <summary>Adds a pack to <see cref="LinkedPacks"/> (full path, no duplicates); false when it was already linked.</summary>
    public bool LinkPack(string packPath)
    {
        packPath = Path.GetFullPath(packPath);
        if (!packPath.EndsWith(".pack", StringComparison.OrdinalIgnoreCase)) throw new ArgumentException($"{packPath} is not a .pack file");
        if (LinkedPacks.Any(p => p.Equals(packPath, StringComparison.OrdinalIgnoreCase))) return false;
        LinkedPacks.Add(packPath);
        return true;
    }

    public bool UnlinkPack(string packPath) =>
        LinkedPacks.RemoveAll(p => p.Equals(Path.GetFullPath(packPath), StringComparison.OrdinalIgnoreCase)) > 0;

    public void AddRecentProject(string path)
    {
        path = Path.GetFullPath(path);
        RecentProjects.RemoveAll(p => p.Equals(path, StringComparison.OrdinalIgnoreCase));
        RecentProjects.Insert(0, path);
        if (RecentProjects.Count > 10) RecentProjects.RemoveRange(10, RecentProjects.Count - 10);
    }
}
