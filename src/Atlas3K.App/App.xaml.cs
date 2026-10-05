using System.IO;
using System.Windows;
using Atlas3K.Core;

namespace Atlas3K.App;

/// <summary>
/// Starts the campaign editor, only the battle-map editor with <c>--battle &lt;source folder&gt;</c>, or only the
/// campaign tile-map editor with <c>--tile-editor [tile_map.png]</c> (default: the kit's), or only the Terry scene editor
/// with <c>--scene [project.terry]</c> (default: the campaign map's .terry); plus the usual <c>--map</c> /
/// <c>--ak</c> / <c>--root</c>).
/// </summary>
public partial class App : Application
{
    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);
        var paths = ProjectPaths.FromArgs(e.Args, out var rest);
        var i = Array.FindIndex(rest, a => a.Equals("--battle", StringComparison.OrdinalIgnoreCase));
        var t = Array.FindIndex(rest, a => a.Equals("--tile-editor", StringComparison.OrdinalIgnoreCase));
        var s = Array.FindIndex(rest, a => a.Equals("--scene", StringComparison.OrdinalIgnoreCase));
        MainWindow = s >= 0 ? new Scene.SceneWindow(paths, s + 1 < rest.Length && !rest[s + 1].StartsWith("--") ? Path.GetFullPath(rest[s + 1]) : null)
            : i >= 0 && i + 1 < rest.Length ? new BattleWindow(rest[i + 1], paths)
            : t >= 0 ? new CampaignTileWindow(paths, t + 1 < rest.Length ? Path.GetFullPath(rest[t + 1]) : null)
            : new MainWindow();
        MainWindow.Show();
        var selftest = Array.FindIndex(rest, a => a.Equals("--selftest", StringComparison.OrdinalIgnoreCase));
        if (selftest >= 0 && selftest + 1 < rest.Length && MainWindow is Scene.SceneWindow scene)
            _ = scene.SelfTestAsync(Path.GetFullPath(rest[selftest + 1]));
        foreach (var kind in new[] { "city", "region" })
        {
            var ti = Array.FindIndex(rest, a => a.Equals($"--{kind}-tour", StringComparison.OrdinalIgnoreCase));
            if (ti >= 0 && ti + 1 < rest.Length && MainWindow is Scene.SceneWindow tourScene)
                _ = tourScene.TourAsync(kind, Path.GetFullPath(rest[ti + 1]), ti + 2 < rest.Length && !rest[ti + 2].StartsWith("--") ? rest[ti + 2] : null);
        }
        var shots = Array.FindIndex(rest, a => a.Equals("--shots", StringComparison.OrdinalIgnoreCase));
        if (shots >= 0 && shots + 2 < rest.Length && MainWindow is Scene.SceneWindow shotScene)
            _ = shotScene.ShotsAsync(Path.GetFullPath(rest[shots + 1]), Path.GetFullPath(rest[shots + 2]));
    }
}
