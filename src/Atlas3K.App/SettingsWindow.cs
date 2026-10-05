using System.IO;
using System.Windows;
using System.Windows.Controls;
using Atlas3K.Core;
using Microsoft.Win32;

namespace Atlas3K.App;

/// <summary>
/// Settings and first-run setup: the game, assembly kit and data folders (each checked live), developer mode, and
/// "Prepare game data", which extracts a vanilla map's compiled files and the tree DB tables from the user's own
/// install. Paths apply to windows opened after saving.
/// </summary>
public sealed class SettingsWindow : Window
{
    private readonly AppSettings _s = AppSettings.Current;
    private readonly bool _firstRun;
    private readonly TextBox _game = new(), _kit = new(), _compiled = new(), _db = new(), _output = new(), _cache = new();
    private readonly CheckBox _dev = new() { Content = "Developer mode (BOB launch, tile-matching simulation, comparison tools, self-tests)" };
    private readonly ComboBox _map = new() { MinWidth = 240, IsEditable = true };
    private readonly TextBox _log = new() { IsReadOnly = true, Height = 110, VerticalScrollBarVisibility = ScrollBarVisibility.Auto, FontSize = 11 };
    private readonly Button _prepare;
    private readonly TileMapSourcePanel _tileMap;

    public SettingsWindow(bool firstRun = false)
    {
        _firstRun = firstRun;
        Title = AppInfo.Title(firstRun ? "Welcome" : "Settings");
        Width = 820;
        SizeToContent = SizeToContent.Height;
        WindowStartupLocation = firstRun ? WindowStartupLocation.CenterScreen : WindowStartupLocation.CenterOwner;
        Background = Theme.Brush("Panel");
        Foreground = Theme.Brush("Text");
        _log.FontFamily = Theme.MonoFont;
        _prepare = Theme.IconButton(Theme.Glyph.Package, "Prepare game data", async (_, _) => await PrepareAsync(),
            "Extract the map's compiled files and the tree DB tables from your game install");

        var panel = new StackPanel { Margin = new Thickness(18) };
        if (firstRun)
        {
            panel.Children.Add(new TextBlock { Text = $"Welcome to {AppInfo.Product}", FontSize = 22, FontWeight = FontWeights.SemiBold });
            panel.Children.Add(new TextBlock
            {
                TextWrapping = TextWrapping.Wrap, Foreground = Theme.Brush("DimText"), Margin = new Thickness(0, 6, 0, 6),
                Text = "Check the folders below (found through Steam where possible), then prepare the game data for the map you want " +
                       "to edit. Nothing of the game's is shipped with Atlas3K: it reads your own install.",
            });
        }
        var detected = GameSetup.FindGameFolder();
        panel.Children.Add(Theme.Header("Folders", firstRun ? 8 : 0));
        panel.Children.Add(PathRow("Game folder", _game, _s.GameFolder, detected ?? "", p => Directory.Exists(Path.Combine(p, "data")),
                                   "Holds data\\ and assembly_kit\\; empty = found through Steam"));
        panel.Children.Add(PathRow("Assembly kit", _kit, _s.AssemblyKit, Path.Combine(Effective(_game, detected ?? ""), "assembly_kit"),
                                   p => Directory.Exists(Path.Combine(p, "raw_data")), "Empty = <game>\\assembly_kit (install it from Steam: Tools)"));
        panel.Children.Add(PathRow("Game data cache", _compiled, _s.CompiledRoot, Defaults.LocalData + "\\vanilla",
                                   p => Directory.Exists(Path.Combine(p, "terrain", "campaigns")), "Extracted compiled maps (Prepare game data fills it)"));
        panel.Children.Add(PathRow("DB tables", _db, _s.DbTsvFolder, Defaults.LocalData + "\\db",
                                   p => File.Exists(Path.Combine(p, "campaign_tree_ids_tables", "data__.tsv")), "Tree DB tables (Prepare game data fills it, or an RPFM TSV export)"));
        panel.Children.Add(PathRow("Output", _output, _s.OutputFolder, Defaults.LocalData + "\\output", _ => true, "Edit journals, build logs, previews"));
        panel.Children.Add(PathRow("Cache", _cache, _s.CacheFolder, Defaults.LocalData + "\\cache", _ => true, "Texture cache"));

        panel.Children.Add(Theme.Header("Tile map source"));
        _tileMap = new TileMapSourcePanel(_s.TileMap, () => new ProjectPaths());
        panel.Children.Add(_tileMap);

        panel.Children.Add(Theme.Header("Prepare game data"));
        var prep = new StackPanel { Orientation = Orientation.Horizontal };
        prep.Children.Add(new TextBlock { Text = "Map", VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(0, 0, 8, 0) });
        prep.Children.Add(_map);
        prep.Children.Add(new Border { Width = 8 });
        prep.Children.Add(_prepare);
        panel.Children.Add(prep);
        panel.Children.Add(_log);
        _log.Margin = new Thickness(0, 6, 0, 0);

        panel.Children.Add(Theme.Header("Other"));
        _dev.IsChecked = _s.DeveloperMode;
        panel.Children.Add(_dev);

        var buttons = new StackPanel { Orientation = Orientation.Horizontal, HorizontalAlignment = HorizontalAlignment.Right, Margin = new Thickness(0, 16, 0, 0) };
        buttons.Children.Add(new TextBlock { Text = "Folder changes apply to windows opened after saving.", Foreground = Theme.Brush("DimText"), VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(0, 0, 12, 0) });
        var ok = new Button { Content = firstRun ? "Continue" : "Save", IsDefault = true, MinWidth = 90, Style = (Style)FindResource("AccentButton") };
        ok.Click += (_, _) => { if (Save()) { DialogResult = true; } };
        buttons.Children.Add(ok);
        if (!firstRun)
        {
            var cancel = new Button { Content = "Cancel", IsCancel = true, MinWidth = 80, Margin = new Thickness(6, 0, 0, 0) };
            buttons.Children.Add(cancel);
        }
        panel.Children.Add(buttons);
        Content = panel;
        Loaded += async (_, _) => await LoadMapsAsync();
    }

    private UIElement PathRow(string label, TextBox box, string value, string placeholder, Func<string, bool> valid, string tip)
    {
        var grid = new Grid { Margin = new Thickness(0, 2, 0, 2), ToolTip = tip };
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(130) });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(22) });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        grid.Children.Add(new TextBlock { Text = label, VerticalAlignment = VerticalAlignment.Center });
        var mark = Theme.Icon(Theme.Glyph.Check, 13);
        Grid.SetColumn(mark, 1);
        grid.Children.Add(mark);
        box.Text = value;
        box.Tag = placeholder;
        void Check()
        {
            var path = Effective(box, placeholder);
            var ok = path.Length > 0 && valid(path);
            mark.Text = ok ? Theme.Glyph.Check : Theme.Glyph.Warning;
            mark.Foreground = Theme.Brush(ok ? "Ok" : "Warn");
            mark.ToolTip = ok ? path : $"not found: {path}";
        }
        box.TextChanged += (_, _) => Check();
        Check();
        Grid.SetColumn(box, 2);
        grid.Children.Add(box);
        var hint = new TextBlock { Text = placeholder, Foreground = Theme.Brush("DimText"), IsHitTestVisible = false, Margin = new Thickness(6, 0, 0, 0), VerticalAlignment = VerticalAlignment.Center };
        hint.Visibility = box.Text.Length == 0 ? Visibility.Visible : Visibility.Collapsed;
        box.TextChanged += (_, _) => hint.Visibility = box.Text.Length == 0 ? Visibility.Visible : Visibility.Collapsed;
        Grid.SetColumn(hint, 2);
        grid.Children.Add(hint);
        var browse = new Button { Content = "…", Padding = new Thickness(8, 0, 8, 0), Margin = new Thickness(4, 0, 0, 0) };
        browse.Click += (_, _) =>
        {
            var dlg = new OpenFolderDialog { Title = label };
            if (dlg.ShowDialog(this) == true) box.Text = dlg.FolderName;
        };
        Grid.SetColumn(browse, 3);
        grid.Children.Add(browse);
        return grid;
    }

    private static string Effective(TextBox box, string placeholder) =>
        box.Text.Trim().Length > 0 ? box.Text.Trim() : (box.Tag as string ?? placeholder);

    private string GameData => Path.Combine(Effective(_game, GameSetup.FindGameFolder() ?? ""), "data");

    private async Task LoadMapsAsync()
    {
        var data = GameData;
        if (!Directory.Exists(data)) { _log.Text = $"Game data folder not found ({data}). Set the game folder first."; return; }
        try
        {
            var maps = await Task.Run(() => GameSetup.VanillaMaps(data));
            _map.ItemsSource = maps;
            _map.SelectedItem = maps.FirstOrDefault(m => m == "3k_dlc07_main_map") ?? maps.FirstOrDefault(m => m.Contains("main_map")) ?? maps.FirstOrDefault();
        }
        catch (Exception e) when (e is IOException or InvalidDataException or NotSupportedException)
        {
            _log.Text = "Could not list the game's maps: " + e.Message;
        }
    }

    private async Task PrepareAsync()
    {
        var map = _map.Text.Trim();
        if (map.Length == 0) return;
        var data = GameData;
        var compiled = Effective(_compiled, Defaults.LocalData + "\\vanilla");
        var db = Effective(_db, Defaults.LocalData + "\\db");
        _prepare.IsEnabled = false;
        void Log(string m) => Dispatcher.BeginInvoke(() => { _log.AppendText(m + "\n"); _log.ScrollToEnd(); });
        try
        {
            Log($"extracting {map} from {data} ...");
            await Task.Run(() =>
            {
                GameSetup.ExtractCompiledMap(data, map, compiled, Log);
                GameSetup.ExtractDbTables(data, db, Log);
            });
            Log("done.");
        }
        catch (Exception e)
        {
            Log("failed: " + e.Message);
            ErrorDialog.Log("Prepare game data failed", e);
        }
        finally { _prepare.IsEnabled = true; }
    }

    private bool Save()
    {
        _s.GameFolder = _game.Text.Trim();
        _s.AssemblyKit = _kit.Text.Trim();
        _s.CompiledRoot = _compiled.Text.Trim();
        _s.DbTsvFolder = _db.Text.Trim();
        _s.OutputFolder = _output.Text.Trim();
        _s.CacheFolder = _cache.Text.Trim();
        _s.DeveloperMode = _dev.IsChecked == true;
        _s.TileMap = _tileMap.StoredValue;
        try
        {
            _s.Save();
            return true;
        }
        catch (Exception e) when (e is IOException or UnauthorizedAccessException)
        {
            ErrorDialog.Show(this, "Could not save the settings.", e);
            return false;
        }
    }
}
