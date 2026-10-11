using System.Diagnostics;
using System.IO;
using System.Windows;
using System.Windows.Controls;
using Atlas3K.Core;

namespace Atlas3K.App.Scene;

/// <summary>How the scene editor's tiles work: what tile_map.png and tile_list.bin are, every place tile_list.bin was
/// looked for (and which one won), where the tile database and the 3D tile meshes come from, and how to fix a missing
/// or misplaced file.</summary>
public sealed class TileSourcesWindow : Window
{
    public TileSourcesWindow(SceneModel model, ProjectPaths paths)
    {
        var map = model.Project.MapName;
        Title = AppInfo.Title("How tiles work");
        Width = 760;
        SizeToContent = SizeToContent.Height;
        MaxHeight = 820;
        ResizeMode = ResizeMode.CanResizeWithGrip;
        WindowStartupLocation = WindowStartupLocation.CenterOwner;
        Background = Theme.Brush("Panel");
        Foreground = Theme.Brush("Text");

        var panel = new StackPanel { Margin = new Thickness(16, 8, 16, 16) };
        TextBlock Para(string text) => new() { Text = text, TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 0, 0, 6) };
        TextBlock Mono(string text) => new() { Text = text, TextWrapping = TextWrapping.Wrap, FontFamily = Theme.MonoFont, FontSize = 11, Foreground = Theme.Brush("DimText") };

        panel.Children.Add(Theme.Header("Source and compiled files"));
        panel.Children.Add(Para(
            $"You paint tiles in tile_map.png, a source file in the kit's raw_data (raw_data\\terrain\\campaigns\\{map}\\tile_map.png; " +
            "File > Edit campaign tile map). Building the map (Build window, tile_list step) turns it into tile_list.bin, a compiled " +
            "file that lists every placed tile with its size, turn and heights. The Tiles overlay and the 3D tile meshes show tile_list.bin, " +
            "so after a tile_map.png edit you see the change only after the next build."));
        panel.Children.Add(Para(
            "raw_data holds sources (.terry, tile_map.png, TIFs); working_data holds compiled files. Compiled files copied into raw_data are not read."));

        panel.Children.Add(Theme.Header("tile_list.bin: looked for in this order"));
        var used = false;
        if (model.TileListChecks.Count == 0)
            panel.Children.Add(Para("Not looked up yet (the project has no campaign terrain)."));
        foreach (var check in model.TileListChecks)
        {
            var isUsed = check.Found && !used;
            used |= check.Found;
            var row = new DockPanel { Margin = new Thickness(0, 2, 0, 4) };
            var icon = Theme.Icon(isUsed ? Theme.Glyph.Check : check.Found ? Theme.Glyph.Skipped : Theme.Glyph.Cancelled, 14,
                Theme.Brush(isUsed ? "Ok" : "DimText"));
            icon.VerticalAlignment = VerticalAlignment.Top;
            icon.Margin = new Thickness(0, 1, 8, 0);
            DockPanel.SetDock(icon, Dock.Left);
            row.Children.Add(icon);
            var text = new StackPanel();
            text.Children.Add(new TextBlock
            {
                Text = check.Where + (isUsed ? ": used" : check.Found ? ": found, but an earlier source wins" : ": not there"),
                Foreground = Theme.Brush(isUsed ? "Ok" : "Text"),
            });
            text.Children.Add(Mono(check.Path));
            row.Children.Add(text);
            panel.Children.Add(row);
        }
        if (model.TileListChecks.Count > 0 && model.TileListChecks.All(c => c.Where != "linked mod pack"))
            panel.Children.Add(Para("No mod packs are linked. A modded map's compiled files usually live in its pack: link it in the start window."));

        if ((!used && model.TileListChecks.Count > 0) || model.MisplacedTileList is not null)
        {
            var fix = new StackPanel { Margin = new Thickness(0, 6, 0, 0) };
            var head = new StackPanel { Orientation = Orientation.Horizontal };
            head.Children.Add(Theme.Icon(Theme.Glyph.Warning, 16, Theme.Brush("Warn")));
            head.Children.Add(new TextBlock { Text = used ? "A copy in raw_data is ignored" : "No tile_list.bin found: how to fix", FontWeight = FontWeights.SemiBold, Margin = new Thickness(8, 0, 0, 0), Foreground = Theme.Brush("Warn") });
            fix.Children.Add(head);
            if (model.MisplacedTileList is { } raw)
            {
                fix.Children.Add(Para("Found a compiled tile_list.bin in raw_data, where nothing reads it:"));
                fix.Children.Add(Mono(raw));
                fix.Children.Add(Para($"\nMove the compiled terrain\\campaigns\\{map} folder to working_data instead:"));
            }
            else
                fix.Children.Add(Para("Do one of these, then reopen the scene editor:"));
            fix.Children.Add(Para(
                $"•  Build the map (Build window): the tile_list step writes it into the build output, by default the kit's working_data.\n" +
                $"•  Or copy the compiled files from the pack with RPFM: extract terrain\\campaigns\\{map} (the game's pack for a vanilla map, " +
                $"the mod's pack for a modded one) into\n    {Path.Combine(paths.AkWorkingDir, "terrain", "campaigns", map)}\n" +
                "•  Or link the mod pack in the start window; linked packs are read first."));
            panel.Children.Add(new Border { BorderBrush = Theme.Brush("Warn"), BorderThickness = new Thickness(1), Padding = new Thickness(10, 6, 10, 4), Margin = new Thickness(0, 6, 0, 0), Child = fix });
        }

        panel.Children.Add(Theme.Header("Tile database (sizes, tile sets)"));
        panel.Children.Add(Mono(model.TileDatabaseSource ?? "not read"));

        panel.Children.Add(Theme.Header("Tile meshes in 3D"));
        panel.Children.Add(Para(
            "Each placed tile's own content (cliff meshes, the props in its bmd_data.bin, river water, its blend0 ground) is read from the tile's " +
            "folder under terrain/tiles/campaign/: linked mod packs first, then the game's packs. Toggle it with Tile meshes in the 3D bar."));

        panel.Children.Add(Theme.Header("Last load"));
        panel.Children.Add(Mono(model.TilesNote ?? "-"));

        var buttons = new StackPanel { Orientation = Orientation.Horizontal, HorizontalAlignment = HorizontalAlignment.Right, Margin = new Thickness(0, 14, 0, 0) };
        buttons.Children.Add(Theme.IconButton(Theme.Glyph.Folder, "Open working_data", (_, _) => OpenFolder(paths.AkWorkingDir),
            "Open the kit's working_data folder (the deepest existing folder of terrain\\campaigns\\" + map + ")"));
        buttons.Children.Add(Theme.IconButton(Theme.Glyph.Copy, "Copy report", (_, _) => Clipboard.SetText(Report(model)), "Copy the lookup for a bug report"));
        var ok = new Button { Content = "Close", IsDefault = true, IsCancel = true, MinWidth = 80, Margin = new Thickness(6, 0, 0, 0) };
        ok.Click += (_, _) => Close();
        buttons.Children.Add(ok);
        panel.Children.Add(buttons);
        Content = new ScrollViewer { VerticalScrollBarVisibility = ScrollBarVisibility.Auto, Content = panel };

        void OpenFolder(string workingData)
        {
            var dir = Path.Combine(workingData, "terrain", "campaigns", map);
            while (!Directory.Exists(dir) && Path.GetDirectoryName(dir) is { } parent) dir = parent;
            if (Directory.Exists(dir)) Process.Start(new ProcessStartInfo("explorer.exe", $"\"{dir}\"") { UseShellExecute = true });
        }
    }

    private static string Report(SceneModel model) =>
        $"{AppInfo.Product} {AppInfo.Version} tile lookup for {model.Project.MapName}\n" +
        string.Join("\n", model.TileListChecks.Select(c => $"  [{(c.Found ? "x" : " ")}] {c.Where}: {c.Path}")) +
        (model.MisplacedTileList is { } raw ? $"\n  raw_data copy (ignored): {raw}" : "") +
        $"\n  tile database: {model.TileDatabaseSource ?? "not read"}\n  {model.TilesNote}";
}
