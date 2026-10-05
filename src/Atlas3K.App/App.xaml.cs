using System.IO;
using System.Windows;
using Atlas3K.Core;

namespace Atlas3K.App;

/// <summary>
/// Opens the start page, or straight into one editor: <c>--scene [project.terry]</c> (default: the campaign map's
/// .terry), <c>--tile-editor [tile_map.png]</c> (default: the kit's), <c>--battle &lt;source folder&gt;</c>,
/// <c>--painter</c> (terrain painter), <c>--build [project.atlas3k]</c>; plus the usual <c>--map</c> / <c>--ak</c> /
/// <c>--root</c>. The first start shows the setup dialog. Developer mode adds the test flags (--selftest, tours, --shots).
/// </summary>
public partial class App : Application
{
    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);
        DispatcherUnhandledException += (_, args) =>
        {
            ErrorDialog.Show(MainWindow, "Something went wrong. Your last edit may not have been applied.", args.Exception);
            args.Handled = true;
        };
        AppDomain.CurrentDomain.UnhandledException += (_, args) => ErrorDialog.Log("Unhandled exception", args.ExceptionObject as Exception);
        // every window gets the app icon (WPF windows don't inherit the exe's)
        var icon = new System.Windows.Media.Imaging.BitmapImage(new Uri("pack://application:,,,/Assets/atlas3k.ico"));
        EventManager.RegisterClassHandler(typeof(Window), FrameworkElement.LoadedEvent, new RoutedEventHandler((w, _) =>
        {
            if (w is Window { Icon: null } window) window.Icon = icon;
        }));

        if (!File.Exists(AppSettings.FilePath) && e.Args.Length == 0)
        {
            ShutdownMode = ShutdownMode.OnExplicitShutdown;
            if (new SettingsWindow(firstRun: true).ShowDialog() != true) { Shutdown(); return; }
            ShutdownMode = ShutdownMode.OnLastWindowClose;
        }

        var paths = ProjectPaths.FromArgs(e.Args, out var rest);
        int Flag(string name) => Array.FindIndex(rest, a => a.Equals(name, StringComparison.OrdinalIgnoreCase));
        string? Value(int i) => i >= 0 && i + 1 < rest.Length && !rest[i + 1].StartsWith("--") ? rest[i + 1] : null;
        int battle = Flag("--battle"), tiles = Flag("--tile-editor"), scene = Flag("--scene"), build = Flag("--build"), painter = Flag("--painter");

        if (build >= 0)
        {
            var window = BuildWindow.Show(null, paths, Value(build) is { } p ? Path.GetFullPath(p) : null);
            MainWindow = window;
            return;
        }
        MainWindow = scene >= 0 ? new Scene.SceneWindow(paths, Value(scene) is { } s ? Path.GetFullPath(s) : null)
            : battle >= 0 && Value(battle) is { } b ? new BattleWindow(b, paths)
            : tiles >= 0 ? new CampaignTileWindow(paths, Value(tiles) is { } t ? Path.GetFullPath(t) : null)
            : painter >= 0 ? new MainWindow(paths)
            : new StartWindow(paths);
        MainWindow.Show();

        if (!AppSettings.Current.DeveloperMode || MainWindow is not Scene.SceneWindow sceneWindow) return;
        var selftest = Flag("--selftest");
        if (selftest >= 0 && Value(selftest) is { } dir)
            _ = sceneWindow.SelfTestAsync(Path.GetFullPath(dir));
        foreach (var kind in new[] { "city", "region" })
        {
            var ti = Flag($"--{kind}-tour");
            if (ti >= 0 && ti + 1 < rest.Length)
                _ = sceneWindow.TourAsync(kind, Path.GetFullPath(rest[ti + 1]), ti + 2 < rest.Length && !rest[ti + 2].StartsWith("--") ? rest[ti + 2] : null);
        }
        var shots = Flag("--shots");
        if (shots >= 0 && shots + 2 < rest.Length)
            _ = sceneWindow.ShotsAsync(Path.GetFullPath(rest[shots + 1]), Path.GetFullPath(rest[shots + 2]));
    }

    protected override void OnExit(ExitEventArgs e)
    {
        try { AppSettings.Current.Save(); }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException) { ErrorDialog.Log("Saving settings failed", ex); }
        base.OnExit(e);
    }
}
