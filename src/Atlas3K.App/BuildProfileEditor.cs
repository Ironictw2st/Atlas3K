using System.Collections.ObjectModel;
using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Data;
using Atlas3K.Core;
using Atlas3K.Core.Build;
using Microsoft.Win32;

namespace Atlas3K.App;

/// <summary>The Build window's Profile tab: edits a <see cref="BuildProject"/> in place and calls back on every change.</summary>
public sealed class BuildProfileEditor : ScrollViewer
{
    private enum Browse { None, Folder, File, SaveFile }

    private readonly BuildProject _project;
    private readonly Func<ProjectPaths> _paths;
    private readonly Action _changed;
    private readonly ObservableCollection<CustomStep> _custom;
    private readonly ObservableCollection<PackContent> _contents;

    public BuildProfileEditor(BuildProject project, Func<ProjectPaths> paths, Action changed)
    {
        _project = project;
        _paths = paths;
        _changed = changed;
        _custom = new ObservableCollection<CustomStep>(project.Build.CustomSteps);
        _contents = new ObservableCollection<PackContent>(project.Build.Pack.Contents);
        _custom.CollectionChanged += (_, _) => { project.Build.CustomSteps = [.. _custom]; changed(); };
        _contents.CollectionChanged += (_, _) => { project.Build.Pack.Contents = [.. _contents]; changed(); };
        VerticalScrollBarVisibility = ScrollBarVisibility.Auto;
        Content = BuildForm();
    }

    private UIElement BuildForm()
    {
        var b = _project.Build;
        var form = new StackPanel { Margin = new Thickness(14, 6, 14, 14), MaxWidth = 1100, HorizontalAlignment = HorizontalAlignment.Left };

        form.Children.Add(Theme.Header("Project", 4));
        form.Children.Add(Field("Name", () => _project.Name, v => _project.Name = v));
        form.Children.Add(Field("Map", () => _project.Map, v => _project.Map = v, tip: "Campaign map name, e.g. 3k_main_map"));
        form.Children.Add(Field("Assembly kit", () => _project.AssemblyKit, v => _project.AssemblyKit = v, Browse.Folder, "Empty = the default kit (Settings)"));
        form.Children.Add(Field("Game data", () => _project.GameData, v => _project.GameData = v, Browse.Folder, "Empty = the default game data folder"));
        form.Children.Add(Field("Mod packs", () => string.Join("; ", _project.ModPacks), v => _project.ModPacks = Split(v, ';'),
                                tip: "Packs searched before vanilla for assets, highest priority first; separate with ;"));

        form.Children.Add(Theme.Header("Tile map source"));
        var tileMap = new TileMapSourcePanel(_project.TileMap, _paths);
        tileMap.Changed += () => { _project.TileMap = tileMap.StoredValue; _changed(); };
        form.Children.Add(tileMap);

        form.Children.Add(Theme.Header("Compile"));
        form.Children.Add(Field("Output", () => b.Output, v => b.Output = v, Browse.Folder,
                                "Where Compile writes, laid out like working_data. {ak}\\working_data replaces the kit's output in place, as BOB did."));
        form.Children.Add(Field("Accept tile-map codes", () => string.Join(", ", b.AcceptTileMap), v => b.AcceptTileMap = Split(v, ','),
                                tip: "Tile-map pre-flight errors to tolerate, e.g. layout.mesh_columns"));
        form.Children.Add(Field("Clean before compile", () => string.Join(", ", b.Clean), v => b.Clean = Split(v, ','),
                                tip: "Folders under the compiled terrain folder to delete first, e.g. global_meshes, height_patches, models"));
        form.Children.Add(Field("Backup folder", () => b.Backup, v => b.Backup = v, Browse.Folder,
                                "When set, a rolling copy of the raw and compiled terrain is kept here before each compile"));

        form.Children.Add(Theme.Header("Custom steps"));
        form.Children.Add(new TextBlock
        {
            TextWrapping = TextWrapping.Wrap, Foreground = Theme.Brush("DimText"), Margin = new Thickness(0, 0, 0, 6),
            Text = "External commands run as part of the build (python scripts, CAIME, an RPFM startpos build…). Tokens in command, arguments and " +
                   "working folder: {project} {ak} {map} {game} {out} {pack}. They also get ATLAS3K_AK, ATLAS3K_MAP, ATLAS3K_OUT, ATLAS3K_GAME, " +
                   "ATLAS3K_PACK, ATLAS3K_PROJECT and ATLAS3K_CLI as environment variables.",
        });
        form.Children.Add(CustomGrid());

        form.Children.Add(Theme.Header("Pack"));
        form.Children.Add(Combo("Mode", Enum.GetValues<PackMode>(), () => b.Pack.Mode, v => b.Pack.Mode = v,
                                "New: a pack with only the contents below. Merge: the base pack with the contents replacing or adding files."));
        form.Children.Add(Field("Output pack", () => b.Pack.Output, v => b.Pack.Output = v, Browse.SaveFile, "e.g. {game}\\my_map.pack or {project}\\{map}.pack"));
        form.Children.Add(Field("Merge base", () => b.Pack.Base, v => b.Pack.Base = v, Browse.File, "Merge only. Empty = merge into the output pack itself"));
        form.Children.Add(Field("Replace folders", () => string.Join(", ", b.Pack.ReplaceDirs), v => b.Pack.ReplaceDirs = Split(v, ','),
                                tip: "Merge only: pack folders whose old files are dropped unless re-added, e.g. terrain/campaigns/{map}/"));
        form.Children.Add(new TextBlock { Text = "Contents (later rows win for the same pack path)", Foreground = Theme.Brush("DimText"), Margin = new Thickness(0, 8, 0, 4) });
        form.Children.Add(ContentsGrid());

        form.Children.Add(Theme.Header("Install"));
        form.Children.Add(Check("Keep a backup of the pack being replaced", () => b.Install.Backup, v => b.Install.Backup = v));
        form.Children.Add(new TextBlock
        {
            TextWrapping = TextWrapping.Wrap, Foreground = Theme.Brush("DimText"),
            Text = "Install copies the output pack into the game's data folder (skipped when it is already there). It refuses while the game is running.",
        });
        return form;
    }

    // ------------------------------------------------------------------ grids

    private UIElement CustomGrid()
    {
        var grid = new DataGrid
        {
            ItemsSource = _custom, AutoGenerateColumns = false, CanUserAddRows = false, MinHeight = 90, MaxHeight = 260,
            HeadersVisibility = DataGridHeadersVisibility.Column, SelectionMode = DataGridSelectionMode.Single,
        };
        grid.Columns.Add(new DataGridCheckBoxColumn { Header = "On", Binding = new Binding(nameof(CustomStep.Enabled)) });
        grid.Columns.Add(new DataGridTextColumn { Header = "Name", Binding = new Binding(nameof(CustomStep.Name)), Width = 140 });
        grid.Columns.Add(new DataGridComboBoxColumn { Header = "Runs", ItemsSource = Enum.GetValues<CustomStepStage>(), SelectedItemBinding = new Binding(nameof(CustomStep.RunAt)), Width = 110 });
        grid.Columns.Add(new DataGridTextColumn { Header = "Command", Binding = new Binding(nameof(CustomStep.Command)), Width = 110 });
        grid.Columns.Add(new DataGridTextColumn { Header = "Arguments", Binding = new Binding(nameof(CustomStep.Arguments)), Width = new DataGridLength(1, DataGridLengthUnitType.Star) });
        grid.Columns.Add(new DataGridTextColumn { Header = "Working folder", Binding = new Binding(nameof(CustomStep.WorkingDir)), Width = 130 });
        grid.Columns.Add(new DataGridTextColumn { Header = "Timeout (s)", Binding = new Binding(nameof(CustomStep.TimeoutSeconds)), Width = 80 });
        grid.Columns.Add(new DataGridCheckBoxColumn { Header = "Continue on error", Binding = new Binding(nameof(CustomStep.ContinueOnError)) });
        grid.CellEditEnding += (_, _) => Dispatcher.BeginInvoke(() => { _project.Build.CustomSteps = [.. _custom]; _changed(); });

        var buttons = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 4, 0, 0) };
        buttons.Children.Add(Theme.IconButton(Theme.Glyph.New, "Add", (_, _) =>
        {
            var name = UniqueName("step");
            _custom.Add(new CustomStep { Name = name, Command = "python", Arguments = "script.py" });
            grid.SelectedIndex = _custom.Count - 1;
        }));
        buttons.Children.Add(Theme.IconButton(Theme.Glyph.Delete, "Remove", (_, _) => { if (grid.SelectedItem is CustomStep s) _custom.Remove(s); }));
        buttons.Children.Add(Theme.IconButton(Theme.Glyph.Up, "Up", (_, _) => Move(grid, -1)));
        buttons.Children.Add(Theme.IconButton(Theme.Glyph.Down, "Down", (_, _) => Move(grid, +1)));
        buttons.Children.Add(Theme.IconButton(Theme.Glyph.Open, "Browse command…", (_, _) =>
        {
            if (grid.SelectedItem is not CustomStep s) return;
            var dlg = new OpenFileDialog { Filter = "Programs and scripts|*.exe;*.bat;*.cmd;*.py;*.ps1|All files|*.*" };
            if (dlg.ShowDialog() != true) return;
            if (dlg.FileName.EndsWith(".py", StringComparison.OrdinalIgnoreCase)) { s.Command = "python"; s.Arguments = $"\"{dlg.FileName}\""; }
            else if (dlg.FileName.EndsWith(".ps1", StringComparison.OrdinalIgnoreCase)) { s.Command = "powershell"; s.Arguments = $"-ExecutionPolicy Bypass -File \"{dlg.FileName}\""; }
            else s.Command = dlg.FileName;
            grid.Items.Refresh();
            _project.Build.CustomSteps = [.. _custom];
            _changed();
        }, "Pick the program or script for the selected step"));
        return new StackPanel { Children = { grid, buttons } };
    }

    private UIElement ContentsGrid()
    {
        var grid = new DataGrid
        {
            ItemsSource = _contents, AutoGenerateColumns = false, CanUserAddRows = false, MinHeight = 90, MaxHeight = 240,
            HeadersVisibility = DataGridHeadersVisibility.Column, SelectionMode = DataGridSelectionMode.Single,
        };
        grid.Columns.Add(new DataGridTextColumn { Header = "Source (file or folder on disk)", Binding = new Binding(nameof(PackContent.Source)), Width = new DataGridLength(1, DataGridLengthUnitType.Star) });
        grid.Columns.Add(new DataGridTextColumn { Header = "Path in pack", Binding = new Binding(nameof(PackContent.Path)), Width = new DataGridLength(1, DataGridLengthUnitType.Star) });
        grid.Columns.Add(new DataGridCheckBoxColumn { Header = "Optional", Binding = new Binding(nameof(PackContent.Optional)) });
        grid.CellEditEnding += (_, _) => Dispatcher.BeginInvoke(() => { _project.Build.Pack.Contents = [.. _contents]; _changed(); });

        var buttons = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 4, 0, 0) };
        buttons.Children.Add(Theme.IconButton(Theme.Glyph.New, "Add folder…", (_, _) =>
        {
            var dlg = new OpenFolderDialog();
            if (dlg.ShowDialog() == true) _contents.Add(new PackContent { Source = dlg.FolderName, Path = "" });
        }));
        buttons.Children.Add(Theme.IconButton(Theme.Glyph.New, "Add file…", (_, _) =>
        {
            var dlg = new OpenFileDialog();
            if (dlg.ShowDialog() == true) _contents.Add(new PackContent { Source = dlg.FileName, Path = Path.GetFileName(dlg.FileName) });
        }));
        buttons.Children.Add(Theme.IconButton(Theme.Glyph.Delete, "Remove", (_, _) => { if (grid.SelectedItem is PackContent c) _contents.Remove(c); }));
        buttons.Children.Add(Theme.IconButton(Theme.Glyph.Build, "Default contents", (_, _) =>
        {
            _contents.Clear();
            foreach (var c in BuildProject.CreateDefault(_project.Map).Build.Pack.Contents) _contents.Add(c);
        }, "The compiled terrain folder, camera heightmap and tree list"));
        return new StackPanel { Children = { grid, buttons } };
    }

    private void Move(DataGrid grid, int delta)
    {
        var i = grid.SelectedIndex;
        if (i < 0 || i + delta < 0 || i + delta >= _custom.Count) return;
        _custom.Move(i, i + delta);
        grid.SelectedIndex = i + delta;
    }

    private string UniqueName(string stem)
    {
        for (var n = 1; ; n++)
            if (_custom.All(c => c.Name != $"{stem} {n}")) return $"{stem} {n}";
    }

    // ------------------------------------------------------------------ fields

    private UIElement Field(string label, Func<string> get, Action<string> set, Browse browse = Browse.None, string? tip = null)
    {
        var grid = Row(label, tip);
        var box = new TextBox { Text = get(), VerticalContentAlignment = VerticalAlignment.Center };
        box.LostFocus += (_, _) =>
        {
            if (box.Text == get()) return;
            set(box.Text.Trim());
            _changed();
        };
        Grid.SetColumn(box, 1);
        grid.Children.Add(box);
        if (browse != Browse.None)
        {
            var button = new Button { Content = "…", Margin = new Thickness(4, 0, 0, 0), Padding = new Thickness(8, 0, 8, 0), ToolTip = "Browse" };
            button.Click += (_, _) =>
            {
                string? picked = browse switch
                {
                    Browse.Folder => new OpenFolderDialog() is var f && f.ShowDialog() == true ? f.FolderName : null,
                    Browse.File => new OpenFileDialog() is var o && o.ShowDialog() == true ? o.FileName : null,
                    _ => new SaveFileDialog { Filter = "Pack (*.pack)|*.pack|All files|*.*" } is var s && s.ShowDialog() == true ? s.FileName : null,
                };
                if (picked is null) return;
                box.Text = picked;
                set(picked);
                _changed();
            };
            Grid.SetColumn(button, 2);
            grid.Children.Add(button);
        }
        return grid;
    }

    private UIElement Combo<T>(string label, T[] values, Func<T> get, Action<T> set, string? tip = null) where T : struct, Enum
    {
        var grid = Row(label, tip);
        var combo = new ComboBox { ItemsSource = values, SelectedItem = get(), HorizontalAlignment = HorizontalAlignment.Left, MinWidth = 140 };
        combo.SelectionChanged += (_, _) => { if (combo.SelectedItem is T v) { set(v); _changed(); } };
        Grid.SetColumn(combo, 1);
        grid.Children.Add(combo);
        return grid;
    }

    private UIElement Check(string label, Func<bool> get, Action<bool> set)
    {
        var box = new CheckBox { Content = label, IsChecked = get(), Margin = new Thickness(160, 4, 0, 4) };
        box.Click += (_, _) => { set(box.IsChecked == true); _changed(); };
        return box;
    }

    private static Grid Row(string label, string? tip)
    {
        var grid = new Grid { Margin = new Thickness(0, 2, 0, 2), ToolTip = tip };
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(160) });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star), MinWidth = 300 });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        grid.Children.Add(new TextBlock { Text = label, VerticalAlignment = VerticalAlignment.Center });
        return grid;
    }

    private static List<string> Split(string v, char sep) =>
        v.Split(sep, StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries).ToList();
}
