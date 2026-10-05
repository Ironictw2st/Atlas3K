using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using Atlas3K.Core;
using Atlas3K.Core.Build;

namespace Atlas3K.App;

/// <summary>The front door: open an editor for the current map, build, or reopen a recent project.</summary>
public sealed class StartWindow : Window
{
    private static StartWindow? _open;
    private readonly ProjectPaths _paths;

    public static void ShowSingle(ProjectPaths paths)
    {
        if (_open is null)
        {
            _open = new StartWindow(paths);
            _open.Closed += (_, _) => _open = null;
            _open.Show();
        }
        else _open.Activate();
    }

    public StartWindow(ProjectPaths paths)
    {
        _paths = paths;
        _open ??= this;
        Closed += (_, _) => { if (_open == this) _open = null; };
        Title = AppInfo.Title("Start");
        Width = 980;
        Height = 660;
        WindowStartupLocation = WindowStartupLocation.CenterScreen;
        Background = Theme.Brush("Bg");
        Foreground = Theme.Brush("Text");
        Content = BuildLayout();
    }

    private UIElement BuildLayout()
    {
        var dock = new DockPanel();
        var menu = new Menu();
        var file = new MenuItem { Header = "_File" };
        file.Items.Add(StandardMenus.Item("_Settings…", () => new SettingsWindow { Owner = this }.ShowDialog()));
        file.Items.Add(new Separator());
        file.Items.Add(StandardMenus.Item("E_xit", () => Application.Current.Shutdown()));
        menu.Items.Add(file);
        StandardMenus.AddTo(menu, this, _paths);
        DockPanel.SetDock(menu, Dock.Top);
        dock.Children.Add(menu);

        var grid = new Grid { Margin = new Thickness(36, 24, 36, 24) };
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(3, GridUnitType.Star) });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(32) });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(2, GridUnitType.Star) });

        // left: title + editor tiles
        var left = new StackPanel();
        var title = new StackPanel { Orientation = Orientation.Horizontal };
        title.Children.Add(Theme.Icon(Theme.Glyph.Map, 36, Theme.Brush("Accent")));
        var names = new StackPanel { Margin = new Thickness(14, 0, 0, 0) };
        names.Children.Add(new TextBlock { Text = AppInfo.Product, FontSize = 30, FontWeight = FontWeights.SemiBold });
        names.Children.Add(new TextBlock { Text = $"{AppInfo.Tagline} · {AppInfo.Version}", Foreground = Theme.Brush("DimText") });
        title.Children.Add(names);
        left.Children.Add(title);

        var mapLine = new TextBlock { Margin = new Thickness(0, 22, 0, 10), TextWrapping = TextWrapping.Wrap, Foreground = Theme.Brush("DimText") };
        mapLine.Inlines.Add("Map ");
        mapLine.Inlines.Add(new System.Windows.Documents.Run(_paths.MapName) { Foreground = Theme.Brush("Text"), FontWeight = FontWeights.SemiBold });
        mapLine.Inlines.Add($"   ·   kit {_paths.AssemblyKitRoot}");
        left.Children.Add(mapLine);

        var tiles = new WrapPanel();
        tiles.Children.Add(Tile(Theme.Glyph.Scene, "Scene editor", "Props, entities, prefabs, layers; 2D and 3D views of the campaign map.",
                                () => new Scene.SceneWindow(_paths).Show()));
        tiles.Children.Add(Tile(Theme.Glyph.Tiles, "Tile map", "Paint the campaign tile map hex by hex, with live validation.",
                                () => new CampaignTileWindow(_paths).Show()));
        tiles.Children.Add(Tile(Theme.Glyph.Terrain, "Terrain painter", "Heights, ground textures and trees on the compiled map.",
                                () => new MainWindow(_paths).Show()));
        tiles.Children.Add(Tile(Theme.Glyph.Build, "Build", "Compile the map natively, run custom steps, pack and install.",
                                () => BuildWindow.Show(this, _paths)));
        left.Children.Add(tiles);
        Grid.SetColumn(left, 0);
        grid.Children.Add(left);

        // right: recent projects
        var right = new StackPanel();
        right.Children.Add(Theme.Header("Recent projects", 6));
        var recent = AppSettings.Current.RecentProjects.Where(File.Exists).Take(8).ToList();
        if (recent.Count == 0)
            right.Children.Add(new TextBlock
            {
                TextWrapping = TextWrapping.Wrap, Foreground = Theme.Brush("DimText"),
                Text = "No projects yet. A project (.atlas3k) holds a map's build profile: open Build and create one.",
            });
        foreach (var r in recent)
        {
            string name;
            try { name = BuildProject.Load(r) is var p && p.Name.Length > 0 ? p.Name : Path.GetFileNameWithoutExtension(r); }
            catch (Exception e) when (e is IOException or InvalidDataException or System.Text.Json.JsonException) { name = Path.GetFileNameWithoutExtension(r); }
            var b = new Button
            {
                HorizontalContentAlignment = HorizontalAlignment.Left, Margin = new Thickness(0, 2, 0, 2), Padding = new Thickness(10, 6, 10, 6),
                Content = new StackPanel
                {
                    Children =
                    {
                        new TextBlock { Text = name, FontWeight = FontWeights.SemiBold },
                        new TextBlock { Text = r, Foreground = Theme.Brush("DimText"), FontSize = 11, TextTrimming = TextTrimming.CharacterEllipsis },
                    },
                },
                ToolTip = r,
            };
            b.Click += (_, _) => BuildWindow.Show(this, _paths, r);
            right.Children.Add(b);
        }
        right.Children.Add(Theme.Header("Get started", 20));
        right.Children.Add(new TextBlock
        {
            TextWrapping = TextWrapping.Wrap, Foreground = Theme.Brush("DimText"),
            Text = "1. Check your game and assembly kit folders in File > Settings.\n" +
                   "2. Edit the map in the Scene editor or Tile map.\n" +
                   "3. Open Build (Ctrl+B), create a project for the map and press Build all.\n" +
                   "Back up your assembly kit before building over it: this is alpha software.",
        });
        Grid.SetColumn(right, 2);
        grid.Children.Add(right);

        dock.Children.Add(new ScrollViewer { VerticalScrollBarVisibility = ScrollBarVisibility.Auto, Content = grid });
        return dock;
    }

    private static Button Tile(string glyph, string title, string text, Action open)
    {
        var content = new StackPanel { Width = 220 };
        content.Children.Add(Theme.Icon(glyph, 26, Theme.Brush("Accent")));
        content.Children.Add(new TextBlock { Text = title, FontSize = 16, FontWeight = FontWeights.SemiBold, Margin = new Thickness(0, 10, 0, 4) });
        content.Children.Add(new TextBlock { Text = text, TextWrapping = TextWrapping.Wrap, Foreground = Theme.Brush("DimText") });
        var b = new Button
        {
            Content = content, Padding = new Thickness(16), Margin = new Thickness(0, 0, 12, 12),
            HorizontalContentAlignment = HorizontalAlignment.Left, VerticalContentAlignment = VerticalAlignment.Top,
            Background = Theme.Brush("Panel"), Height = 150,
        };
        b.Click += (_, _) =>
        {
            try { open(); }
            catch (Exception e) { ErrorDialog.Show(Window.GetWindow(b), $"Could not open {title}.", e); }
        };
        return b;
    }
}
